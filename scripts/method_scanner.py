#!/usr/bin/env python3
"""Method scanner to identify potential method mismatches during refactors."""

import argparse
import ast
from pathlib import Path


def extract_method_calls(file_path: Path) -> set[str]:
    """Extract all method calls from a Python file."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)

        methods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                methods.add(node.func.attr)

        return methods
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}")
        return set()


def extract_method_definitions(file_path: Path) -> set[str]:
    """Extract all method definitions from a Python file."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)

        methods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                methods.add(node.name)

        return methods
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}")
        return set()


def scan_directory(directory: Path) -> dict[str, dict[str, set[str]]]:
    """Scan directory for method calls and definitions."""
    results = {}

    for py_file in directory.glob("**/*.py"):
        if py_file.name.startswith("__"):
            continue

        results[str(py_file.relative_to(directory))] = {
            "calls": extract_method_calls(py_file),
            "definitions": extract_method_definitions(py_file),
        }

    return results


def find_orphaned_calls(scan_results: dict[str, dict[str, set[str]]]) -> list[str]:
    """Find method calls that don't have corresponding definitions."""
    all_calls = set()
    all_definitions = set()

    for file_data in scan_results.values():
        all_calls.update(file_data["calls"])
        all_definitions.update(file_data["definitions"])

    orphaned = []
    for call in all_calls:
        if call.startswith(("get_", "send_", "set_")) and call not in all_definitions:
            orphaned.append(call)

    return sorted(orphaned)


def compare_scans(before: dict, after: dict) -> dict[str, list[str]]:
    """Compare two scan results to identify changes."""
    changes = {"removed_methods": [], "added_methods": [], "files_with_changes": []}

    before_all = set()
    after_all = set()

    for file_data in before.values():
        before_all.update(file_data["definitions"])

    for file_data in after.values():
        after_all.update(file_data["definitions"])

    changes["removed_methods"] = sorted(before_all - after_all)
    changes["added_methods"] = sorted(after_all - before_all)

    return changes


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Scan for method call/definition mismatches")
    parser.add_argument("directory", help="Directory to scan")
    parser.add_argument("--check-orphans", action="store_true", help="Check for orphaned method calls")
    parser.add_argument("--api-methods", help="File containing API method list")

    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory {directory} does not exist")
        return 1

    print(f"🔍 Scanning {directory} for method usage...")
    scan_results = scan_directory(directory)

    if args.check_orphans:
        print("\n📞 Checking for orphaned method calls...")
        orphaned = find_orphaned_calls(scan_results)

        if orphaned:
            print("⚠️  Found potentially orphaned method calls:")
            for method in orphaned:
                print(f"  - {method}")

                # Find which files use this method
                for file_path, data in scan_results.items():
                    if method in data["calls"]:
                        print(f"    Used in: {file_path}")
        else:
            print("✅ No orphaned method calls found")

    if args.api_methods:
        api_file = Path(args.api_methods)
        if api_file.exists():
            api_methods = set(api_file.read_text().strip().split("\n"))

            print(f"\n🔗 Checking against API methods from {api_file}...")

            all_calls = set()
            for file_data in scan_results.values():
                all_calls.update(file_data["calls"])

            missing_methods = []
            for call in all_calls:
                if call.startswith(("get_", "send_")) and call not in api_methods:
                    missing_methods.append(call)

            if missing_methods:
                print("❌ Method calls not found in API:")
                for method in sorted(missing_methods):
                    print(f"  - {method}")
            else:
                print("✅ All API method calls are valid")

    return 0


if __name__ == "__main__":
    exit(main())
