#!/usr/bin/env python3
"""
WiiM Integration Test Runner

Runs unit tests for the WiiM integration.
This replaces the old phase-based validation tests with proper pytest-based testing.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


# Colors for output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text: str, color: str = Colors.CYAN) -> None:
    """Print a colored header."""
    print(f"\n{color}{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{color}{Colors.BOLD}{text.center(60)}{Colors.END}")
    print(f"{color}{Colors.BOLD}{'=' * 60}{Colors.END}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print_info(f"Running: {description}")
    print(f"{Colors.WHITE}Command: {' '.join(cmd)}{Colors.END}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            print_success(f"{description} passed")
            if result.stdout.strip():
                print(f"{Colors.WHITE}{result.stdout}{Colors.END}")
            return True
        else:
            print_error(f"{description} failed")
            if result.stdout.strip():
                print(f"{Colors.WHITE}STDOUT:\n{result.stdout}{Colors.END}")
            if result.stderr.strip():
                print(f"{Colors.RED}STDERR:\n{result.stderr}{Colors.END}")
            return False

    except FileNotFoundError as e:
        print_error(f"Command not found: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error running {description}: {e}")
        return False


def get_python_executable() -> str:
    """Get the Python executable path."""
    return sys.executable


def run_unit_tests(verbose: bool = False) -> bool:
    """Run unit tests."""
    print_header("Running Unit Tests", Colors.GREEN)

    cmd = [
        get_python_executable(),
        "-m",
        "pytest",
        "tests/unit/",
        "-v" if verbose else "-q",
        "--tb=short",
        "-x",  # Stop on first failure for faster feedback
    ]

    return run_command(cmd, "Unit tests")


def run_specific_test_file(test_file: str, verbose: bool = False) -> bool:
    """Run a specific test file."""
    print_header(f"Running {test_file}", Colors.YELLOW)

    cmd = [
        get_python_executable(),
        "-m",
        "pytest",
        test_file,
        "-v" if verbose else "-q",
        "--tb=short",
    ]

    return run_command(cmd, f"Test file: {test_file}")


def run_linting() -> bool:
    """Run linting checks."""
    print_header("Running Linting Checks", Colors.CYAN)

    # Check if ruff is available
    try:
        subprocess.run(
            [get_python_executable(), "-m", "ruff", "--version"],
            capture_output=True,
            check=True,
        )
        has_ruff = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        has_ruff = False

    success = True

    if has_ruff:
        # Run ruff linting
        cmd = [
            get_python_executable(),
            "-m",
            "ruff",
            "check",
            "custom_components/wiim/",
        ]
        if not run_command(cmd, "Ruff linting"):
            success = False
    else:
        print_warning("Ruff not available, skipping style checks")

    # MyPy removed - not needed for HA integrations
    # Focus on Ruff for style and unit tests for functionality

    return success


def run_all_tests(verbose: bool = False) -> bool:
    """Run all tests."""
    print_header("WiiM Integration - Full Test Suite", Colors.BOLD)

    results = []

    # Run unit tests
    results.append(("Unit Tests", run_unit_tests(verbose)))

    # Run linting
    results.append(("Linting", run_linting()))

    # Print summary
    print_header("Test Results Summary", Colors.WHITE)

    passed = 0
    total = len(results)

    for test_name, success in results:
        if success:
            print_success(f"{test_name}")
            passed += 1
        else:
            print_error(f"{test_name}")

    print(f"\n{Colors.BOLD}Results: {passed}/{total} test suites passed{Colors.END}")

    if passed == total:
        print_success("🎉 All tests passed! WiiM integration is production-ready.")
        print_info("Testing approach: Unit tests for integration glue code + code style checks")
        return True
    else:
        print_error("❌ Some tests failed. Please fix issues before deployment.")
        return False


def show_test_structure() -> None:
    """Show the test directory structure."""
    print_header("WiiM Test Structure", Colors.CYAN)

    test_dir = Path("tests")
    if not test_dir.exists():
        print_error("Tests directory not found!")
        return

    def print_tree(path: Path, prefix: str = "") -> None:
        """Print directory tree."""
        if path.is_file() and path.suffix == ".py":
            print(f"{prefix}📄 {path.name}")
        elif path.is_dir():
            print(f"{prefix}📁 {path.name}/")
            children = sorted(path.iterdir())
            for i, child in enumerate(children):
                is_last = i == len(children) - 1
                new_prefix = prefix + ("    " if is_last else "│   ")
                print_tree(child, new_prefix)

    print_tree(test_dir)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WiiM Unit Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/run_tests.py                    # Run all tests
  python tests/run_tests.py --unit            # Run only unit tests
  python tests/run_tests.py --lint            # Run only linting
  python tests/run_tests.py --file tests/unit/test_data.py  # Run specific file
  python tests/run_tests.py --verbose         # Verbose output
  python tests/run_tests.py --structure       # Show test structure
        """,
    )

    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--lint", action="store_true", help="Run linting only")
    parser.add_argument("--file", type=str, help="Run specific test file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--structure", action="store_true", help="Show test structure")

    args = parser.parse_args()

    # Change to the correct directory
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)

    if args.structure:
        show_test_structure()
        return

    success = True

    if args.unit:
        success = run_unit_tests(args.verbose)
    elif args.lint:
        success = run_linting()
    elif args.file:
        success = run_specific_test_file(args.file, args.verbose)
    else:
        success = run_all_tests(args.verbose)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
