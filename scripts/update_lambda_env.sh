#!/bin/bash
# Update Lambda environment variables from current shell env.
# Run:
#   export DB_HOST=...
#   export DB_PASSWORD=...
#   export JWT_SECRET=...
#   export CEREBRAS_API_KEY=...   # optional
#   bash scripts/update_lambda_env.sh

set -euo pipefail

required_vars=(
  DB_HOST
  DB_NAME
  DB_USER
  DB_PASSWORD
  JWT_SECRET
)

for v in "${required_vars[@]}"; do
  if [[ -z "${!v:-}" ]]; then
    echo "Missing required env var: $v" >&2
    exit 1
  fi
done

ENVIRONMENT_VALUE="${ENVIRONMENT:-staging}"
AWS_REGION_VALUE="${AWS_REGION_NAME:-us-east-1}"
DB_PORT_VALUE="${DB_PORT:-5432}"
BEDROCK_MODEL_VALUE="${BEDROCK_MODEL_ID:-amazon.nova-lite-v1:0}"
ALLOWED_ORIGINS_VALUE="${ALLOWED_ORIGINS:-http://localhost:5173}"
CEREBRAS_MODEL_VALUE="${CEREBRAS_MODEL:-llama3.1-8b}"
FUNCTION_PREFIX="${LAMBDA_FUNCTION_PREFIX:-pfip-staging}"
export ENVIRONMENT_VALUE AWS_REGION_VALUE DB_PORT_VALUE BEDROCK_MODEL_VALUE
export ALLOWED_ORIGINS_VALUE CEREBRAS_MODEL_VALUE

# Build JSON payload without echoing secret values.
TMPFILE=$(mktemp /tmp/lambda_env_XXXXXX.json)
trap 'rm -f "$TMPFILE"' EXIT
python3 - <<'PY' > "$TMPFILE"
import json
import os

variables = {
    "ENVIRONMENT": os.environ["ENVIRONMENT_VALUE"],
    "DB_HOST": os.environ["DB_HOST"],
    "DB_PORT": os.environ["DB_PORT_VALUE"],
    "DB_NAME": os.environ["DB_NAME"],
    "DB_USER": os.environ["DB_USER"],
    "DB_PASSWORD": os.environ["DB_PASSWORD"],
    "JWT_SECRET": os.environ["JWT_SECRET"],
    "BEDROCK_MODEL_ID": os.environ["BEDROCK_MODEL_VALUE"],
    "AWS_REGION_NAME": os.environ["AWS_REGION_VALUE"],
    "ALLOWED_ORIGINS": os.environ["ALLOWED_ORIGINS_VALUE"],
    "CEREBRAS_MODEL": os.environ["CEREBRAS_MODEL_VALUE"],
}

cerebras_api_key = os.environ.get("CEREBRAS_API_KEY")
if cerebras_api_key:
    variables["CEREBRAS_API_KEY"] = cerebras_api_key

print(json.dumps({"Variables": variables}))
PY

for fn in insights-agent income-agent expense-agent savings-agent metrics-agent auth-api; do
  function_name="${FUNCTION_PREFIX}-${fn}"
  echo -n "${function_name}: "
  aws lambda update-function-configuration \
    --function-name "${function_name}" \
    --region "${AWS_REGION_VALUE}" \
    --environment "file://${TMPFILE}" \
    --query 'LastUpdateStatus' \
    --output text
  sleep 2
done

echo "Done."
