"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from ..infrastructure.config import settings
from .routes import health, analyze

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Eject API...")
    logger.info(f"Debug mode: {settings.debug}")
    yield
    logger.info("Shutting down Eject API...")


# Create FastAPI app
app = FastAPI(
    title="Eject API",
    description="AI-powered product safety analysis backend",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(analyze.router, prefix="/api", tags=["analysis"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Eject API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }
