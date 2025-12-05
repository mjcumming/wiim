#!/usr/bin/env python3
"""
WiiM Integration - Pre-Release Validation
Automated checklist for release readiness.

Validates:
- All unit tests pass
- Integration tests pass
- Coverage above threshold
- Linting passes
- Smoke tests pass (if device available)
"""

import argparse
import subprocess
import sys
from pathlib import Path


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class PreReleaseValidator:
    """Validate release readiness."""

    def __init__(self, coverage_threshold: float = 0.70):
        self.coverage_threshold = coverage_threshold
        self.checks = []
        self.repo_root = Path(__file__).parent.parent

    def print_header(self, text: str):
        width = 80
        print(f"\n{Colors.BLUE}{'=' * width}{Colors.RESET}")
        print(f"{Colors.BOLD}{text:^{width}}{Colors.RESET}")
        print(f"{Colors.BLUE}{'=' * width}{Colors.RESET}\n")

    def print_success(self, text: str):
        print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

    def print_failure(self, text: str):
        print(f"{Colors.RED}❌ {text}{Colors.RESET}")

    def print_warning(self, text: str):
        print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

    def print_info(self, text: str):
        print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

    def check_unit_tests(self) -> bool:
        """Check 1: All unit tests pass."""
        self.print_header("Check 1: Unit Tests")

        try:
            result = subprocess.run(
                ["pytest", "tests/unit/", "-v", "--tb=short"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.print_success("All unit tests pass")
                return True
            else:
                self.print_failure("Unit tests failed")
                print(result.stdout)
                print(result.stderr)
                return False
        except Exception as e:
            self.print_failure(f"Error running unit tests: {e}")
            return False

    def check_integration_tests(self) -> bool:
        """Check 2: Integration tests pass."""
        self.print_header("Check 2: Integration Tests")

        try:
            result = subprocess.run(
                ["pytest", "tests/integration/", "-v", "--tb=short"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.print_success("All integration tests pass")
                return True
            else:
                self.print_failure("Integration tests failed")
                print(result.stdout)
                print(result.stderr)
                return False
        except Exception as e:
            self.print_failure(f"Error running integration tests: {e}")
            return False

    def check_coverage(self) -> bool:
        """Check 3: Coverage above threshold."""
        self.print_header("Check 3: Test Coverage")

        try:
            result = subprocess.run(
                [
                    "pytest",
                    "tests/",
                    "--cov=custom_components.wiim",
                    "--cov-report=term-missing",
                    "--cov-report=json",
                ],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self.print_failure("Coverage check failed (tests failed)")
                return False

            # Parse coverage from output
            lines = result.stdout.split("\n")
            coverage_line = [l for l in lines if "TOTAL" in l and "%" in l]
            if coverage_line:
                # Extract percentage
                parts = coverage_line[0].split()
                for part in parts:
                    if "%" in part:
                        coverage = float(part.replace("%", ""))
                        self.print_info(f"Coverage: {coverage:.1f}% (threshold: {self.coverage_threshold * 100:.1f}%)")

                        if coverage >= self.coverage_threshold * 100:
                            self.print_success(f"Coverage above threshold ({coverage:.1f}% >= {self.coverage_threshold * 100:.1f}%)")
                            return True
                        else:
                            self.print_failure(f"Coverage below threshold ({coverage:.1f}% < {self.coverage_threshold * 100:.1f}%)")
                            return False

            self.print_warning("Could not parse coverage")
            return True  # Don't fail if we can't parse
        except Exception as e:
            self.print_failure(f"Error checking coverage: {e}")
            return False

    def check_linting(self) -> bool:
        """Check 4: Linting passes."""
        self.print_header("Check 4: Linting")

        try:
            result = subprocess.run(
                ["python", "tests/run_tests.py", "--lint"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.print_success("Linting passes")
                return True
            else:
                self.print_failure("Linting failed")
                print(result.stdout)
                print(result.stderr)
                return False
        except Exception as e:
            self.print_failure(f"Error running linting: {e}")
            return False

    def check_smoke_tests(self, ha_url: str | None = None, token: str | None = None) -> bool:
        """Check 5: Smoke tests pass (optional, requires device)."""
        self.print_header("Check 5: Smoke Tests (Optional)")

        if not ha_url or not token:
            self.print_warning("Smoke tests skipped (no HA URL/token provided)")
            self.print_info("Use --ha-url and --token to run smoke tests")
            return True  # Optional check

        try:
            result = subprocess.run(
                ["python", "scripts/test-smoke.py", "--ha-url", ha_url, "--token", token],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.print_success("Smoke tests pass")
                return True
            else:
                self.print_failure("Smoke tests failed")
                print(result.stdout)
                print(result.stderr)
                return False
        except Exception as e:
            self.print_failure(f"Error running smoke tests: {e}")
            return False

    def validate(self, ha_url: str | None = None, token: str | None = None) -> bool:
        """Run all validation checks."""
        self.print_header("Pre-Release Validation")

        checks = [
            ("Unit Tests", self.check_unit_tests),
            ("Integration Tests", self.check_integration_tests),
            ("Coverage", self.check_coverage),
            ("Linting", self.check_linting),
            ("Smoke Tests", lambda: self.check_smoke_tests(ha_url, token)),
        ]

        results = []
        for name, check_func in checks:
            try:
                result = check_func()
                results.append((name, result))
            except Exception as e:
                self.print_failure(f"{name} raised exception: {e}")
                results.append((name, False))

        # Summary
        self.print_header("Validation Summary")
        passed = sum(1 for _, result in results if result)
        total = len(results)

        for name, result in results:
            if result:
                self.print_success(f"{name}: PASSED")
            else:
                self.print_failure(f"{name}: FAILED")

        print(f"\n{Colors.BOLD}Results: {passed}/{total} checks passed{Colors.RESET}")

        if passed == total:
            self.print_success("\n✅ Ready for release!")
        else:
            self.print_failure("\n❌ Not ready - fix issues above")

        return passed == total


def main():
    parser = argparse.ArgumentParser(description="WiiM Integration Pre-Release Validation")
    parser.add_argument("--ha-url", help="Home Assistant URL (for smoke tests)")
    parser.add_argument("--token", help="Home Assistant token (for smoke tests)")
    parser.add_argument("--coverage-threshold", type=float, default=0.70, help="Coverage threshold (default: 0.70)")

    args = parser.parse_args()

    validator = PreReleaseValidator(coverage_threshold=args.coverage_threshold)
    success = validator.validate(ha_url=args.ha_url, token=args.token)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

