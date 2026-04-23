"""Authentication middleware for Cognito JWT verification."""
import os
from typing import Optional

import requests
from jose import JWTError, jwt

from src.shared.logger import logger

# Module-level cache for JWKS
_jwks_cache: dict[str, dict] = {}


class AuthError(Exception):
    """Authentication error with HTTP status code."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_cognito_public_keys(user_pool_id: str, region: str) -> dict:
    """Fetch JWKS from Cognito's well-known endpoint.

    Results are cached in a module-level dict to avoid fetching on every request.

    Args:
        user_pool_id: Cognito user pool ID
        region: AWS region (e.g., 'us-east-1')

    Returns:
        JWKS dict with 'keys' array

    Raises:
        AuthError: If fetching JWKS fails
    """
    cache_key = f"{region}:{user_pool_id}"
    if cache_key in _jwks_cache:
        return _jwks_cache[cache_key]

    jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        jwks = response.json()
        _jwks_cache[cache_key] = jwks
        return jwks
    except Exception as e:
        raise AuthError(f"Failed to fetch JWKS: {e}", status_code=401) from e


def verify_token(token: str) -> dict:
    """Decode and verify a Cognito JWT.

    For LOCAL development (when ENVIRONMENT=local or COGNITO_USER_POOL_ID is not set),
    skip JWT verification and return mock claims.

    Args:
        token: JWT token string

    Returns:
        Decoded claims dict

    Raises:
        AuthError: On any verification failure (expired, invalid, malformed)
    """
    environment = os.getenv("ENVIRONMENT", "").lower()
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID")

    # Local dev bypass
    if environment == "local" or not user_pool_id:
        logger.info(
            "Local dev mode: bypassing JWT verification",
            user_id="local-dev-user",
            operation="verify_token",
            status="ok",
        )
        return {"sub": "00000000-0000-0000-0000-000000000001", "email": "dev@local.test"}

    region = os.getenv("COGNITO_REGION", "us-east-1")

    try:
        # Get kid from token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # Local JWT tokens (HS256, no kid) — verify with local secret
        if not kid:
            local_secret = os.getenv("JWT_SECRET", "pfip-local-dev-secret-key-change-in-production")
            try:
                claims = jwt.decode(token, local_secret, algorithms=["HS256"])
                return claims
            except JWTError:
                pass  # Fall through to Cognito verification

        # Fetch JWKS and find matching key
        jwks = get_cognito_public_keys(user_pool_id, region)
        key = None
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key = k
                break

        if not key:
            raise AuthError(f"Public key not found for kid: {kid}", status_code=401)

        # Verify signature, expiry, and decode
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Cognito tokens may not have 'aud'
        )
        return claims

    except JWTError as e:
        raise AuthError(f"JWT verification failed: {e}", status_code=401) from e
    except Exception as e:
        raise AuthError(f"Token verification error: {e}", status_code=401) from e


def extract_user_id(claims: dict) -> str:
    """Extract user ID from JWT claims.

    Args:
        claims: Decoded JWT claims dict

    Returns:
        User ID (Cognito 'sub' field)

    Raises:
        AuthError: If 'sub' field is missing
    """
    user_id = claims.get("sub")
    if not user_id:
        raise AuthError("Claims missing 'sub' field", status_code=401)
    return user_id


def get_user_id_from_event(event: dict) -> str:
    """Extract user_id from Lambda event.

    Handles three paths:
    1. API Gateway path: event.requestContext.authorizer.claims.sub
    2. MCP server path: verify Authorization header token directly
    3. Local dev: return 'local-dev-user'

    Args:
        event: Lambda event dict

    Returns:
        User ID string

    Raises:
        AuthError: If authentication fails
    """
    environment = os.getenv("ENVIRONMENT", "").lower()

    # Local dev bypass
    if environment == "local":
        return "00000000-0000-0000-0000-000000000001"

    # Path 1: API Gateway authorizer claims
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    if claims and "sub" in claims:
        return claims["sub"]

    # Path 2: Authorization header — local JWT or MCP server path
    headers = event.get("headers", {}) or {}
    auth_header = headers.get("Authorization") or headers.get("authorization", "")
    if auth_header:
        # Extract token from "Bearer <token>"
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            claims = verify_token(token)
            return extract_user_id(claims)

    raise AuthError("No valid authentication found", status_code=401)
