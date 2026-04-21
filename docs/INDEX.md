# Documentation Index

## For Developers

### Architecture & Design

1. **[DEVELOPMENT-RULES.md](DEVELOPMENT-RULES.md)** ⭐ **Rules map first**

   - **[Rules map (read this first)](DEVELOPMENT-RULES.md#rules-map-read-this-first)** — what the integration does, how it works, pywiim, collaboration, contracts, ADRs
   - Non-negotiables, golden rules, Rule 8 (ADRs), PR checklist, doc standards
   - **AI / Cursor seed:** [`.cursor/rules/wiim-project.mdc`](../.cursor/rules/wiim-project.mdc) (always on) and root [`AGENTS.md`](../AGENTS.md)

2. **[ARCHITECTURE.md](ARCHITECTURE.md)** — Structure and patterns

   - Component responsibilities, data flow, project layout, decision log index

3. **[adr/README.md](adr/README.md)** — Architecture Decision Records (ADRs)

   - Numbered decisions; [template](adr/0000-template.md)

4. **[TESTING-CONSOLIDATED.md](TESTING-CONSOLIDATED.md)**

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

1. Read [DEVELOPMENT-RULES.md — Rules map](DEVELOPMENT-RULES.md#rules-map-read-this-first) - What this is, pywiim, contracts, ADRs
2. Read [ARCHITECTURE.md](ARCHITECTURE.md) - Structure and data flow
3. Read [DEVELOPMENT-RULES.md](DEVELOPMENT-RULES.md) in full - Rules and checklists
4. Read [TESTING-CONSOLIDATED.md](TESTING-CONSOLIDATED.md) - Understand testing
5. Read [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution workflow

### Fixing a Bug?

1. Skim [Rules map](DEVELOPMENT-RULES.md#rules-map-read-this-first) if new to the repo
2. Read [bug-fix-testing-checklist.md](bug-fix-testing-checklist.md)
3. Write failing test (TDD)
4. Fix the bug
5. Verify test passes
6. Run full test suite

### Adding a Feature?

1. Read [Rules map](DEVELOPMENT-RULES.md#rules-map-read-this-first) and [ARCHITECTURE.md](ARCHITECTURE.md) - Where it fits
2. Read [DEVELOPMENT-RULES.md](DEVELOPMENT-RULES.md) - Follow the rules (including Rule 8 if needed)
3. Write tests first (TDD)
4. Implement feature
5. Update documentation

## Documentation Standards

### When to Create Documentation

- ✅ Architecture decisions ([adr/](adr/README.md) for durable ADRs)
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
