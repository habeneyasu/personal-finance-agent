"""
Local auth API — register and login with email/password.
Issues JWT tokens compatible with the existing auth middleware.

Endpoints:
  POST /auth/register  — create account
  POST /auth/login     — get JWT token
  GET  /auth/me        — get current user info
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from jose import jwt
from pydantic import BaseModel, field_validator

from src.shared.db import get_connection, get_cursor

app = FastAPI(title="PFIP Auth")

# Secret key for local JWT signing — in production this is Cognito
JWT_SECRET = os.getenv("JWT_SECRET", "pfip-local-dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


class RegisterRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address")
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


def _create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _error(detail: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": detail, "status": status})


@app.post("/auth/register", status_code=201)
async def register(request: Request):
    try:
        body = await request.json()
        req = RegisterRequest(**body)
    except Exception as e:
        return _error(str(e), 400)

    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    user_id = str(uuid.uuid4())

    conn = get_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute(
                "SELECT id FROM users WHERE email = %s", (req.email,)
            )
            if cur.fetchone():
                return _error("Email already registered", 409)

            cur.execute(
                "INSERT INTO users (id, email, hashed_password) VALUES (%s, %s, %s) RETURNING id",
                (user_id, req.email, hashed),
            )
            row = cur.fetchone()
            user_id = str(row[0])
    finally:
        conn.close()

    token = _create_token(user_id, req.email)
    return JSONResponse(status_code=201, content={
        "access_token": token,
        "token_type": "bearer",
        "user_id": user_id,
        "email": req.email,
    })


@app.post("/auth/login")
async def login(request: Request):
    try:
        body = await request.json()
        req = LoginRequest(**body)
    except Exception as e:
        return _error(str(e), 400)

    conn = get_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute(
                "SELECT id, email, hashed_password FROM users WHERE email = %s",
                (req.email.lower().strip(),),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    # Generic error to prevent user enumeration
    if not row or not row[2]:
        return _error("Invalid email or password", 401)

    if not bcrypt.checkpw(req.password.encode(), row[2].encode()):
        return _error("Invalid email or password", 401)

    token = _create_token(str(row[0]), row[1])
    return JSONResponse(content={
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(row[0]),
        "email": row[1],
    })


@app.get("/auth/me")
async def me(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return _error("Missing token", 401)

    token = auth_header[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return JSONResponse(content={
            "user_id": payload["sub"],
            "email": payload["email"],
        })
    except Exception:
        return _error("Invalid or expired token", 401)
