# 🏦 Personal Financial Intelligence Platform (PFIP)

> **AI-Native Personal Finance with Model Context Protocol Integration**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![AWS](https://img.shields.io/badge/AWS-Lambda-orange.svg)](https://aws.amazon.com/lambda/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org)
[![MCP](https://img.shields.io/badge/MCP-1.0-purple.svg)](https://modelcontextprotocol.io)
[![Coverage](https://img.shields.io/badge/Coverage-90%25-brightgreen.svg)](https://pytest.org)

A cutting-edge personal finance platform that combines **AI-powered insights** with **serverless architecture** and **Model Context Protocol (MCP)** integration. Track income, categorize expenses automatically, manage savings goals, and query your financial data in natural language.

---

## ✨ Key Features

### 🤖 AI-Powered Intelligence
- **Smart Expense Categorization** using AWS Bedrock (Claude/Nova)
- **Natural Language Insights** - Query your finances in plain English
- **LLM-as-Judge System** with Chain-of-Thought retry and SQL fallback
- **Accuracy Tracking** for continuous improvement

### 🏗️ Modern Architecture
- **Serverless-First** on AWS Lambda with FastAPI
- **Aurora Serverless v2** PostgreSQL database
- **Microservices Design** with specialized agents
- **Model Context Protocol** for Claude Desktop integration

### 📊 Comprehensive Financial Management
- **Income Tracking** with recurring income support
- **Expense Management** with automatic categorization
- **Savings Goals** with progress tracking and milestones
- **Real-time Metrics** and visual analytics

### 🔒 Enterprise-Grade Security
- **AWS Cognito** authentication (production)
- **JWT-based auth** for local development
- **Secrets Manager** integration
- **IAM role-based access control**

---

## 🏛️ Architecture Overview

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[React Dashboard]
        B[MCP Inspector]
    end
    
    subgraph "API Gateway"
        C[API Gateway]
    end
    
    subgraph "Lambda Microservices"
        D[Income Agent]
        E[Expense Agent]
        F[Savings Agent]
        G[Insights Agent]
        H[Metrics Agent]
        I[Auth API]
        J[MCP Server]
    end
    
    subgraph "AI Services"
        K[AWS Bedrock]
        L[LLM Judge]
    end
    
    subgraph "Data Layer"
        M[Aurora Serverless]
        N[Secrets Manager]
    end
    
    A --> C
    B --> C
    C --> D
    C --> E
    C --> F
    C --> G
    C --> H
    C --> I
    C --> J
    
    E --> K
    G --> K
    E --> L
    G --> L
    
    D --> M
    E --> M
    F --> M
    G --> M
    H --> M
    I --> M
    
    D --> N
    E --> N
    F --> N
    G --> N
    H --> N
    I --> N
```

### 📁 Project Structure

```
pfip-mvp/
├── 📂 src/
│   ├── 📂 shared/              # Core utilities (auth, db, llm, logging)
│   ├── 📂 income_agent/        # Income tracking microservice
│   ├── 📂 expense_agent/       # Expense management + AI categorizer
│   ├── 📂 savings_agent/       # Savings goals + progress calculator
│   ├── 📂 insights_agent/      # NL insights + LLM judge system
│   ├── 📂 metrics_agent/        # Real-time financial metrics
│   ├── 📂 mcp_server/          # Model Context Protocol server
│   └── 📂 auth_api/            # Authentication service
├── 📂 infra/                   # Terraform infrastructure
├── 📂 frontend/                # React dashboard
├── 📂 tests/                   # Comprehensive test suite
├── 📂 scripts/                 # Utilities and migration tools
└── 📂 .github/workflows/       # CI/CD pipeline
```

---

## 🚀 Quick Start

### 📋 Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- AWS CLI (for deployment)

### 🏠 Local Development

**1. Clone & Setup**
```bash
git clone https://github.com/your-org/pfip-mvp.git
cd pfip-mvp
```

**2. Start Database**
```bash
docker-compose up -d
```

**3. Setup Environment**
```bash
export $(cat .env.local | grep -v '^#' | grep -v '^$' | xargs)
```

**4. Run Database Setup**
```bash
python3 scripts/migrate.py --env local
python3 scripts/seed_demo.py --env local --reset
```

**5. Start Backend API**
```bash
uvicorn scripts.run_api_local:app --port 8000 --reload
```

**6. Start Frontend**
```bash
cd frontend && npm install && npm run dev
```

**7. Access the Application**
- 🌐 Frontend: http://localhost:5173
- 🔐 Login: `demo@pfip.dev` / `Demo1234!`
- 📚 API Docs: http://localhost:8000/docs

**8. Optional: MCP Inspector**
```bash
npx @modelcontextprotocol/inspector python3 scripts/run_mcp_local.py
```

---

## 🧪 Testing

### Run All Tests
```bash
pip install -e ".[dev]"
ENVIRONMENT=local pytest tests/unit/ --cov=src --cov-fail-under=80 -q
```

### Test Categories
- **126 Unit Tests** with 90% coverage
- **Integration Tests** for API endpoints
- **LLM Accuracy Tests** for categorization
- **MCP Protocol Tests** for tool compliance

---

## 🌩️ AWS Deployment

### Infrastructure as Code
```bash
cd infra
terraform init
terraform apply \
  -var="aurora_master_password=YourSecurePassword" \
  -var="subnet_ids=[\"subnet-xxx\",\"subnet-yyy\"]" \
  -var="vpc_id=vpc-xxx"
```

### CI/CD Integration
The platform includes a complete GitHub Actions pipeline for:
- **Automated Testing** on every push
- **Infrastructure Deployment** on merge
- **Security Scanning** and compliance checks
- **Performance Monitoring** setup

### Required Secrets
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `AURORA_MASTER_PASSWORD`, `TF_SUBNET_IDS`, `TF_VPC_ID`
- `JWT_SECRET`, `BEDROCK_API_KEY`

---

## 📚 API Documentation

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/income` | GET/POST | Income tracking and management |
| `/v1/expenses` | GET/POST | Expense tracking with AI categorization |
| `/v1/goals` | GET/POST | Savings goals and progress |
| `/v1/insights/query` | POST | Natural language financial insights |
| `/v1/metrics` | GET | Real-time financial metrics |
| `/auth/*` | POST | Authentication (local dev only) |

### MCP Integration
The platform exposes **7 tools** and **3 resources** through the Model Context Protocol:
- **Tools**: Add income, categorize expenses, create goals, query insights, get metrics, calculate savings, export data
- **Resources**: Financial summary, transaction history, goal progress

---

## 🎯 Use Cases

### 💼 Personal Finance Management
- Track monthly income and expenses
- Set and monitor savings goals
- Get AI-powered spending insights
- Export financial reports

### 🤖 AI Assistant Integration
- Connect with Claude Desktop via MCP
- Query finances in natural language
- Automate categorization workflows
- Generate personalized insights

### 📊 Financial Analytics
- Real-time spending patterns
- Goal progress visualization
- Income vs expense analysis
- Predictive savings projections

---

## 🔧 Development

### Code Quality
- **Type Hints** throughout the codebase
- **Pydantic Models** for data validation
- **Structured Logging** with correlation IDs
- **Error Handling** with custom exceptions

### Performance
- **Serverless Architecture** for auto-scaling
- **Database Connection Pooling**
- **Caching Strategy** for frequently accessed data
- **Async Operations** where applicable

### Security
- **Input Validation** and sanitization
- **SQL Injection Prevention** with parameterized queries
- **Authentication & Authorization** checks
- **Secrets Management** best practices

---

## 📈 Roadmap

### 🚧 In Progress
- [ ] Mobile app development
- [ ] Advanced AI insights (spending predictions)
- [ ] Multi-currency support
- [ ] Investment tracking integration

### 🎯 Coming Soon
- [ ] Budget planning tools
- [ ] Bill payment reminders
- [ ] Tax optimization insights
- [ ] Financial health scoring

### 💡 Future Enhancements
- [ ] Plaid integration for bank syncing
- [ ] Machine learning for fraud detection
- [ ] Collaborative family budgeting
- [ ] Advanced reporting and analytics

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Ensure all tests pass
5. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **AWS** for serverless infrastructure
- **FastAPI** for the web framework
- **Model Context Protocol** team for the AI integration standard
- **React** community for the frontend ecosystem

---

## 📞 Support

- 📧 Email: support@pfip.dev
- 📖 Documentation: [docs.pfip.dev](https://docs.pfip.dev)
- 🐛 Issues: [GitHub Issues](https://github.com/your-org/pfip-mvp/issues)
- 💬 Discord: [Join our community](https://discord.gg/pfip)

---

<div align="center">

**🌟 Star this repo if it inspired you!**

Made with ❤️ by the PFIP Team

</div>
