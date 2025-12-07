# Documentation Index

## For Developers

### Architecture & Design

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** ⭐ START HERE

   - Complete architecture overview
   - Component responsibilities
   - Data flow
   - Project structure
   - Code patterns
   - Decision log

2. **[DEVELOPMENT-RULES.md](DEVELOPMENT-RULES.md)**

   - Non-negotiable rules
   - Golden rules
   - Code quality standards
   - Documentation guidelines
   - Mental checklist
   - PR checklist

3. **[TESTING-CONSOLIDATED.md](TESTING-CONSOLIDATED.md)**

   - Complete testing strategy
   - 4-tier test approach
   - Test directory structure
   - Testing workflow
   - Test requirements
   - Running tests

### Quick References

- **[bug-fix-testing-checklist.md](bug-fix-testing-checklist.md)**: Bug fix workflow

## For Users

- **[README.md](README.md)**: Quick start guide
- **[user-guide.md](user-guide.md)**: Complete user guide
- **[faq-and-troubleshooting.md](faq-and-troubleshooting.md)**: FAQ and troubleshooting
- **[automation-cookbook.md](automation-cookbook.md)**: Automation examples
- **[TTS_GUIDE.md](TTS_GUIDE.md)**: Text-to-speech guide

## Project Structure

```
wiim/
├── custom_components/wiim/    # Integration code (ONLY place to modify)
├── tests/                     # Automated tests (pytest)
├── scripts/                   # Real-device validation tests
├── docs/                      # Documentation (this directory)
└── development/               # Developer guides
```

## Getting Started

### New Developer?

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) - Understand the design
2. Read [DEVELOPMENT-RULES.md](DEVELOPMENT-RULES.md) - Learn the rules
3. Read [TESTING-CONSOLIDATED.md](TESTING-CONSOLIDATED.md) - Understand testing
4. Read [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution workflow

### Fixing a Bug?

1. Read [bug-fix-testing-checklist.md](bug-fix-testing-checklist.md)
2. Write failing test (TDD)
3. Fix the bug
4. Verify test passes
5. Run full test suite

### Adding a Feature?

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) - Understand where it fits
2. Read [DEVELOPMENT-RULES.md](DEVELOPMENT-RULES.md) - Follow the rules
3. Write tests first (TDD)
4. Implement feature
5. Update documentation

## Documentation Standards

### When to Create Documentation

- ✅ Architecture decisions
- ✅ Design patterns
- ✅ Testing strategies
- ✅ User guides
- ❌ Don't create docs without being asked
- ❌ Don't duplicate existing docs

### Documentation Format

- Use Markdown (`.md`)
- Use YYYY.MM.DD format for dated docs
- Use hyphens for multi-word names
- Keep it concise and actionable
