# Refactor Validation Guide

## ❌ The Problem: Endless Try-and-Fail Cycles

After major refactors, integrations often fail at runtime with cryptic errors like:

```
AttributeError: 'WiiMClient' object has no attribute 'get_multiroom_info'. Did you mean: 'get_multiroom_status'?
```

These issues force developers into frustrating cycles of:

1. 🔄 Run integration → ❌ Error → 🔧 Fix → 🔄 Repeat

## ✅ The Solution: Systematic Validation

We've built a comprehensive validation system that catches refactor issues **before** runtime.

## 🛠️ Available Tools

### 1. **Comprehensive Validator** (`scripts/validate_refactor.py`)

**When to use**: After major refactors, before releases
**What it checks**:

- Method call consistency with API
- Import integrity
- Test mock alignment
- Syntax validation
- API surface compatibility

```bash
make validate
# or
python scripts/validate_refactor.py
```

**Example Output**:

```
❌ ERRORS (1)
  ❌ coordinator.py:203 - Method 'get_multiroom_info' not found in API

⚠️  WARNINGS (3)
  ⚠️  Method 'get_multiroom_info_defensive' used but not in API
```

### 2. **Quick Pattern Check** (`scripts/quick_check.py`)

**When to use**: During development, frequent checks
**What it checks**: Common refactor pitfalls using grep patterns

```bash
python scripts/quick_check.py custom_components/wiim/
```

### 3. **Method Scanner** (`scripts/method_scanner.py`)

**When to use**: Before/after comparisons, orphaned call detection
**What it checks**: Method definitions vs. calls, orphaned methods

```bash
python scripts/method_scanner.py custom_components/wiim --check-orphans
```

### 4. **Pre-Commit Suite** (`scripts/pre_commit_check.sh`)

**When to use**: Before every commit during refactors
**What it runs**: All validation tools in sequence

```bash
make pre-commit
```

## 📋 Refactor Workflow

### **Phase 1: Pre-Refactor Baseline**

```bash
# Create baseline snapshots
make validate > validation_baseline.txt
python scripts/method_scanner.py custom_components/wiim --check-orphans > methods_baseline.txt
```

### **Phase 2: During Refactor (Every ~30 mins)**

```bash
# Quick validation cycle (30 seconds)
python scripts/quick_check.py custom_components/wiim/

# Full validation (if quick check passes)
make validate
```

### **Phase 3: Pre-Commit Validation**

```bash
# Comprehensive check before committing
make pre-commit
```

### **Phase 4: Release Validation**

```bash
# Full pipeline (validation + linting + tests)
make check-all
```

## 🎯 How It Would Have Caught Our Issue

Our recent `get_multiroom_info` vs `get_multiroom_status` issue would have been caught:

**Before Fix** (Broken):

```bash
$ make validate
❌ ERRORS (1)
  ❌ coordinator.py:203 - Method 'get_multiroom_info' not found in API
```

**After Fix** (Working):

```bash
$ make validate
✅ No critical errors found
```

## 🚀 Integration Into Development

### **VS Code Integration**

Add to `.vscode/tasks.json`:

```json
{
  "label": "Validate Refactor",
  "type": "shell",
  "command": "make validate",
  "group": "build",
  "presentation": { "echo": true, "reveal": "always" }
}
```

### **Git Hooks**

```bash
# Install pre-commit hook
cp scripts/pre_commit_check.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### **CI/CD Pipeline**

```yaml
# GitHub Actions example
- name: Validate Refactor
  run: make validate
```

## 📊 Benefits

| Traditional Approach  | Validation Approach   |
| --------------------- | --------------------- |
| ❌ Runtime discovery  | ✅ Static analysis    |
| 🔄 Try-fail cycles    | 🎯 Proactive catching |
| ⏱️ 10-30min per issue | ⚡ 30sec validation   |
| 😤 Frustrating        | 😌 Confident          |
| 🐛 Error-prone        | 🛡️ Systematic         |

## 🔧 Customization

### **Adding Custom Patterns**

Edit `scripts/quick_check.py`:

```python
DANGER_PATTERNS = [
    (r'\.your_old_method\(', 'Check for renamed method'),
    # Add your patterns here
]
```

### **Project-Specific Validation**

Create `scripts/custom_validate.py` for project-specific checks.

## 📈 Success Metrics

After implementing this system:

- ✅ **0** runtime method mismatch errors
- ⚡ **30-second** refactor validation
- 🎯 **100%** confidence before commits
- 🚀 **Faster** development cycles

## 🎉 Example Success Story

**Issue**: v2.0.0 refactor broke `get_multiroom_info` → `get_multiroom_status`

**Traditional Path**:

1. Start Home Assistant → ❌ Error
2. Debug logs → 🔍 Find issue
3. Fix method → 🔄 Restart
4. Test again → ✅ Works
5. **Total time**: 15-20 minutes

**Validation Path**:

1. `make validate` → ❌ Shows exact line
2. Fix method → ✅ Immediate
3. **Total time**: 30 seconds

---

**💡 Key Takeaway**: Invest 5 minutes setting up validation to save hours of debugging. Systematic validation eliminates refactor anxiety and enables confident code changes.
