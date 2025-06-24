#!/usr/bin/env python3
"""Refactor validation script to catch method mismatches and API inconsistencies."""

import ast
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class RefactorValidator:
    """Validates refactored code for common issues."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.custom_components_path = base_path / "custom_components" / "wiim"
        self.tests_path = base_path / "tests"
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_all(self) -> bool:
        """Run all validation checks."""
        print(f"{BLUE}🔍 Running Refactor Validation...{RESET}")

        success = True
        success &= self.validate_method_calls()
        success &= self.validate_imports()
        success &= self.validate_api_consistency()
        success &= self.validate_test_mocks()
        success &= self.check_syntax()

        self.print_summary()
        return success

    def validate_method_calls(self) -> bool:
        """Check for method calls that might not exist."""
        print(f"\n{YELLOW}📞 Validating method calls...{RESET}")

        # Extract actual API methods from the client
        api_methods = self._get_api_methods()
        print(f"Found {len(api_methods)} API methods")

        # Extract internal methods from coordinator
        coordinator_methods = self._get_coordinator_methods()
        print(f"Found {len(coordinator_methods)} coordinator methods")

        # Find all method calls in the codebase
        method_calls = self._find_method_calls()

        success = True
        for file_path, calls in method_calls.items():
            for call_info in calls:
                method_name = call_info["method"]
                call_type = call_info["type"]

                if call_type == "client_call" and method_name.startswith(("get_", "send_")):
                    if method_name not in api_methods:
                        self.errors.append(f"❌ {file_path}:{call_info['line']} - API method '{method_name}' not found")
                        success = False
                    else:
                        print(f"✅ {method_name} (API) - OK")

                elif call_type == "coordinator_call" and method_name.startswith("_get_"):
                    if method_name not in coordinator_methods:
                        self.errors.append(
                            f"❌ {file_path}:{call_info['line']} - Coordinator method '{method_name}' not found"
                        )
                        success = False
                    else:
                        print(f"✅ {method_name} (coordinator) - OK")

        return success

    def validate_imports(self) -> bool:
        """Test that all modules can be imported."""
        print(f"\n{YELLOW}📦 Validating imports...{RESET}")

        success = True
        python_files = list(self.custom_components_path.glob("*.py"))

        for py_file in python_files:
            if py_file.name.startswith("__"):
                continue

            try:
                # Add the parent directory to sys.path temporarily
                sys.path.insert(0, str(self.base_path))

                module_name = f"custom_components.wiim.{py_file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    print(f"✅ {py_file.name} - imports OK")
                else:
                    self.errors.append(f"❌ Failed to create spec for {py_file.name}")
                    success = False

            except Exception as e:
                self.errors.append(f"❌ Import error in {py_file.name}: {e}")
                success = False
            finally:
                if str(self.base_path) in sys.path:
                    sys.path.remove(str(self.base_path))

        return success

    def validate_api_consistency(self) -> bool:
        """Check API method consistency between modules."""
        print(f"\n{YELLOW}🔗 Validating API consistency...{RESET}")

        # Check for common method name patterns that might be inconsistent
        patterns_to_check = [
            (r"get_multiroom_\w+", "multiroom methods"),
            (r"get_eq_\w+", "EQ methods"),
            (r"get_preset\w*", "preset methods"),
            (r"send_\w+", "send methods"),
        ]

        success = True
        all_files = list(self.custom_components_path.glob("*.py"))

        for pattern, description in patterns_to_check:
            methods_found = set()

            for py_file in all_files:
                content = py_file.read_text()
                matches = re.findall(pattern, content)
                methods_found.update(matches)

            if methods_found:
                print(f"Found {description}: {sorted(methods_found)}")

                # Validate these methods exist in API
                api_methods = self._get_api_methods()
                for method in methods_found:
                    # Skip internal helper methods that aren't supposed to be in the API
                    if method in ["send_volume_debounced"]:
                        continue

                    if method not in api_methods:
                        self.warnings.append(f"⚠️  Method '{method}' used but not in API")

        return success

    def validate_test_mocks(self) -> bool:
        """Check that test mocks match actual API methods."""
        print(f"\n{YELLOW}🧪 Validating test mocks...{RESET}")

        api_methods = self._get_api_methods()
        success = True

        test_files = list(self.tests_path.glob("**/*.py"))

        for test_file in test_files:
            content = test_file.read_text()

            # Find mock method assignments like client.method_name =
            mock_patterns = [
                r"client\.(\w+)\s*=.*Mock",
                r"client\.(\w+)\.return_value",
                r'"custom_components\.wiim\.api\.WiiMClient\.(\w+)"',
            ]

            for pattern in mock_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if match.startswith("get_") and match not in api_methods:
                        self.errors.append(f"❌ {test_file.name} - Mock method '{match}' doesn't exist in API")
                        success = False

        return success

    def check_syntax(self) -> bool:
        """Check Python syntax for all files."""
        print(f"\n{YELLOW}🐍 Checking syntax...{RESET}")

        success = True
        python_files = list(self.custom_components_path.glob("*.py"))

        for py_file in python_files:
            try:
                with open(py_file) as f:
                    ast.parse(f.read(), filename=str(py_file))
                print(f"✅ {py_file.name} - syntax OK")
            except SyntaxError as e:
                self.errors.append(f"❌ Syntax error in {py_file.name}: {e}")
                success = False

        return success

    def _get_api_methods(self) -> set[str]:
        """Extract all methods from the WiiM API client."""
        try:
            sys.path.insert(0, str(self.base_path))
            from custom_components.wiim.api import WiiMClient

            methods = set()
            for name in dir(WiiMClient):
                if not name.startswith("_"):
                    attr = getattr(WiiMClient, name)
                    if callable(attr):
                        methods.add(name)

            return methods
        except Exception as e:
            self.warnings.append(f"⚠️  Could not load API methods: {e}")
            return set()
        finally:
            if str(self.base_path) in sys.path:
                sys.path.remove(str(self.base_path))

    def _get_coordinator_methods(self) -> set[str]:
        """Extract all methods from the WiiM coordinator."""
        try:
            coordinator_file = self.custom_components_path / "coordinator.py"
            if not coordinator_file.exists():
                return set()

            content = coordinator_file.read_text()
            tree = ast.parse(content)

            methods = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    methods.add(node.name)

            return methods
        except Exception as e:
            self.warnings.append(f"⚠️  Could not load coordinator methods: {e}")
            return set()

    def _find_method_calls(self) -> dict[str, list[dict[str, Any]]]:
        """Find all method calls in Python files."""
        method_calls = {}

        python_files = list(self.custom_components_path.glob("*.py"))

        for py_file in python_files:
            try:
                content = py_file.read_text()
                tree = ast.parse(content)

                calls = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            # Look for self.client.method_name() or client.method_name()
                            if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "client":
                                calls.append({"method": node.func.attr, "line": node.lineno, "type": "client_call"})
                            # NEW: Look for coordinator.method_name() or self.method_name()
                            elif isinstance(node.func.value, ast.Name) and node.func.value.id == "coordinator":
                                calls.append(
                                    {"method": node.func.attr, "line": node.lineno, "type": "coordinator_call"}
                                )
                            elif isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "self":
                                calls.append({"method": node.func.attr, "line": node.lineno, "type": "self_call"})

                if calls:
                    method_calls[py_file.name] = calls

            except Exception as e:
                self.warnings.append(f"⚠️  Could not parse {py_file.name}: {e}")

        return method_calls

    def print_summary(self):
        """Print validation summary."""
        print(f"\n{BLUE}📋 Validation Summary{RESET}")
        print("=" * 50)

        if self.errors:
            print(f"\n{RED}❌ ERRORS ({len(self.errors)}){RESET}")
            for error in self.errors:
                print(f"  {error}")

        if self.warnings:
            print(f"\n{YELLOW}⚠️  WARNINGS ({len(self.warnings)}){RESET}")
            for warning in self.warnings:
                print(f"  {warning}")

        if not self.errors and not self.warnings:
            print(f"\n{GREEN}✅ All checks passed!{RESET}")
        elif not self.errors:
            print(f"\n{GREEN}✅ No critical errors found{RESET}")
        else:
            print(f"\n{RED}❌ {len(self.errors)} critical errors found{RESET}")


def main():
    """Main entry point."""
    base_path = Path(__file__).parent.parent
    validator = RefactorValidator(base_path)

    success = validator.validate_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
