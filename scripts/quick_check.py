#!/usr/bin/env python3
"""Quick refactor dependency checker using grep patterns."""

import subprocess
import sys
from pathlib import Path

# Common patterns that often break during refactors
DANGER_PATTERNS = [
    # Method calls that often get renamed
    (r"\.get_multiroom_info\(", "Potential old multiroom method"),
    (r"\.get_device_status\(", "Potential old status method"),
    (r"\.get_status_ex\(", "Potential old status method"),
    # Import patterns that break
    (r"from.*import.*get_multiroom_info", "Import of potentially renamed method"),
    (r"from.*import.*WiiMDevice", "Import of potentially renamed class"),
    # Mock patterns in tests that need updating
    (r"Mock.*get_multiroom_info", "Test mock of potentially renamed method"),
    (r"patch.*get_multiroom_info", "Test patch of potentially renamed method"),
    # Common typos during refactors
    (r"coordinator\.client\.get_\w*_info\(", "Check if _info methods exist in API"),
    (r"self\.client\.send_\w*\(", "Check if send methods exist in API"),
]


def run_grep(pattern: str, directory: str) -> list[tuple[str, int, str]]:
    """Run grep and return matches."""
    try:
        cmd = ["grep", "-rn", "--include=*.py", pattern, directory]
        result = subprocess.run(cmd, capture_output=True, text=True)

        matches = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    matches.append((parts[0], int(parts[1]), parts[2]))

        return matches
    except Exception:
        return []


def check_import_consistency(directory: Path) -> list[str]:
    """Check for import inconsistencies."""
    issues = []

    # Find all import statements
    for py_file in directory.glob("**/*.py"):
        try:
            content = py_file.read_text()
            lines = content.split("\n")

            for i, line in enumerate(lines, 1):
                if "import" in line:
                    # Check for imports that might be broken
                    if "get_multiroom_info" in line:
                        issues.append(f"{py_file}:{i} - Importing potentially renamed method")
                    elif "WiiMDevice" in line and "WiiMClient" not in line:
                        issues.append(f"{py_file}:{i} - Potential class name mismatch")
        except Exception:
            continue

    return issues


def quick_syntax_check(directory: Path) -> list[str]:
    """Quick syntax validation using Python's compile."""
    issues = []

    for py_file in directory.glob("**/*.py"):
        try:
            with open(py_file) as f:
                compile(f.read(), py_file, "exec")
        except SyntaxError as e:
            issues.append(f"{py_file}:{e.lineno} - Syntax error: {e.msg}")
        except Exception as e:
            issues.append(f"{py_file} - Compilation error: {e}")

    return issues


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python quick_check.py <directory>")
        return 1

    directory = Path(sys.argv[1])
    if not directory.exists():
        print(f"Error: Directory {directory} does not exist")
        return 1

    print(f"🚀 Quick refactor check for {directory}")
    print("=" * 50)

    total_issues = 0

    # 1. Pattern-based checks
    print("\n📋 Checking dangerous patterns...")
    for pattern, description in DANGER_PATTERNS:
        matches = run_grep(pattern, str(directory))
        if matches:
            print(f"\n⚠️  {description}:")
            for file_path, line_num, content in matches:
                print(f"  {file_path}:{line_num} - {content.strip()}")
            total_issues += len(matches)

    # 2. Import consistency
    print("\n📦 Checking import consistency...")
    import_issues = check_import_consistency(directory)
    if import_issues:
        for issue in import_issues:
            print(f"⚠️  {issue}")
        total_issues += len(import_issues)
    else:
        print("✅ No import issues found")

    # 3. Quick syntax check
    print("\n🐍 Quick syntax check...")
    syntax_issues = quick_syntax_check(directory)
    if syntax_issues:
        for issue in syntax_issues:
            print(f"❌ {issue}")
        total_issues += len(syntax_issues)
    else:
        print("✅ No syntax errors found")

    # 4. Summary
    print("\n" + "=" * 50)
    if total_issues == 0:
        print("✅ No issues found - refactor looks good!")
        return 0
    else:
        print(f"⚠️  Found {total_issues} potential issues to review")
        return 1


if __name__ == "__main__":
    exit(main())
