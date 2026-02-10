"""FastAPI application entry point."""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from ..infrastructure.config import settings
from .routes import health, analyze, admin, credits, user

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Initialize rate limiter
# 100 requests per minute per IP - very generous for normal use
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Ruh API...")
    logger.info(f"Debug mode: {settings.debug}")
    yield
    logger.info("Shutting down Ruh API...")


# Create FastAPI app
app = FastAPI(
    title="Ruh API",
    description="AI-powered product safety analysis backend",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS for Chrome extensions and web clients
# Origins configured via ALLOWED_ORIGINS env var (comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
    expose_headers=["X-Request-ID"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


# Private Network Access: raw ASGI middleware (not BaseHTTPMiddleware) that
# intercepts at the protocol level before CORSMiddleware handles OPTIONS.
# Only active in debug mode — production uses public URLs, not loopback.
class PrivateNetworkAccessMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("method") == "OPTIONS":
            headers_dict = {k: v for k, v in scope.get("headers", [])}
            if b"access-control-request-private-network" in headers_dict:
                origin = headers_dict.get(b"origin", b"*")
                response_headers = [
                    (b"access-control-allow-private-network", b"true"),
                    (b"access-control-allow-origin", origin),
                    (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
                    (b"access-control-allow-headers", b"Content-Type, Authorization, Accept"),
                    (b"access-control-allow-credentials", b"true"),
                    (b"content-length", b"0"),
                ]
                await send({"type": "http.response.start", "status": 200, "headers": response_headers})
                await send({"type": "http.response.body", "body": b""})
                return
        await self.app(scope, receive, send)

if settings.debug:
    app.add_middleware(PrivateNetworkAccessMiddleware)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(analyze.router, prefix="/api", tags=["analysis"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(credits.router, prefix="/api", tags=["credits"])
app.include_router(user.router, prefix="/api", tags=["user"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Ruh API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }
