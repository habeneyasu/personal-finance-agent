# Contributing to PFIP

Thank you for your interest in contributing to the Personal Financial Intelligence Platform! This guide will help you get started with contributing to our project.

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- AWS CLI (for deployment)
- Git

### Setup Development Environment

1. **Fork the Repository**
   ```bash
   # Fork the repository on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/pfip-mvp.git
   cd pfip-mvp
   git remote add upstream https://github.com/original-org/pfip-mvp.git
   ```

2. **Set Up Python Environment**
   ```bash
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -e ".[dev]"
   ```

3. **Set Up Frontend**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Start Local Development**
   ```bash
   # Start database
   docker-compose up -d
   
   # Set up environment
   export $(cat .env.local | grep -v '^#' | grep -v '^$' | xargs)
   
   # Run migrations
   python3 scripts/migrate.py --env local
   python3 scripts/seed_demo.py --env local --reset
   
   # Start backend (in one terminal)
   uvicorn scripts.run_api_local:app --port 8000 --reload
   
   # Start frontend (in another terminal)
   cd frontend && npm run dev
   ```

## 📝 Development Guidelines

### Code Style

We follow these coding standards:

#### Python
- **PEP 8** for Python code formatting
- **Type hints** for all function signatures and complex variables
- **Docstrings** for all public functions and classes
- **Maximum line length**: 88 characters

```python
from typing import List, Optional
from pydantic import BaseModel

class IncomeEntry(BaseModel):
    """Model for income entry data."""
    
    amount: Decimal
    source: str
    date: datetime
    notes: Optional[str] = None
    
    def calculate_tax(self, rate: float) -> Decimal:
        """Calculate tax amount based on rate."""
        return self.amount * Decimal(str(rate))
```

#### JavaScript/TypeScript
- **ESLint** configuration included
- **Prettier** for code formatting
- **Functional components** preferred
- **TypeScript** for type safety

```typescript
interface IncomeEntry {
  amount: number;
  source: string;
  date: string;
  notes?: string;
}

const IncomeCard: React.FC<{ entry: IncomeEntry }> = ({ entry }) => {
  return (
    <div className="income-card">
      <h3>{entry.source}</h3>
      <p>${entry.amount.toFixed(2)}</p>
    </div>
  );
};
```

### Testing Guidelines

#### Writing Tests
- **Unit tests** for all business logic
- **Integration tests** for API endpoints
- **Mock external dependencies** (AWS services, databases)
- **Test coverage minimum**: 80%

```python
import pytest
from unittest.mock import Mock, patch
from src.income_agent.handler import create_income

@pytest.mark.asyncio
async def test_create_income_success():
    """Test successful income entry creation."""
    # Arrange
    mock_request = Mock()
    mock_request.json.return_value = {
        "amount": 1000.00,
        "source": "Salary",
        "date": "2024-01-01"
    }
    
    # Act
    with patch('src.income_agent.handler.get_user_id_from_event') as mock_auth:
        mock_auth.return_value = "test-user-id"
        response = await create_income(mock_request)
    
    # Assert
    assert response.status_code == 201
    assert "id" in response.json()
```

#### Running Tests
```bash
# Run all tests
pytest tests/unit/ --cov=src --cov-fail-under=80

# Run specific test file
pytest tests/unit/test_income_agent.py -v

# Run with coverage report
pytest tests/unit/ --cov=src --cov-report=html
```

### Commit Guidelines

We use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Build process or dependency changes

#### Examples
```bash
feat(income): add recurring income support
fix(auth): resolve JWT token expiration issue
docs(readme): update installation instructions
test(expenses): add categorization unit tests
```

## 🏗️ Project Structure

Understanding the codebase organization:

```
src/
├── shared/              # Shared utilities and helpers
│   ├── auth.py          # Authentication logic
│   ├── database.py      # Database connection and utilities
│   ├── llm.py          # LLM integration and helpers
│   └── logger.py        # Structured logging setup
├── income_agent/        # Income tracking microservice
│   ├── handler.py       # FastAPI endpoints
│   ├── models.py        # Pydantic models
│   └── __init__.py
├── expense_agent/       # Expense management microservice
│   ├── handler.py       # API endpoints
│   ├── categorizer.py   # AI categorization logic
│   ├── models.py        # Data models
│   └── __init__.py
├── savings_agent/       # Savings goals microservice
├── insights_agent/      # AI insights microservice
├── metrics_agent/        # Financial metrics microservice
├── mcp_server/          # Model Context Protocol server
└── auth_api/            # Authentication service
```

## 🔄 Development Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes
- Write code following our style guidelines
- Add tests for new functionality
- Update documentation if needed
- Ensure all tests pass

### 3. Test Your Changes
```bash
# Run unit tests
pytest tests/unit/ --cov=src

# Run integration tests
pytest tests/integration/

# Check code style
flake8 src/
black src/
```

### 4. Commit Changes
```bash
git add .
git commit -m "feat(your-scope): add your feature description"
```

### 5. Push and Create Pull Request
```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear title and description
- Reference any related issues
- Include screenshots if UI changes
- Add testing instructions

## 🐛 Bug Reports

### Reporting Bugs
1. **Search existing issues** first
2. **Use the bug report template** in GitHub Issues
3. **Include**:
   - Environment details (OS, Python version, etc.)
   - Steps to reproduce
   - Expected vs actual behavior
   - Error logs and screenshots
   - Minimal reproduction example

### Bug Report Template
```markdown
**Bug Description**
Brief description of the bug

**Steps to Reproduce**
1. Step one
2. Step two
3. Step three

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.11.5]
- Browser: [e.g., Chrome 120]

**Additional Context**
Any other relevant information
```

## 💡 Feature Requests

### Proposing Features
1. **Check roadmap** and existing issues
2. **Discuss in GitHub Discussions** first
3. **Create detailed proposal** including:
   - Problem statement
   - Proposed solution
   - Implementation approach
   - Acceptance criteria

### Feature Request Template
```markdown
**Feature Description**
Clear description of the feature

**Problem Statement**
What problem does this solve?

**Proposed Solution**
How should this work?

**Implementation Ideas**
Technical approach or implementation details

**Acceptance Criteria**
What defines "done" for this feature
```

## 🔧 Code Review Process

### Review Guidelines
- **Be constructive** and respectful
- **Focus on code quality**, not personal preferences
- **Explain reasoning** for suggested changes
- **Approve** when you're confident in the code quality

### Review Checklist
- [ ] Code follows style guidelines
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No breaking changes (or clearly documented)
- [ ] Security considerations addressed
- [ ] Performance implications considered

## 📚 Documentation

### Updating Documentation
- **README.md**: Project overview and quick start
- **API docs**: Update docstrings for new endpoints
- **Architecture docs**: Update for major changes
- **Deployment guides**: Keep instructions current

### Documentation Style
- **Clear, concise language**
- **Code examples** for complex concepts
- **Consistent formatting**
- **Links to related documentation**

## 🚀 Release Process

### Versioning
We follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Steps
1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md**
3. **Create release tag**
4. **Deploy to production**
5. **Announce release**

## 🤝 Community Guidelines

### Code of Conduct
- **Be respectful** and inclusive
- **Welcome newcomers** and help them learn
- **Focus on constructive feedback**
- **Avoid personal attacks** or criticism

### Getting Help
- **GitHub Discussions**: General questions and ideas
- **GitHub Issues**: Bug reports and feature requests
- **Discord**: Real-time chat and community support
- **Email**: security@pfip.dev for security issues

## 🏆 Recognition

### Contributors
All contributors are recognized in:
- **README.md** contributor section
- **Release notes** for each version
- **Annual contributor awards**

### Types of Contributions
- **Code**: Features, fixes, tests
- **Documentation**: Guides, tutorials, API docs
- **Community**: Support, discussions, reviews
- **Design**: UI/UX, graphics, architecture

---

## 📞 Need Help?

- **📧 Email**: dev@pfip.dev
- **💬 Discord**: [Join our community](https://discord.gg/pfip)
- **📖 Documentation**: [docs.pfip.dev](https://docs.pfip.dev)
- **🐛 Issues**: [GitHub Issues](https://github.com/your-org/pfip-mvp/issues)

Thank you for contributing to PFIP! 🎉
