#!/usr/bin/env python3
"""
Test runner for IPv6 regression tests.

This script can be used in CI/CD pipelines to ensure IPv6 handling
remains working correctly and prevents regression of GitHub issue #81.

Usage:
    python tests/integration/run_ipv6_tests.py
"""

import sys
import os
import subprocess


def run_ipv6_regression_tests():
    """Run the IPv6 regression test suite."""
    print("🧪 Running IPv6 Regression Tests...")

    # Get the path to the test script
    test_script = os.path.join(os.path.dirname(__file__), "test_ipv6_regression.py")

    if not os.path.exists(test_script):
        print(f"❌ Test script not found: {test_script}")
        return False

    try:
        # Run the test script
        result = subprocess.run(
            [sys.executable, test_script],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )

        # Print the output
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        # Return success if exit code is 0
        return result.returncode == 0

    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False


def main():
    """Main test runner."""
    print("=" * 60)
    print("🔍 IPv6 REGRESSION TEST RUNNER")
    print("=" * 60)

    success = run_ipv6_regression_tests()

    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("✅ IPv6 handling is working correctly")
        print("✅ GitHub issue #81 regression prevention is active")
        return 0
    else:
        print("❌ TESTS FAILED!")
        print("🚨 IPv6 handling may have issues")
        print("🔧 Please check the test output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
