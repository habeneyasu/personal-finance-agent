# PFIP Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the Personal Finance Intelligence Platform (PFIP) to AWS production environment.

## Architecture Overview

PFIP is built on a serverless AWS architecture with the following components:

### Infrastructure Components
- **API Gateway**: REST API with CORS support
- **Lambda Functions**: 6 microservices (auth, income, expense, savings, insights, mcp-server)
- **Aurora Serverless**: PostgreSQL-compatible database
- **Cognito**: User authentication (configured but not used in current auth implementation)
- **S3**: Frontend static hosting
- **CloudFront**: CDN for frontend (optional)
- **Secrets Manager**: Secure credential storage
- **CloudWatch**: Logging and monitoring

### Application Architecture
- **Frontend**: React/Vite application
- **Backend**: Python FastAPI microservices
- **AI Integration**: AWS Bedrock with Nova Lite model
- **Authentication**: Custom JWT-based auth system

## Prerequisites

### Required Tools
- AWS CLI v2.34.30+
- Terraform v1.14.9+
- Node.js v20.19.5+
- Python 3.11+
- Git

### AWS Account Setup
1. AWS account with appropriate permissions
2. VPC and subnets configured
3. Bedrock model access enabled (amazon.nova-lite-v1:0)
4. IAM roles for Lambda execution

## Deployment Steps

### 1. Environment Configuration

#### AWS Values Gathering
```bash
# Get AWS account ID
aws sts get-caller-identity --query Account --output text

# Get VPC ID (using default VPC)
aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text

# Get subnet IDs (using default subnets)
aws ec2 describe-subnets --filters "Name=defaultForAz,Values=true" --query "Subnets[0:2].SubnetId" --output text
```

#### Generate Secrets
```bash
# Generate JWT secret
python3 -c "import secrets; print(secrets.token_hex(32))"

# Generate API key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate database password
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

#### Create Terraform Variables
Create `infra/terraform.tfvars`:
```hcl
# AWS Configuration
aws_region = "us-east-1"
environment = "production"
project_name = "pfip"

# Database Configuration
aurora_master_password = "your_secure_password"

# VPC Configuration
vpc_id = "your_vpc_id"
subnet_ids = [
  "your_subnet_1",
  "your_subnet_2"
]

# Authentication
jwt_secret = "your_jwt_secret"
pfip_api_key = "your_api_key"
```

### 2. Terraform Deployment

#### Initialize Terraform
```bash
cd infra
terraform init
```

#### Create Terraform State Bucket
```bash
aws s3 mb s3://pfip-terraform-state-YOUR_ACCOUNT_ID --region us-east-1
```

#### Deploy Infrastructure
```bash
terraform plan
terraform apply
```

### 3. Lambda Function Deployment

#### Package Lambda Functions
```bash
# Package all Lambda functions
scripts/package_lambdas.sh

# Manual packaging for auth API (if needed)
cd src/auth_api
pip install bcrypt --platform manylinux2014_x86_64 --only-binary=:all: -t .
zip -r ../../dist/auth_api_final.zip . -x "*.pyc" "__pycache__/*"
```

#### Deploy Lambda Functions
```bash
# Deploy main Lambda functions
aws lambda update-function-code --function-name pfip-production-income-agent --zip-file fileb://dist/income_agent.zip
aws lambda update-function-code --function-name pfip-production-expense-agent --zip-file fileb://dist/expense_agent.zip
aws lambda update-function-code --function-name pfip-production-savings-agent --zip-file fileb://dist/savings_agent.zip
aws lambda update-function-code --function-name pfip-production-insights-agent --zip-file fileb://dist/insights_agent.zip
aws lambda update-function-code --function-name pfip-production-mcp-server --zip-file fileb://dist/mcp_server.zip

# Deploy auth API
aws lambda update-function-code --function-name pfip-production-auth-api --zip-file fileb://dist/auth_api_final.zip
```

### 4. Frontend Deployment

#### Configure API URL
Update `frontend/src/api.ts`:
```typescript
const BASE_URL = import.meta.env.VITE_API_URL || 'https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/v1'
```

#### Build and Deploy Frontend
```bash
cd frontend
npm run build
aws s3 sync dist/ s3://your-frontend-bucket --delete
```

### 5. Database Setup

#### Run Database Migration
```bash
export DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:pfip/production/db-credentials-SECRET_ID
python3 scripts/migrate.py
```

## Production URLs

### Application Endpoints
- **Frontend**: `http://pfip-production-frontend.s3-website-us-east-1.amazonaws.com`
- **API Gateway**: `https://your-api-id.execute-api.us-east-1.amazonaws.com/v1`
- **Auth Endpoints**: 
  - `POST /v1/auth/register`
  - `POST /v1/auth/login`
  - `GET /v1/auth/health`

### API Endpoints
- **Income**: `GET/POST /v1/income`
- **Expenses**: `GET/POST /v1/expenses`
- **Goals**: `GET/POST /v1/goals`
- **Insights**: `POST /v1/insights/query`
- **Metrics**: `GET /v1/metrics`

## Monitoring and Logging

### CloudWatch Logs
- **Lambda Logs**: `/aws/lambda/pfip-production-*`
- **API Gateway Logs**: Available through execution logs
- **Database Logs**: Aurora PostgreSQL logs

### Monitoring Setup
```bash
# Create CloudWatch dashboards
aws logs create-log-group --log-group-name /aws/lambda/pfip-production-metrics --retention-in-days 7

# Set up alarms (examples)
aws cloudwatch put-metric-alarm --alarm-name "PFIP-HighErrorRate" --metric-name Errors --namespace AWS/Lambda --threshold 10 --comparison-operator GreaterThanThreshold --evaluation-periods 2
```

## Security Configuration

### Network Security
- VPC isolation with private subnets
- Security groups for Lambda functions
- API Gateway with CORS configuration
- Secrets Manager for credential storage

### IAM Roles
- Lambda execution roles with least privilege
- Cross-service communication via IAM policies
- Bedrock model access permissions

## Troubleshooting

### Common Issues

#### Lambda Deployment Issues
- **Pydantic Dependencies**: Use platform-specific packages
- **Missing Handler**: Ensure handler.py is in zip root
- **Import Errors**: Check package structure and dependencies

#### CORS Issues
- **Preflight Failures**: Ensure OPTIONS method configured
- **Origin Headers**: Check CORS configuration in API Gateway
- **Integration Issues**: Verify deployment includes CORS resources

#### Database Connectivity
- **Timeout Issues**: Check Aurora cluster status
- **Authentication**: Verify Secrets Manager access
- **Network Configuration**: Ensure VPC connectivity

### Debug Commands
```bash
# Check Lambda logs
aws logs filter-log-events --log-group-name /aws/lambda/pfip-production-auth-api --start-time $(date -d '5 minutes ago' +%s)000

# Test API endpoints
curl -X POST https://your-api.execute-api.us-east-1.amazonaws.com/v1/auth/register -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"testpassword123"}'

# Check API Gateway deployment
aws apigateway get-deployments --rest-api-id your-api-id
```

## Maintenance

### Regular Tasks
- Monitor Lambda function performance
- Review CloudWatch metrics and logs
- Update dependencies as needed
- Backup database regularly
- Rotate secrets periodically

### Scaling Considerations
- Lambda auto-scaling configured
- Aurora Serverless auto-scaling
- API Gateway throttling limits
- S3 bandwidth considerations

## Rollback Procedures

### Terraform Rollback
```bash
terraform plan -destroy
terraform apply -destroy
# Then redeploy with previous configuration
```

### Lambda Rollback
```bash
# Update with previous working version
aws lambda update-function-code --function-name function-name --zip-file fileb://dist/previous-version.zip
```

### Frontend Rollback
```bash
# Deploy previous frontend build
aws s3 sync dist/previous/ s3://your-frontend-bucket --delete
```

## Support

### Contact Information
- **Development Team**: [team@pfip.com]
- **Infrastructure Support**: [infra@pfip.com]
- **Emergency Contact**: [emergency@pfip.com]

### Documentation
- **API Documentation**: Available at `/docs/api`
- **Architecture Guide**: Available at `/docs/architecture`
- **Troubleshooting Guide**: Available at `/docs/troubleshooting`

---

**Last Updated**: April 23, 2026
**Version**: 1.0
**Environment**: Production
