"""
Unified local FastAPI server — mounts all 4 agents on a single app.

Usage:
    uvicorn scripts.run_api_local:app --port 8000 --reload

`app` is CORSMiddleware wrapping the FastAPI instance so CORS headers are added even
when ServerErrorMiddleware returns 500s (e.g. DB down); otherwise browsers report a
false "CORS" error with no Access-Control-Allow-Origin on the error body.

Endpoints:
    POST/GET  /v1/income
    POST/GET  /v1/expenses
    POST/GET  /v1/goals
    POST      /v1/insights/query
"""
import os
import secrets
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env.local if it exists — always override with file values
_env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local")
if os.path.exists(_env_file):
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip()
                if val:  # only set if value is non-empty
                    os.environ[key] = val

# Set local environment — bypasses Cognito auth and uses local DB
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5433")
os.environ.setdefault("DB_NAME", "pfip")
os.environ.setdefault("DB_USER", "pfip_admin")
if not os.environ.get("JWT_SECRET"):
    os.environ["JWT_SECRET"] = secrets.token_urlsafe(32)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from jose import jwt as jose_jwt, JWTError
from psycopg2 import OperationalError

# Import handler functions directly from each agent
from src.income_agent.handler import create_income, list_income
from src.expense_agent.handler import create_expense, list_expenses
from src.savings_agent.handler import create_goal, list_goals
from src.insights_agent.handler import query_insights
from src.metrics_agent.handler import get_metrics

JWT_SECRET = os.environ["JWT_SECRET"]

api = FastAPI(title="PFIP Local API", version="0.1.0")


@api.middleware("http")
async def inject_auth_event(request: Request, call_next):
    """Inject a mock AWS event into request scope so agent handlers can extract user_id."""
    auth_header = request.headers.get("Authorization", "")
    user_id = "00000000-0000-0000-0000-000000000001"  # default local dev user

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jose_jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user_id = payload.get("sub", user_id)
        except JWTError:
            pass  # fall back to default local user

    # Inject mock API Gateway event so get_user_id_from_event works
    request.scope["aws.event"] = {
        "requestContext": {
            "authorizer": {
                "claims": {"sub": user_id}
            }
        },
        "headers": dict(request.headers),
    }
    return await call_next(request)


@api.exception_handler(OperationalError)
async def handle_db_operational_error(_: Request, __: OperationalError):
    """Return a stable JSON error when local Postgres is unavailable."""
    return JSONResponse(
        status_code=503,
        content={
            "error": "database_unavailable",
            "detail": "Could not connect to Postgres on localhost:5433. Start DB with `docker compose up -d`.",
            "status": 503,
        },
    )


# Register all routes directly on the unified app
api.post("/v1/income", status_code=201)(create_income)
api.get("/v1/income")(list_income)

api.post("/v1/expenses", status_code=201)(create_expense)
api.get("/v1/expenses")(list_expenses)

api.post("/v1/goals", status_code=201)(create_goal)
api.get("/v1/goals")(list_goals)

api.post("/v1/insights/query")(query_insights)
api.get("/v1/metrics")(get_metrics)

# Add endpoints without /v1 prefix for frontend compatibility
api.post("/income", status_code=201)(create_income)
api.get("/income")(list_income)

api.post("/expenses", status_code=201)(create_expense)
api.get("/expenses")(list_expenses)

api.post("/goals", status_code=201)(create_goal)
api.get("/goals")(list_goals)

api.post("/insights/query")(query_insights)
api.get("/metrics")(get_metrics)

# Mount auth routes directly
from src.auth_api.handler import register, login, me

api.post("/auth/register", status_code=201)(register)
api.post("/auth/login")(login)
api.get("/auth/me")(me)


@api.get("/health")
def health():
    return {"status": "ok", "service": "pfip-local-api"}


# Outer CORS so 500s from ServerErrorMiddleware still get Access-Control-Allow-Origin
app = CORSMiddleware(
    api,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)
