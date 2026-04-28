"""Shared CORS middleware for all PFIP Lambda handlers."""
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def _default_origin() -> str:
    environment = os.getenv("ENVIRONMENT", "").lower()
    if environment == "production":
        return "http://pfip-production-frontend.s3-website-us-east-1.amazonaws.com"
    if environment == "staging":
        return "http://pfip-staging-frontend.s3-website-us-east-1.amazonaws.com"
    return "http://localhost:5173"


def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    if raw:
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return [_default_origin()]


def cors_headers(origin: str | None) -> dict:
    allowed = _allowed_origins()
    o = (origin or "").rstrip("/")
    if o in allowed:
        allow = o
    elif allowed:
        allow = allowed[0]
    else:
        allow = "*"
    return {
        "Access-Control-Allow-Origin": allow,
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
    }


def add_cors_middleware(app: FastAPI) -> None:
    """Attach CORS middleware to a FastAPI app."""

    @app.middleware("http")
    async def _cors(request: Request, call_next):
        origin = request.headers.get("origin") or request.headers.get("Origin")
        if request.method == "OPTIONS":
            return JSONResponse(content={}, headers=cors_headers(origin))
        response = await call_next(request)
        for k, v in cors_headers(origin).items():
            response.headers[k] = v
        return response
