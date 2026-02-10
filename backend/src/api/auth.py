"""API authentication: dual-mode JWT (Supabase Auth) + static API key."""

import logging
import secrets
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..infrastructure.config import settings

logger = logging.getLogger(__name__)

# Security scheme for Bearer token
security = HTTPBearer()


@dataclass
class AuthContext:
    """Authentication context passed to route handlers.

    Attributes:
        user_id: Internal user UUID (None for legacy API key auth)
        auth_id: Supabase Auth UID (None for legacy API key auth)
        tier: User tier - 'free', 'basic', 'middle', 'unlimited'
        credits_remaining: Current credit balance (-1 for unlimited, -1 for API key)
        is_api_key: True if authenticated via legacy static API key
    """
    user_id: Optional[UUID] = None
    auth_id: Optional[UUID] = None
    tier: str = "free"
    credits_remaining: int = -1
    is_api_key: bool = False


def _try_decode_jwt(token: str) -> Optional[dict]:
    """Attempt to decode a Supabase Auth JWT.

    Returns decoded payload on success, None on any failure.
    """
    if not settings.supabase_jwt_secret:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("JWT decode failed: %s", e)
        return None


async def _resolve_user_from_jwt(payload: dict) -> AuthContext:
    """Look up (or create) the internal user from a decoded JWT payload.

    The actual user creation + credit initialization happens in credit_service
    (Phase 3). For now, we return a minimal AuthContext with the auth_id so
    the route can identify the caller.
    """
    auth_id = payload.get("sub")
    if not auth_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT missing sub claim",
        )

    # Import here to avoid circular imports — credit_service depends on
    # database which depends on config, and auth is imported by routes.
    from ..infrastructure.database import db

    if not db.is_available:
        # DB down — allow the request through with minimal context.
        # The route can still serve cached data or degrade gracefully.
        return AuthContext(
            auth_id=UUID(auth_id),
            tier="free",
            credits_remaining=0,
            is_api_key=False,
        )

    try:
        # Look up user by auth_id
        response = db.client.table("users").select(
            "id"
        ).eq("auth_id", auth_id).execute()

        if response.data:
            user_id = UUID(response.data[0]["id"])
        else:
            # First-time login — create user row. Tier + credits are
            # initialized by credit_service.get_or_create_user_from_auth()
            # (wired in Phase 3). For now, insert a basic user row.
            user_data = {
                "auth_id": auth_id,
                "email": payload.get("email", ""),
            }
            insert_resp = db.client.table("users").insert(user_data).execute()
            user_id = UUID(insert_resp.data[0]["id"])

            # Initialize default tier + credits via RPC
            db.client.rpc("initialize_user_credits", {
                "p_user_id": str(user_id),
            }).execute()
            logger.info("Created new user %s from auth_id %s", user_id, auth_id)

        # Fetch tier and credit balance
        tier_resp = db.client.table("user_tiers").select(
            "tier"
        ).eq("user_id", str(user_id)).execute()

        credit_resp = db.client.table("credit_ledger").select(
            "credits_remaining"
        ).eq("user_id", str(user_id)).execute()

        tier = tier_resp.data[0]["tier"] if tier_resp.data else "free"
        credits = credit_resp.data[0]["credits_remaining"] if credit_resp.data else 0

        if tier == "unlimited":
            credits = -1

        return AuthContext(
            user_id=user_id,
            auth_id=UUID(auth_id),
            tier=tier,
            credits_remaining=credits,
            is_api_key=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to resolve user from JWT: %s", e)
        # Don't block the request — return a degraded context
        return AuthContext(
            auth_id=UUID(auth_id),
            tier="free",
            credits_remaining=0,
            is_api_key=False,
        )


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> AuthContext:
    """Authenticate the request via JWT or static API key.

    Priority:
    1. Try decoding the Bearer token as a Supabase JWT
    2. Fall back to static API key comparison
    3. Reject if neither succeeds

    Returns:
        AuthContext with user identity and authorization info
    """
    token = credentials.credentials

    # --- Path 1: Supabase JWT ---
    payload = _try_decode_jwt(token)
    if payload is not None:
        return await _resolve_user_from_jwt(payload)

    # --- Path 2: Static API key (migration compatibility) ---
    if secrets.compare_digest(token, settings.api_key):
        return AuthContext(is_api_key=True)

    # --- Neither worked ---
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Keep legacy function for backward compatibility during migration.
# Routes can be updated incrementally from verify_api_key → get_auth_context.
async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Legacy: verify static API key only. Use get_auth_context for new routes."""
    if not secrets.compare_digest(credentials.credentials, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
