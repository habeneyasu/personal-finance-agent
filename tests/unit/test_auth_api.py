"""Unit tests for src/auth_api/handler — register, login, me endpoints."""
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

os.environ.setdefault("ENVIRONMENT", "local")

from src.auth_api.handler import app

client = TestClient(app)


def _mock_conn(fetchone=None, fetchall=None):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone
    mock_cursor.fetchall.return_value = fetchall or []
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


class TestRegister:
    def test_valid_registration_returns_201_with_token(self):
        import uuid
        user_id = uuid.uuid4()
        mock_conn, mock_cursor = _mock_conn(fetchone=None)
        # First fetchone (check existing) returns None, second (insert) returns user_id
        mock_cursor.fetchone.side_effect = [None, (user_id,)]

        with patch("src.auth_api.handler.get_connection", return_value=mock_conn):
            resp = client.post("/auth/register", json={
                "email": "test@example.com",
                "password": "Test1234!"
            })

        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["email"] == "test@example.com"

    def test_duplicate_email_returns_409(self):
        import uuid
        mock_conn, mock_cursor = _mock_conn(fetchone=(uuid.uuid4(),))

        with patch("src.auth_api.handler.get_connection", return_value=mock_conn):
            resp = client.post("/auth/register", json={
                "email": "existing@example.com",
                "password": "Test1234!"
            })

        assert resp.status_code == 409
        assert "already registered" in resp.json()["error"]

    def test_weak_password_returns_400(self):
        resp = client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "weak"
        })
        assert resp.status_code == 400

    def test_invalid_email_returns_400(self):
        resp = client.post("/auth/register", json={
            "email": "notanemail",
            "password": "Test1234!"
        })
        assert resp.status_code == 400

    def test_password_without_uppercase_returns_400(self):
        resp = client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "test1234!"
        })
        assert resp.status_code == 400

    def test_password_without_number_returns_400(self):
        resp = client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "TestPassword!"
        })
        assert resp.status_code == 400


class TestLogin:
    def test_valid_login_returns_token(self):
        import uuid
        import bcrypt
        user_id = uuid.uuid4()
        hashed = bcrypt.hashpw(b"Test1234!", bcrypt.gensalt()).decode()
        mock_conn, mock_cursor = _mock_conn(fetchone=(user_id, "test@example.com", hashed))

        with patch("src.auth_api.handler.get_connection", return_value=mock_conn):
            resp = client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "Test1234!"
            })

        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["email"] == "test@example.com"

    def test_wrong_password_returns_401(self):
        import uuid
        import bcrypt
        user_id = uuid.uuid4()
        hashed = bcrypt.hashpw(b"CorrectPass1!", bcrypt.gensalt()).decode()
        mock_conn, mock_cursor = _mock_conn(fetchone=(user_id, "test@example.com", hashed))

        with patch("src.auth_api.handler.get_connection", return_value=mock_conn):
            resp = client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "WrongPass1!"
            })

        assert resp.status_code == 401
        assert "Invalid" in resp.json()["error"]

    def test_nonexistent_user_returns_401(self):
        mock_conn, mock_cursor = _mock_conn(fetchone=None)

        with patch("src.auth_api.handler.get_connection", return_value=mock_conn):
            resp = client.post("/auth/login", json={
                "email": "nobody@example.com",
                "password": "Test1234!"
            })

        assert resp.status_code == 401


class TestMe:
    def test_valid_token_returns_user_info(self):
        import uuid
        from src.auth_api.handler import _create_token
        user_id = str(uuid.uuid4())
        token = _create_token(user_id, "test@example.com")

        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == user_id
        assert body["email"] == "test@example.com"

    def test_missing_token_returns_401(self):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401
