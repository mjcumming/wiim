# IPv6 Regression Test Suite

This test suite prevents regression of GitHub issue #81, which was caused by improper IPv6 URL construction in the WiiM Home Assistant integration.

## Problem Solved

**GitHub Issue #81**: "Unknown error occurred" when adding the IP address of a WiiM Ultra device.

**Root Cause**: The integration was not properly handling IPv6 addresses in URL construction, leading to "Invalid IPv6 URL" errors when `urlsplit()` tried to parse malformed URLs.

**Solution**: Fixed URL construction logic to properly add brackets around IPv6 addresses when reconstructing URLs.

## Test Files

### 1. `test_ipv6_regression.py`

Comprehensive integration test that verifies:

- IPv6 URL construction works correctly
- IPv6 vs IPv4 parsing logic is correct
- Original bug scenario is prevented
- Edge cases are handled properly

### 2. `run_ipv6_tests.py`

Test runner script for CI/CD pipelines that:

- Runs the regression test suite
- Provides clear pass/fail output
- Returns appropriate exit codes for automation

### 3. Unit Tests in `test_api_base.py`

Added `TestWiiMClientIPv6Handling` class with tests for:

- IPv6 URL construction in fast-path
- IPv6 URL construction in protocol fallback
- IPv6 bracketed URL construction
- IPv6 vs IPv4 host:port parsing
- IPv6 edge cases
- IPv6 request simulation

### 4. Unit Tests in `test_config_flow.py`

Added `TestIPv6ConfigFlowHandling` class with tests for:

- IPv6 vs host:port parsing in config flow
- IPv6 edge cases in config flow
- IPv6 address validation

## Running the Tests

### Manual Testing

```bash
# Run the comprehensive regression test
python tests/integration/test_ipv6_regression.py

# Run the test runner (for CI/CD)
python tests/integration/run_ipv6_tests.py
```

### Unit Tests (if test framework is working)

```bash
# Run IPv6-specific unit tests
python -m pytest tests/unit/test_api_base.py::TestWiiMClientIPv6Handling -v
python -m pytest tests/unit/test_config_flow.py::TestIPv6ConfigFlowHandling -v
```

## What the Tests Verify

### ✅ IPv6 URL Construction

- URLs with IPv6 addresses are properly formatted with brackets
- `urlsplit()` can successfully parse reconstructed URLs
- No "Invalid IPv6 URL" errors occur

### ✅ IPv6 vs IPv4 Parsing

- IPv6 addresses are not incorrectly parsed as host:port format
- IPv4 addresses with ports are correctly parsed as host:port
- Config flow logic handles both cases properly

### ✅ Edge Cases

- Various IPv6 address formats (localhost, trailing ::, full addresses)
- IPv6 addresses with zone identifiers
- IPv6 addresses with custom ports

### ✅ Original Bug Prevention

- Simulates the exact scenario that caused GitHub issue #81
- Verifies that the old buggy logic would fail
- Confirms that the new fixed logic works correctly

## Integration with CI/CD

The test suite can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions step
- name: Run IPv6 Regression Tests
  run: python tests/integration/run_ipv6_tests.py
```

## Maintenance

These tests should be run:

- Before any release
- When making changes to URL construction logic
- When modifying IPv6 handling code
- As part of the regular test suite

## Success Criteria

All tests must pass to ensure:

- IPv6 devices can be added to Home Assistant without errors
- The "Invalid IPv6 URL" error does not regress
- IPv6 and IPv4 addresses are handled correctly
- The integration works with modern IPv6-enabled networks
