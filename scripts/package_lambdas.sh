#!/bin/bash
# Package all Lambda functions with their dependencies for AWS deployment.
# Layout: root handler matches AWS "handler.lambda_handler"; agent code lives under src/
# so imports like `from src.shared...` resolve (same as production).
# Usage: bash scripts/package_lambdas.sh

set -e

DIST_DIR="dist"
mkdir -p "$DIST_DIR"

echo "Installing dependencies into a temp layer (Linux cp311 wheels for Lambda)..."
LAYER_DIR=$(mktemp -d)
# Lambda is Python 3.11 on Amazon Linux 2; local pip may be 3.12 — force ABI-compatible wheels.
python3 -m pip install \
  fastapi mangum pydantic psycopg2-binary boto3 \
  aws-lambda-powertools "python-jose[cryptography]" \
  mcp bcrypt requests \
  --target "$LAYER_DIR" -q \
  --platform manylinux2014_x86_64 \
  --python-version 3.11 \
  --implementation cp \
  --abi cp311 \
  --only-binary=:all:

# $1 = zip base name (e.g. income_agent), $2 = path to agent package under src/ (e.g. src/income_agent)
package_agent() {
  local zip_name=$1
  local src_dir=$2
  local module
  module=$(basename "$src_dir")

  echo "Packaging $zip_name..."
  local tmp
  tmp=$(mktemp -d)
  cp -r "$LAYER_DIR/." "$tmp/"
  mkdir -p "$tmp/src"
  cp -r src/shared "$tmp/src/"
  cp -r "$src_dir" "$tmp/src/$module"
  printf 'from src.%s.handler import lambda_handler\n' "$module" > "$tmp/handler.py"
  rm -f "$OLDPWD/$DIST_DIR/${zip_name}.zip"
  (
    cd "$tmp"
    zip -r "$OLDPWD/$DIST_DIR/${zip_name}.zip" . -q
  )
  rm -rf "$tmp"
  echo "  ✓ $DIST_DIR/${zip_name}.zip"
}

package_mcp_server() {
  echo "Packaging mcp_server..."
  local tmp
  tmp=$(mktemp -d)
  cp -r "$LAYER_DIR/." "$tmp/"
  mkdir -p "$tmp/src"
  cp -r src/shared "$tmp/src/"
  cp -r src/mcp_server "$tmp/src/mcp_server"
  printf 'from src.mcp_server.simple_handler import lambda_handler\n' > "$tmp/simple_handler.py"
  rm -f "$OLDPWD/$DIST_DIR/mcp_server.zip"
  (
    cd "$tmp"
    zip -r "$OLDPWD/$DIST_DIR/mcp_server.zip" . -q
  )
  rm -rf "$tmp"
  echo "  ✓ $DIST_DIR/mcp_server.zip"
}

package_agent "income_agent"   "src/income_agent"
package_agent "expense_agent"  "src/expense_agent"
package_agent "savings_agent"  "src/savings_agent"
package_agent "insights_agent" "src/insights_agent"
package_mcp_server
package_agent "auth_api"       "src/auth_api"

rm -rf "$LAYER_DIR"
echo ""
echo "✅ All Lambda packages ready in $DIST_DIR/"
ls -lh "$DIST_DIR/"*.zip | tail -8
