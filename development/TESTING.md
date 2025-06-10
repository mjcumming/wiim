# Testing Guide for WiiM Integration

This document outlines the testing strategy and best practices for the WiiM Home Assistant integration.

## Testing Strategy

### 1. Unit Testing

- Use `respx` for mocking HTTP requests
- Maintain snapshot JSONs for each device model
- Test all API endpoints and error conditions
- Coverage target: ≥ 90%

### 2. Integration Testing

- Use Home Assistant test harness
- Test entity state and services
- Verify UI integration
- Test configuration flow

### 3. Group Testing

- Test with two mocked devices
- Verify join/kick functionality
- Test computed group volume
- Verify synchronization

### 4. Test Structure

```
tests/
  unit/
    test_api.py
    test_coordinator.py
    test_media_player.py
    test_config_flow.py
  integration/
    test_init.py
    test_services.py
    test_groups.py
```

## Running Tests

### Quick Test (Development)

```bash
make test-quick
```

### Full Test Suite

```bash
make test
```

### Test with Coverage

```bash
make test-coverage
```

## Test Data

- Maintain test fixtures in `tests/fixtures/`
- Use realistic device responses
- Include error cases and edge conditions
- Document test data sources

## CI Pipeline

Tests are automatically run in GitHub Actions:

```yaml
jobs:
  lint-test:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.12'}
      - run: pip install -r requirements-dev.txt
      - run: pre-commit run --all-files
      - run: pytest
```

## Best Practices

1. Write tests before implementing features
2. Test both success and failure paths
3. Mock external dependencies
4. Use realistic test data
5. Maintain test coverage
6. Document test scenarios
7. Keep tests focused and isolated 