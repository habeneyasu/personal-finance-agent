# PFIP AWS Deployment Guide

## Prerequisites

1. AWS CLI configured: `aws configure`
2. Terraform installed: `terraform -version`
3. Node.js 20+: `node --version`
4. Python 3.11+: `python3 --version`

## Step 1 — Gather AWS values

```bash
# Your AWS account ID
aws sts get-caller-identity --query Account --output text

# Default VPC ID
aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text

# Two subnets in different AZs
aws ec2 describe-subnets \
  --filters "Name=defaultForAz,Values=true" \
  --query "Subnets[0:2].SubnetId" --output text
```

## Step 2 — Create Terraform variables file

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
# Edit infra/terraform.tfvars with your real values
```

Required values to fill in:
- `vpc_id` — from Step 1
- `subnet_ids` — from Step 1
- `aurora_master_password` — strong password (min 8 chars)
- `jwt_secret` — run: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `pfip_api_key` — run: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- optional `cors_allow_origin` — must be a single browser origin (never comma-separated)

## Local vs AWS config (avoid mixing)

Use separate config sources per environment:

- **Local dev (`scripts/run_api_local.py`)**
  - reads `.env.local`
  - should use `ENVIRONMENT=local`
  - frontend origin is `http://localhost:5173`
- **AWS staging/production (`terraform apply`)**
  - reads `infra/terraform.tfvars` or `TF_VAR_*`
  - must set `jwt_secret`, `pfip_api_key`, DB/VPC vars
  - CORS should be a single deployed frontend origin

Do not share one comma-separated `ALLOWED_ORIGINS` string across local + AWS deploys.

## Step 3 — Enable Bedrock model access

In AWS Console → Bedrock → Model access → Request access for:
- `amazon.nova-lite-v1:0` (or `anthropic.claude-3-haiku-20240307-v1:0`)

## Step 4 — Create Terraform state bucket

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3 mb s3://pfip-terraform-state-${ACCOUNT_ID} --region us-east-1
```

Then uncomment the `backend "s3"` block in `infra/main.tf` and replace `YOUR_ACCOUNT_ID`.

## Step 5 — Deploy infrastructure

```bash
cd infra
terraform init
terraform plan    # review what will be created
terraform apply   # type 'yes' to confirm
```

Save the outputs:
```bash
terraform output  # copy all values
```

## Step 6 — Package and deploy Lambdas

The Insights Agent includes an LLM-as-Judge pipeline (`src/insights_agent/judge.py`).
Make sure it's included in the Lambda package — `package_lambdas.sh` handles this automatically.

```bash
cd ..
bash scripts/package_lambdas.sh

# Deploy each Lambda
for agent in income_agent expense_agent savings_agent insights_agent mcp_server auth_api; do
  aws lambda update-function-code \
    --function-name "pfip-staging-${agent//_/-}" \
    --zip-file "fileb://dist/${agent}.zip" \
    --no-cli-pager
done
```

## Step 7 — Run DB migration

```bash
DB_SECRET_ARN=$(cd infra && terraform output -raw aurora_secret_arn)
DB_SECRET_ARN=$DB_SECRET_ARN python3 scripts/migrate.py --env staging
```

If your Aurora cluster is private, run migration from inside the VPC (bastion/SSM/VPN).

## Step 8 — Seed demo data

```bash
DB_SECRET_ARN=$(cd infra && terraform output -raw aurora_secret_arn)
DB_SECRET_ARN=$DB_SECRET_ARN python3 scripts/seed_demo.py --env staging --reset
```

## Step 9 — Build and deploy frontend

```bash
API_URL=$(cd infra && terraform output -raw api_gateway_url)
echo "VITE_API_URL=${API_URL}" > frontend/.env.production

cd frontend
npm ci
npm run build

BUCKET=$(cd ../infra && terraform output -raw frontend_bucket)
aws s3 sync dist/ "s3://${BUCKET}/" --delete

DIST_ID=$(cd ../infra && terraform output -raw cloudfront_distribution_id 2>/dev/null || echo "")
if [ -n "$DIST_ID" ]; then
  aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"
fi
```

## Step 10 — Set GitHub Secrets (for CI/CD)

In GitHub → Settings → Secrets → Actions, add:

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `AURORA_MASTER_PASSWORD` | Same as terraform.tfvars |
| `TF_VPC_ID` | Your VPC ID |
| `TF_SUBNET_IDS` | `["subnet-xxx","subnet-yyy"]` |
| `JWT_SECRET` | Same as terraform.tfvars |
| `PFIP_API_KEY` | Same as terraform.tfvars |
| `VITE_API_URL` | From `terraform output api_gateway_url` |
| `FRONTEND_S3_BUCKET` | From `terraform output frontend_bucket` |
| `CLOUDFRONT_DISTRIBUTION_ID` | From `terraform output cloudfront_distribution_id` |

## Verify deployment

```bash
API_URL=$(cd infra && terraform output -raw api_gateway_url)

# Health check (auth endpoint — no auth required)
curl -s "${API_URL}/auth/login" -X POST \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@pfip.dev","password":"Demo1234!"}'

# Frontend
FRONTEND_URL=$(cd infra && terraform output -raw frontend_url)
echo "Dashboard: $FRONTEND_URL"
```

## Teardown

```bash
cd infra
terraform destroy  # type 'yes' — this deletes everything including the DB
```
