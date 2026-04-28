#!/bin/bash
# Seed demo data via the staging API (no direct DB access needed)
# Usage: bash scripts/seed_via_api.sh

API="https://8sm0pyqys1.execute-api.us-east-1.amazonaws.com/api"
EMAIL="haben123@gmail.com"
PASSWORD="Test123456!"

echo "=== PFIP Staging Seed via API ==="

# 1. Login
echo "Logging in..."
TOKEN=$(curl -s -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))")

if [ -z "$TOKEN" ]; then
  echo "ERROR: Login failed"
  exit 1
fi
echo "✓ Logged in"

AUTH="Authorization: Bearer $TOKEN"
CT="Content-Type: application/json"

# Helper
post() { curl -s -X POST "$API/v1/$1" -H "$CT" -H "$AUTH" -d "$2" > /dev/null && echo "✓ $1"; }

# 2. Income entries
TODAY=$(date +%Y-%m-%d)
M1=$(date -d "30 days ago" +%Y-%m-%d 2>/dev/null || date -v-30d +%Y-%m-%d)
M2=$(date -d "60 days ago" +%Y-%m-%d 2>/dev/null || date -v-60d +%Y-%m-%d)
M3=$(date -d "90 days ago" +%Y-%m-%d 2>/dev/null || date -v-90d +%Y-%m-%d)

echo "Seeding income..."
post "income" "{\"amount\":5000,\"source\":\"Salary\",\"date\":\"$TODAY\"}"
post "income" "{\"amount\":950,\"source\":\"Freelance\",\"date\":\"$M1\"}"
post "income" "{\"amount\":5000,\"source\":\"Salary\",\"date\":\"$M1\"}"
post "income" "{\"amount\":1200,\"source\":\"Freelance\",\"date\":\"$M2\"}"
post "income" "{\"amount\":5000,\"source\":\"Salary\",\"date\":\"$M2\"}"
post "income" "{\"amount\":800,\"source\":\"Freelance\",\"date\":\"$M3\"}"

# 3. Expense entries
echo "Seeding expenses..."
post "expenses" "{\"amount\":87.50,\"merchant\":\"Whole Foods\",\"date\":\"$TODAY\"}"
post "expenses" "{\"amount\":24.50,\"merchant\":\"Uber\",\"date\":\"$TODAY\"}"
post "expenses" "{\"amount\":68.00,\"merchant\":\"The Capital Grille\",\"date\":\"$TODAY\"}"
post "expenses" "{\"amount\":15.99,\"merchant\":\"Netflix\",\"date\":\"$M1\"}"
post "expenses" "{\"amount\":120.00,\"merchant\":\"Electric Company\",\"date\":\"$M1\"}"
post "expenses" "{\"amount\":89.99,\"merchant\":\"Amazon\",\"date\":\"$M1\"}"
post "expenses" "{\"amount\":62.30,\"merchant\":\"Trader Joes\",\"date\":\"$M1\"}"
post "expenses" "{\"amount\":32.50,\"merchant\":\"Chipotle\",\"date\":\"$M2\"}"
post "expenses" "{\"amount\":45.00,\"merchant\":\"Shell Gas Station\",\"date\":\"$M2\"}"
post "expenses" "{\"amount\":150.00,\"merchant\":\"Dental Clinic\",\"date\":\"$M2\"}"
post "expenses" "{\"amount\":145.00,\"merchant\":\"Nike Store\",\"date\":\"$M2\"}"
post "expenses" "{\"amount\":85.00,\"merchant\":\"Internet Provider\",\"date\":\"$M3\"}"
post "expenses" "{\"amount\":200.00,\"merchant\":\"Car Insurance\",\"date\":\"$M3\"}"

# 4. Savings goals
echo "Seeding goals..."
GOAL1=$(date -d "180 days" +%Y-%m-%d 2>/dev/null || date -v+180d +%Y-%m-%d)
GOAL2=$(date -d "365 days" +%Y-%m-%d 2>/dev/null || date -v+365d +%Y-%m-%d)
post "goals" "{\"name\":\"Vacation Fund\",\"target_amount\":3000,\"target_date\":\"$GOAL1\"}"
post "goals" "{\"name\":\"Emergency Fund\",\"target_amount\":10000,\"target_date\":\"$GOAL2\"}"

echo ""
echo "=== Seed complete! ==="
echo "Open: http://pfip-staging-frontend.s3-website-us-east-1.amazonaws.com"
