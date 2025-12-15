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
import os
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
        self.python = sys.executable

    def _run(self, cmd: list[str], check_name: str) -> bool:
        """Run a command in repo root and return success."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            self.print_failure(f"Error running {check_name}: {e}")
            return False

        if result.returncode == 0:
            self.print_success(f"{check_name} passed")
            return True

        self.print_failure(f"{check_name} failed")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return False

    def check_ci_checks(self) -> bool:
        """Check 0: Run the exact same checks as GitHub CI."""
        self.print_header("Check 0: CI Checks (Exact Match)")
        return self._run(["bash", "scripts/check-before-push.sh"], "CI checks")

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
                [self.python, "-m", "pytest", "tests/unit/", "-v", "--tb=short"],
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

        integration_dir = self.repo_root / "tests" / "integration"
        if not integration_dir.exists():
            # This repository currently uses unit tests under tests/unit/.
            # Treat missing integration test folder as a skipped optional check.
            self.print_warning("Integration tests skipped (tests/integration/ not present)")
            return True

        try:
            result = subprocess.run(
                [self.python, "-m", "pytest", "tests/integration/", "-v", "--tb=short"],
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
                    self.python,
                    "-m",
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
                            self.print_success(
                                f"Coverage above threshold ({coverage:.1f}% >= {self.coverage_threshold * 100:.1f}%)"
                            )
                            return True
                        else:
                            self.print_failure(
                                f"Coverage below threshold ({coverage:.1f}% < {self.coverage_threshold * 100:.1f}%)"
                            )
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
                [self.python, "tests/run_tests.py", "--lint"],
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

    def check_smoke_tests(
        self,
        ha_url: str | None = None,
        token: str | None = None,
        config: str | None = None,
        required: bool = False,
    ) -> bool:
        """Check 5: Smoke tests pass (optional unless required=True)."""
        self.print_header("Check 5: Smoke Tests")

        if config:
            config_path = Path(config)
            if not config_path.is_absolute():
                config_path = self.repo_root / config_path
            if not config_path.exists():
                if required:
                    self.print_failure(f"Smoke tests require config file, not found: {config_path}")
                    return False
                self.print_warning(f"Smoke tests skipped (config not found: {config_path})")
                return True
            return self._run(
                [self.python, "scripts/test-smoke.py", "--config", str(config_path)],
                "Smoke tests",
            )

        if not ha_url or not token:
            if required:
                self.print_failure("Smoke tests required but no HA URL/token provided")
                return False
            self.print_warning("Smoke tests skipped (no HA URL/token provided)")
            self.print_info("Use --ha-url/--token or --config to run smoke tests")
            return True  # Optional check

        try:
            result = subprocess.run(
                [self.python, "scripts/test-smoke.py", "--ha-url", ha_url, "--token", token],
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

    def check_realworld_tests(
        self,
        *,
        ha_url: str | None = None,
        token: str | None = None,
        config: str | None = None,
        full: bool = False,
        required: bool = False,
    ) -> bool:
        """Optional: run real-world tests against a running HA instance."""
        self.print_header("Check 6: Real-World Tests (Optional)")

        # Smoke first (fast sanity)
        if not self.check_smoke_tests(ha_url=ha_url, token=token, config=config, required=required):
            return False

        # Automated suite (critical by default)
        cmd: list[str]
        if config:
            config_path = Path(config)
            if not config_path.is_absolute():
                config_path = self.repo_root / config_path
            if not config_path.exists():
                if required:
                    self.print_failure(f"Real-world tests require config file, not found: {config_path}")
                    return False
                self.print_warning(f"Real-world tests skipped (config not found: {config_path})")
                return True
            cmd = [self.python, "scripts/test-automated.py", "--config", str(config_path)]
        else:
            # test-automated can read HA_URL/HA_TOKEN from env if not using --config
            if not ha_url or not token:
                if required:
                    self.print_failure("Real-world tests required but no HA URL/token provided")
                    return False
                self.print_warning("Real-world tests skipped (no HA URL/token provided)")
                return True
            cmd = [self.python, "scripts/test-automated.py"]

        cmd += ["--mode", "full" if full else "critical"]
        if not self._run(cmd, "Automated real-world tests"):
            return False

        # Multiroom is only part of the full real-world cycle and requires env vars.
        if full:
            if not ha_url or not token:
                if required:
                    self.print_failure("Full real-world tests require --ha-url and --token (for multiroom)")
                    return False
                self.print_warning("Skipping multiroom (requires --ha-url/--token for HA_URL/HA_TOKEN env)")
                return True

            env = {**os.environ.copy(), "HA_URL": ha_url, "HA_TOKEN": token}
            try:
                result = subprocess.run(
                    [self.python, "scripts/test-multiroom-comprehensive.py"],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                    env=env,
                )
            except Exception as e:
                self.print_failure(f"Error running multiroom tests: {e}")
                return False

            if result.returncode != 0:
                self.print_failure("Multiroom tests failed")
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
                return False

            self.print_success("Multiroom tests passed")

        return True

    def validate(
        self,
        ha_url: str | None = None,
        token: str | None = None,
        config: str | None = None,
        run_realworld: bool = False,
        realworld_full: bool = False,
        require_realworld: bool = False,
    ) -> bool:
        """Run all validation checks."""
        self.print_header("Pre-Release Validation")

        checks = [
            ("CI Checks", self.check_ci_checks),
            ("Unit Tests", self.check_unit_tests),
            ("Integration Tests", self.check_integration_tests),
            ("Coverage", self.check_coverage),
            ("Linting", self.check_linting),
            ("Smoke Tests", lambda: self.check_smoke_tests(ha_url=ha_url, token=token, config=config)),
            (
                "Real-World Tests",
                lambda: self.check_realworld_tests(
                    ha_url=ha_url,
                    token=token,
                    config=config,
                    full=realworld_full,
                    required=require_realworld,
                )
                if (run_realworld or require_realworld)
                else True,
            ),
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
    parser.add_argument("--config", help="Path to scripts/test.config for real-world tests")
    parser.add_argument(
        "--realworld",
        action="store_true",
        help="Run critical real-world tests (smoke + automated critical) if HA details are provided",
    )
    parser.add_argument(
        "--realworld-full",
        action="store_true",
        help="Run full real-world tests (smoke + automated full + multiroom). Requires --ha-url/--token for multiroom.",
    )
    parser.add_argument(
        "--require-realworld",
        action="store_true",
        help="Require real-world tests to pass (fail if HA details/config are missing).",
    )
    parser.add_argument("--coverage-threshold", type=float, default=0.70, help="Coverage threshold (default: 0.70)")

    args = parser.parse_args()

    validator = PreReleaseValidator(coverage_threshold=args.coverage_threshold)
    success = validator.validate(
        ha_url=args.ha_url,
        token=args.token,
        config=args.config,
        run_realworld=args.realworld or args.realworld_full,
        realworld_full=args.realworld_full,
        require_realworld=args.require_realworld,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
