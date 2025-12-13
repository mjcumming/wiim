# GitHub Actions Constraints File - CRITICAL DOCUMENTATION

## ⚠️ READ THIS BEFORE MODIFYING constraints.txt

This file documents the **painful lessons learned** about managing dependencies for Home Assistant custom component testing.

---

## The Problem

`pytest-homeassistant-custom-component` has **VERY specific version requirements** for ALL pytest-related packages. If you specify ANY conflicting version in `requirements_test.txt` or `constraints.txt`, pip will fail with dependency conflicts.

---

## The Solution

### 1. **requirements_test.txt** - Keep it MINIMAL

```text
-r requirements_dev.txt

# ONLY specify pytest-homeassistant-custom-component
# DO NOT list pytest, pytest-asyncio, pytest-cov, pytest-timeout, pytest-xdist
# These will all be pulled in by pytest-homeassistant-custom-component
pytest-homeassistant-custom-component>=0.12.0

# Test utilities (not pytest-related)
aresponses>=2.1.6
freezegun>=1.2.2
zeroconf

# Code quality
flake8>=6.0.0
ruff>=0.4.2
```

### 2. **constraints.txt** - Match pytest-homeassistant-custom-component EXACTLY

The constraint file must use the EXACT versions that `pytest-homeassistant-custom-component` requires.

**How to find the correct versions:**

1. Go to: https://github.com/MatthewFlamm/pytest-homeassistant-custom-component
2. Check the version you're using (currently 0.13.251)
3. Look at `setup.py` or `pyproject.toml` for EXACT version pins
4. Copy those EXACT versions to `constraints.txt`

**Example for 0.13.251:**

```text
pytest-homeassistant-custom-component==0.13.251
pytest==8.3.5                    # ← MUST match exactly!
pytest-cov==6.0.0                # ← MUST match exactly!
coverage==7.6.12                 # ← MUST match exactly!
pytest-asyncio==0.26.0           # ← Pulled in automatically, don't override
pytest-timeout==2.3.1            # ← Pulled in automatically, don't override
pytest-xdist==3.6.1              # ← Pulled in automatically, don't override
```

---

## What Went Wrong (Learn from our mistakes)

### Mistake 1: Listing pytest plugins explicitly

❌ **WRONG:**

```text
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-timeout>=2.1.0
pytest-xdist>=3.0.0
pytest-homeassistant-custom-component>=0.12.0
```

✅ **CORRECT:**

```text
pytest-homeassistant-custom-component>=0.12.0
# All pytest plugins pulled in automatically
```

### Mistake 2: Wrong pytest version in constraints

❌ **WRONG:**

```text
pytest-homeassistant-custom-component==0.13.251
pytest==8.4.2  # ← Conflicts! Should be 8.3.5
```

✅ **CORRECT:**

```text
pytest-homeassistant-custom-component==0.13.251
pytest==8.3.5  # ← Matches exactly what it requires
```

### Mistake 3: Including homeassistant in requirements_dev.txt

❌ **WRONG:**

```text
homeassistant>=2024.12.0  # Causes version conflicts
```

✅ **CORRECT:**

```text
# NO homeassistant dependency needed
# pytest-homeassistant-custom-component provides all test fixtures
```

---

## Dependency Conflicts We Encountered

1. **pytest version conflict**: constraints had 8.4.2, but pytest-homeassistant-custom-component needs 8.3.5
2. **pytest-asyncio conflict**: Explicitly listed >=0.21.0, but pytest-homeassistant-custom-component needs ==0.26.0
3. **pytest-timeout conflict**: Explicitly listed >=2.1.0, but pytest-homeassistant-custom-component needs ==2.3.1
4. **pytest-xdist conflict**: Explicitly listed >=3.0.0, but pytest-homeassistant-custom-component needs ==3.6.1
5. **coverage conflict**: pytest-cov wanted >=7.10.6, but pytest-homeassistant-custom-component needs ==7.6.12
6. **homeassistant conflict**: Caused aiohttp/multidict version conflicts
7. **pycares conflict**: Python 3.13 compatibility issue, needed ==4.4.0 with aiodns==3.2.0

---

## When to Update constraints.txt

**ONLY when pytest-homeassistant-custom-component is updated!**

1. Update pytest-homeassistant-custom-component version in `requirements_test.txt`
2. Check its repository for new dependency versions
3. Update constraints.txt to match EXACTLY
4. Test locally with: `pip install -c .github/workflows/constraints.txt -r requirements_test.txt`
5. Verify tests pass: `pytest tests/unit/`
6. Push and verify CI passes

---

## Testing Locally Before Push

```bash
# Clean environment
pip uninstall pytest pytest-asyncio pytest-cov pytest-timeout pytest-xdist -y

# Install with constraints
pip install -c .github/workflows/constraints.txt -r requirements_test.txt

# Verify versions
pip show pytest pytest-homeassistant-custom-component pytest-asyncio pytest-cov

# Run tests
pytest tests/unit/ -v
```

---

## Quick Reference

| Package                               | Version (for 0.13.251) | Notes              |
| ------------------------------------- | ---------------------- | ------------------ |
| pytest-homeassistant-custom-component | 0.13.251               | Pin this version   |
| pytest                                | 8.3.5                  | MUST match exactly |
| pytest-cov                            | 6.0.0                  | MUST match exactly |
| coverage                              | 7.6.12                 | MUST match exactly |
| pytest-asyncio                        | 0.26.0                 | Auto-installed     |
| pytest-timeout                        | 2.3.1                  | Auto-installed     |
| pytest-xdist                          | 3.6.1                  | Auto-installed     |
| pycares                               | 4.4.0                  | Python 3.13 fix    |
| aiodns                                | 3.2.0                  | Python 3.13 fix    |

---

## The Golden Rule

**Let pytest-homeassistant-custom-component manage ALL pytest-related dependencies.**

**DO NOT:**

- ❌ List pytest plugins in requirements_test.txt
- ❌ Override pytest versions in constraints.txt without checking pytest-homeassistant-custom-component
- ❌ Include homeassistant in requirements_dev.txt

**DO:**

- ✅ Only specify pytest-homeassistant-custom-component in requirements_test.txt
- ✅ Match EXACT versions in constraints.txt
- ✅ Test locally before pushing
- ✅ Update this documentation when you learn something new

---

## Last Updated

- Date: 2025-12-13
- pytest-homeassistant-custom-component version: 0.13.251
- Updated by: Fixing dependency hell after release workflow failures

---

## If CI Still Fails

1. Check the error message for version conflicts
2. Look up what pytest-homeassistant-custom-component ACTUALLY requires
3. Update constraints.txt to match
4. **DO NOT** add more packages to requirements - simplify instead!
5. Document what you learned in this file
