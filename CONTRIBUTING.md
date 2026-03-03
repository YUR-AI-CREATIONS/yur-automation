# Contributing to FranklinOps

Thank you for your interest in contributing to FranklinOps! We welcome contributions from the community and are pleased to have them.

## 🚀 Quick Start for Contributors

### Prerequisites
- Python 3.11+
- Git
- Basic understanding of business automation concepts

### Development Setup

1. **Fork and clone the repository:**
```bash
git clone https://github.com/YUR-AI-CREATIONS/yur-automation.git
cd yur-automation
```

2. **Create a virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install development dependencies:**
```bash
pip install -r requirements-minimal.txt
pip install pytest black isort flake8  # Development tools
```

4. **Set up your environment:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Run the system:**
```bash
python -m uvicorn src.franklinops.server:app --host 127.0.0.1 --port 8000 --reload
```

## 🎯 How to Contribute

### Types of Contributions We Welcome

- **🐛 Bug Fixes**: Help us squash bugs and improve reliability
- **✨ Feature Enhancements**: Add new capabilities to existing spokes
- **🔧 New Integrations**: Connect to additional business systems
- **📚 Documentation**: Improve guides, examples, and API docs
- **🧪 Testing**: Expand test coverage and add edge case testing
- **🎨 UI/UX Improvements**: Enhance the user interface and experience

### Development Workflow

1. **Create a new branch:**
```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes:**
- Follow the existing code style
- Add tests for new functionality
- Update documentation as needed

3. **Test your changes:**
```bash
python -m pytest  # Run tests
python -m black src/  # Format code
python -m flake8 src/  # Lint code
```

4. **Commit and push:**
```bash
git add .
git commit -m "feat: add your feature description"
git push origin feature/your-feature-name
```

5. **Create a Pull Request:**
- Use clear, descriptive titles
- Include a detailed description of changes
- Reference related issues

## 🏗️ Architecture Guidelines

### Code Organization
```
src/franklinops/
├── server.py              # FastAPI server and UI endpoints
├── opsdb.py               # Database operations
├── {module}_spokes.py     # Business automation modules
├── integrations/          # External system integrations
└── core modules...        # Supporting functionality
```

### Key Design Principles

1. **Local-First**: Sensitive data stays on user's machine
2. **Human-in-the-Loop**: Always require approval for high-risk actions
3. **Audit Everything**: Complete trail of all automated actions
4. **Graceful Degradation**: System works even when external services fail
5. **Progressive Automation**: Shadow → Assist → Autopilot

### Adding New Spokes (Automation Modules)

New business automation modules should follow this pattern:

```python
class NewSpokes:
    def __init__(self, db: OpsDB, audit: AuditLogger, approvals: ApprovalService):
        self.db = db
        self.audit = audit
        self.approvals = approvals
    
    def process_automation(self, context: dict) -> dict:
        # 1. Detect work to be done
        # 2. Request approval if needed
        # 3. Execute approved actions
        # 4. Log all activities to audit
        # 5. Return results with metrics
        pass
```

### Database Schema Extensions

When adding new database tables:

1. **Update `opsdb.py`** with new table definitions
2. **Add migration logic** for existing databases
3. **Include audit trail** columns where appropriate
4. **Test with existing data**

## 🧪 Testing Guidelines

### Test Structure
```
tests/
├── unit/           # Unit tests for individual modules
├── integration/    # Integration tests across modules
└── end_to_end/    # Full system workflow tests
```

### Writing Tests

- **Unit tests**: Test individual functions in isolation
- **Integration tests**: Test module interactions
- **Mock external services**: Don't rely on external APIs in tests
- **Test edge cases**: Handle errors gracefully

### Running Tests
```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src/franklinops

# Run specific test file
python -m pytest tests/unit/test_sales_spokes.py
```

## 📋 Code Style

### Python Style Guide
- Follow PEP 8 style guidelines
- Use Black for code formatting
- Maximum line length: 100 characters
- Use type hints for all functions
- Document all public functions with docstrings

### Example Function:
```python
def process_invoice(
    self, 
    invoice_data: dict, 
    approval_required: bool = True
) -> dict[str, Any]:
    """
    Process an invoice through the approval workflow.
    
    Args:
        invoice_data: Dictionary containing invoice details
        approval_required: Whether to require human approval
        
    Returns:
        Dictionary with processing results and status
        
    Raises:
        ValueError: If invoice_data is invalid
    """
    # Implementation here
    pass
```

### Commit Message Format
```
type: brief description

More detailed explanation if needed.

- Bullet points for specific changes
- Reference issues: Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## 🔍 Code Review Process

### What We Look For
- **Functionality**: Does it work as intended?
- **Architecture**: Fits with existing design patterns?
- **Security**: No sensitive data exposure?
- **Performance**: Efficient database queries and operations?
- **Testing**: Adequate test coverage?
- **Documentation**: Clear and up-to-date?

### Review Checklist
- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New functionality is tested
- [ ] Documentation is updated
- [ ] No breaking changes without discussion
- [ ] Security considerations addressed

## 🐛 Bug Reports

When reporting bugs, please include:

- **FranklinOps version**
- **Operating system and version**
- **Python version**
- **Steps to reproduce**
- **Expected vs actual behavior**
- **Error messages or logs**
- **Configuration details** (without sensitive info)

## 💡 Feature Requests

When proposing features:

- **Use case**: Why is this needed?
- **Business value**: How does it help users?
- **Implementation ideas**: Technical approach
- **Alternatives considered**: Other ways to solve the problem
- **Breaking changes**: Any compatibility impacts?

## 🤝 Community Guidelines

- **Be respectful**: Treat everyone with kindness and respect
- **Be constructive**: Provide helpful feedback and suggestions
- **Be collaborative**: Work together to improve FranklinOps
- **Be patient**: Reviews and discussions take time
- **Have fun**: Enjoy building amazing automation tools!

## 📞 Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and community chat
- **Documentation**: Check existing docs first
- **Code Review**: Ask for feedback during development

## 🏆 Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes for significant contributions
- Special thanks in project announcements

## 📄 License

By contributing to FranklinOps, you agree that your contributions will be licensed under the same license as the project (MIT License).

---

**Ready to contribute? We're excited to see what you'll build!** 🚀

Thank you for helping make FranklinOps the pinnacle of user-friendly business automation!