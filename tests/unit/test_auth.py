"""Unit tests for src/shared/auth — JWT verification and user ID extraction."""
import os
from unittest.mock import MagicMock, patch

import pytest
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from src.shared.auth import (
    AuthError,
    extract_user_id,
    get_user_id_from_event,
    verify_token,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_claims(sub: str = "user-uuid-123") -> dict:
    return {"sub": sub, "email": "test@example.com", "token_use": "access"}


# ---------------------------------------------------------------------------
# verify_token tests
# ---------------------------------------------------------------------------

class TestVerifyToken:
    """Tests for verify_token."""

    def test_local_env_bypasses_verification(self, monkeypatch):
        """When ENVIRONMENT=local, verify_token returns mock claims without hitting Cognito."""
        monkeypatch.setenv("ENVIRONMENT", "local")
        monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_abc123")

        result = verify_token("any.token.value")

        assert result["sub"] == "00000000-0000-0000-0000-000000000001"

    def test_missing_user_pool_id_bypasses_verification(self, monkeypatch):
        """When COGNITO_USER_POOL_ID is not set, verify_token returns mock claims."""
        monkeypatch.delenv("COGNITO_USER_POOL_ID", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")

        result = verify_token("any.token.value")

        assert result["sub"] == "00000000-0000-0000-0000-000000000001"

    def test_valid_token_returns_claims(self, monkeypatch):
        """verify_token with a valid mock JWT returns decoded claims."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_abc123")
        monkeypatch.setenv("COGNITO_REGION", "us-east-1")

        expected_claims = _make_mock_claims()

        with patch("src.shared.auth.jwt.get_unverified_header") as mock_header, \
             patch("src.shared.auth.get_cognito_public_keys") as mock_jwks, \
             patch("src.shared.auth.jwt.decode") as mock_decode:

            mock_header.return_value = {"kid": "key-id-1", "alg": "RS256"}
            mock_jwks.return_value = {"keys": [{"kid": "key-id-1", "kty": "RSA"}]}
            mock_decode.return_value = expected_claims

            result = verify_token("valid.jwt.token")

        assert result == expected_claims
        assert result["sub"] == "user-uuid-123"

    def test_expired_token_raises_auth_error_401(self, monkeypatch):
        """verify_token with expired token raises AuthError with status_code=401."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_abc123")
        monkeypatch.setenv("COGNITO_REGION", "us-east-1")

        with patch("src.shared.auth.jwt.get_unverified_header") as mock_header, \
             patch("src.shared.auth.get_cognito_public_keys") as mock_jwks, \
             patch("src.shared.auth.jwt.decode") as mock_decode:

            mock_header.return_value = {"kid": "key-id-1", "alg": "RS256"}
            mock_jwks.return_value = {"keys": [{"kid": "key-id-1", "kty": "RSA"}]}
            mock_decode.side_effect = JWTError("Signature has expired")

            with pytest.raises(AuthError) as exc_info:
                verify_token("expired.jwt.token")

        assert exc_info.value.status_code == 401
        assert "JWT verification failed" in exc_info.value.message

    def test_malformed_token_raises_auth_error_401(self, monkeypatch):
        """verify_token with malformed token raises AuthError with status_code=401."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_abc123")
        monkeypatch.setenv("COGNITO_REGION", "us-east-1")

        with patch("src.shared.auth.jwt.get_unverified_header") as mock_header:
            mock_header.side_effect = JWTError("Not enough segments")

            with pytest.raises(AuthError) as exc_info:
                verify_token("not-a-jwt")

        assert exc_info.value.status_code == 401

    def test_missing_kid_in_header_raises_auth_error(self, monkeypatch):
        """verify_token raises AuthError when token has no 'kid' and is not a valid local JWT."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_abc123")
        monkeypatch.setenv("COGNITO_REGION", "us-east-1")
        monkeypatch.setenv("JWT_SECRET", "test-secret")

        with patch("src.shared.auth.jwt.get_unverified_header") as mock_header, \
             patch("src.shared.auth.jwt.decode") as mock_decode:
            mock_header.return_value = {"alg": "HS256"}  # no 'kid'
            mock_decode.side_effect = JWTError("Invalid token")  # local JWT also fails

            with pytest.raises(AuthError) as exc_info:
                verify_token("invalid.local.token")

        assert exc_info.value.status_code == 401

    def test_unknown_kid_raises_auth_error(self, monkeypatch):
        """verify_token raises AuthError when kid doesn't match any JWKS key."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-east-1_abc123")
        monkeypatch.setenv("COGNITO_REGION", "us-east-1")

        with patch("src.shared.auth.jwt.get_unverified_header") as mock_header, \
             patch("src.shared.auth.get_cognito_public_keys") as mock_jwks:

            mock_header.return_value = {"kid": "unknown-kid", "alg": "RS256"}
            mock_jwks.return_value = {"keys": [{"kid": "different-kid", "kty": "RSA"}]}

            with pytest.raises(AuthError) as exc_info:
                verify_token("token.with.unknown.kid")

        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# extract_user_id tests
# ---------------------------------------------------------------------------

class TestExtractUserId:
    """Tests for extract_user_id."""

    def test_returns_sub_from_claims(self):
        """extract_user_id returns the 'sub' field from claims."""
        claims = {"sub": "user-uuid-abc", "email": "user@example.com"}
        assert extract_user_id(claims) == "user-uuid-abc"

    def test_raises_auth_error_when_sub_missing(self):
        """extract_user_id raises AuthError when 'sub' is not in claims."""
        claims = {"email": "user@example.com"}
        with pytest.raises(AuthError) as exc_info:
            extract_user_id(claims)
        assert exc_info.value.status_code == 401

    def test_raises_auth_error_when_sub_is_none(self):
        """extract_user_id raises AuthError when 'sub' is None."""
        claims = {"sub": None}
        with pytest.raises(AuthError) as exc_info:
            extract_user_id(claims)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_user_id_from_event tests
# ---------------------------------------------------------------------------

class TestGetUserIdFromEvent:
    """Tests for get_user_id_from_event."""

    def test_local_env_returns_local_dev_user(self, monkeypatch):
        """When ENVIRONMENT=local, returns fixed UUID without checking event."""
        monkeypatch.setenv("ENVIRONMENT", "local")
        result = get_user_id_from_event({})
        assert result == "00000000-0000-0000-0000-000000000001"

    def test_api_gateway_claims_path(self, monkeypatch):
        """Extracts user_id from API Gateway authorizer claims."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": "apigw-user-uuid"}
                }
            }
        }
        result = get_user_id_from_event(event)
        assert result == "apigw-user-uuid"

    def test_bearer_token_path(self, monkeypatch):
        """Falls back to verifying Authorization header token."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        event = {
            "headers": {"Authorization": "Bearer valid.jwt.token"}
        }
        with patch("src.shared.auth.verify_token") as mock_verify:
            mock_verify.return_value = {"sub": "mcp-user-uuid"}
            result = get_user_id_from_event(event)

        assert result == "mcp-user-uuid"

    def test_no_auth_raises_auth_error(self, monkeypatch):
        """Raises AuthError when no authentication is present."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        with pytest.raises(AuthError) as exc_info:
            get_user_id_from_event({})
        assert exc_info.value.status_code == 401

    def test_lowercase_authorization_header(self, monkeypatch):
        """Handles lowercase 'authorization' header."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        event = {
            "headers": {"authorization": "Bearer valid.jwt.token"}
        }
        with patch("src.shared.auth.verify_token") as mock_verify:
            mock_verify.return_value = {"sub": "mcp-user-uuid"}
            result = get_user_id_from_event(event)

        assert result == "mcp-user-uuid"


# ---------------------------------------------------------------------------
# AuthError tests
# ---------------------------------------------------------------------------

class TestAuthError:
    """Tests for AuthError exception class."""

    def test_default_status_code_is_401(self):
        err = AuthError("unauthorized")
        assert err.status_code == 401

    def test_message_field(self):
        err = AuthError("token expired")
        assert err.message == "token expired"

    def test_custom_status_code(self):
        err = AuthError("forbidden", status_code=403)
        assert err.status_code == 403
