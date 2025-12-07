# Bug Fix Testing Checklist

> **Quick reference workflow for fixing bugs.** For comprehensive testing strategy, see [TESTING-CONSOLIDATED.md](TESTING-CONSOLIDATED.md).

## Before Fixing Any Bug

- [ ] Reproduce the bug
- [ ] Write a failing test that reproduces the bug
- [ ] Verify the test fails (confirms bug exists)

## While Fixing

- [ ] Implement the fix
- [ ] Run the test - should now pass
- [ ] Add edge case tests (None values, missing attributes, etc.)
- [ ] Run full test suite: `make test`

## After Fixing

- [ ] All new tests pass
- [ ] All existing tests still pass
- [ ] No linting errors: `make lint`
- [ ] Manual testing (if applicable)
- [ ] Update CHANGELOG.md
- [ ] Update this checklist if new patterns emerge

## Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/test_media_player.py -v

# Run specific test
pytest tests/unit/test_media_player.py::TestWiiMMediaPlayerVolume::test_volume_step_reads_from_config_custom -v

# Run with coverage
pytest --cov=custom_components.wiim --cov-report=term-missing
```
