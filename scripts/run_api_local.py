"""
Unified local FastAPI server — mounts all 4 agents on a single app.

Usage:
    uvicorn scripts.run_api_local:app --port 8000 --reload

Endpoints:
    POST/GET  /v1/income
    POST/GET  /v1/expenses
    POST/GET  /v1/goals
    POST      /v1/insights/query
"""
import os
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
os.environ.setdefault("DB_PASSWORD", "pfip_local_password")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import jwt as jose_jwt, JWTError

# Import handler functions directly from each agent
from src.income_agent.handler import create_income, list_income
from src.expense_agent.handler import create_expense, list_expenses
from src.savings_agent.handler import create_goal, list_goals
from src.insights_agent.handler import query_insights

JWT_SECRET = os.getenv("JWT_SECRET", "pfip-local-dev-secret-key-change-in-production")

app = FastAPI(title="PFIP Local API", version="0.1.0")

# Allow all origins for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
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

# Register all routes directly on the unified app
app.post("/v1/income", status_code=201)(create_income)
app.get("/v1/income")(list_income)

app.post("/v1/expenses", status_code=201)(create_expense)
app.get("/v1/expenses")(list_expenses)

app.post("/v1/goals", status_code=201)(create_goal)
app.get("/v1/goals")(list_goals)

app.post("/v1/insights/query")(query_insights)

# Mount auth routes directly
from src.auth_api.handler import register, login, me
app.post("/auth/register", status_code=201)(register)
app.post("/auth/login")(login)
app.get("/auth/me")(me)


@app.get("/health")
def health():
    return {"status": "ok", "service": "pfip-local-api"}
