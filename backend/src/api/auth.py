"""API authentication using Bearer tokens."""

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..infrastructure.config import settings

# Security scheme for Bearer token
security = HTTPBearer()


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Verify the API key from the Authorization header.

    Args:
        credentials: HTTP Bearer credentials from the request header

    Returns:
        The verified API key

    Raises:
        HTTPException: If the API key is invalid
    """
    if credentials.credentials != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
