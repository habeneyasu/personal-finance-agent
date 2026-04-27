"""
Local auth API — register and login with email/password.
Issues JWT tokens compatible with the existing auth middleware.

Endpoints:
  POST /auth/register  — create account
  POST /auth/login     — get JWT token
  GET  /auth/me        — get current user info
"""
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import psycopg2
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from jose import jwt
from mangum import Mangum
from pydantic import BaseModel, ValidationError, field_validator
from psycopg2 import errors as pg_errors

from src.shared.db import get_connection, get_cursor
from src.shared.cors import cors_headers

_logger = logging.getLogger(__name__)

app = FastAPI(title="PFIP Auth")

def get_cors_headers(origin: str | None = None) -> dict:
    """Use shared CORS policy so auth and other agents stay aligned."""
    return cors_headers(origin)

# CORS middleware for all responses
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin") or request.headers.get("Origin")
    cors_headers = get_cors_headers(origin)
    
    for header, value in cors_headers.items():
        response.headers[header] = value
    
    return response

JWT_SECRET = os.getenv("JWT_SECRET", "pfip-local-dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


@app.exception_handler(pg_errors.UndefinedTable)
async def pg_undefined_table_handler(request: Request, exc: pg_errors.UndefinedTable):
    """Aurora reachable but schema not applied — typical after first terraform apply."""
    _logger.warning("PostgreSQL undefined relation: %s", exc)
    origin = request.headers.get("origin") or request.headers.get("Origin")
    return JSONResponse(
        status_code=503,
        content={
            "error": "database_schema_missing",
            "status": 503,
            "message": (
                "PFIP tables are missing on this database. Run scripts/migrate.py from a "
                "host inside the VPC (or port-forward to Aurora), then retry."
            ),
        },
        headers=get_cors_headers(origin),
    )


@app.exception_handler(psycopg2.OperationalError)
async def pg_operational_handler(request: Request, exc: psycopg2.OperationalError):
    _logger.warning("PostgreSQL operational error: %s", exc)
    origin = request.headers.get("origin") or request.headers.get("Origin")
    return JSONResponse(
        status_code=503,
        content={
            "error": "database_unavailable",
            "status": 503,
            "message": "Could not reach PostgreSQL. Check Aurora status, security groups, and VPC routing.",
        },
        headers=get_cors_headers(origin),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return JSON + CORS headers (API Gateway never adds CORS to raw Lambda error dicts)."""
    _logger.exception("Unhandled error in auth API: %s", exc)
    origin = request.headers.get("origin") or request.headers.get("Origin")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "status": 500},
        headers=get_cors_headers(origin),
    )


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
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
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


def _validation_error_message(exc: ValidationError) -> str:
    """Single user-facing line from Pydantic (avoids dumping the full error blob)."""
    errs = exc.errors()
    if not errs:
        return "Invalid input"
    msg = errs[0].get("msg", "Invalid input")
    if isinstance(msg, str) and msg.startswith("Value error, "):
        return msg[len("Value error, ") :]
    return str(msg)


@app.get("/v1")
async def health_v1():
    return JSONResponse({"status": "ok", "service": "pfip-auth-api"})


@app.post("/auth/register", status_code=201)
@app.post("/v1/auth/register", status_code=201)
async def register(request: Request):
    try:
        body = await request.json()
        req = RegisterRequest(**body)
    except ValidationError as e:
        return _error(_validation_error_message(e), 422)
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
@app.post("/v1/auth/login")
async def login(request: Request):
    try:
        body = await request.json()
        req = LoginRequest(**body)
    except ValidationError as e:
        return _error(_validation_error_message(e), 422)
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


@app.options("/auth/register")
@app.options("/v1/auth/register")
@app.options("/auth/login")
@app.options("/v1/auth/login")
@app.options("/auth/me")
@app.options("/v1/auth/me")
async def options_handler(request: Request):
    """Handle CORS preflight requests."""
    origin = request.headers.get("origin") or request.headers.get("Origin")
    cors_headers = get_cors_headers(origin)
    return JSONResponse(content={"message": "CORS preflight successful"}, headers=cors_headers)

@app.get("/auth/me")
@app.get("/v1/auth/me")
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


_mangum = Mangum(app)


def lambda_handler(event: dict, context) -> dict:
    return _mangum(event, context)
