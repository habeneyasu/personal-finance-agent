#!/bin/bash
# Package all Lambda functions with their dependencies for AWS deployment
# Usage: bash scripts/package_lambdas.sh

set -e

DIST_DIR="dist"
mkdir -p "$DIST_DIR"

echo "Installing dependencies into a temp layer..."
LAYER_DIR=$(mktemp -d)
pip3 install \
  fastapi mangum pydantic psycopg2-binary boto3 \
  aws-lambda-powertools python-jose[cryptography] \
  mcp bcrypt requests \
  --target "$LAYER_DIR" -q

package_agent() {
  local name=$1
  local src_dir=$2
  echo "Packaging $name..."
  local tmp=$(mktemp -d)
  cp -r "$LAYER_DIR/." "$tmp/"
  cp -r src/shared "$tmp/"
  cp -r "$src_dir" "$tmp/$(basename $src_dir)"
  cd "$tmp"
  zip -r "$OLDPWD/$DIST_DIR/${name}.zip" . -q
  cd "$OLDPWD"
  rm -rf "$tmp"
  echo "  ✓ $DIST_DIR/${name}.zip"
}

package_agent "income_agent"   "src/income_agent"
package_agent "expense_agent"  "src/expense_agent"
package_agent "savings_agent"  "src/savings_agent"
package_agent "insights_agent" "src/insights_agent"
package_agent "mcp_server"     "src/mcp_server"

rm -rf "$LAYER_DIR"
echo ""
echo "✅ All Lambda packages ready in $DIST_DIR/"
ls -lh "$DIST_DIR/"
