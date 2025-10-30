# Why Discovery Bugs Keep Getting Missed

## The Problem: Missing Test Coverage

GitHub issue #80 (Audio Pro discovery failures) represents a systemic testing gap in the WiiM integration.

## Root Causes

### 1. **Zero Discovery Flow Tests**

The `async_step_zeroconf` and `async_step_ssdp` methods have **zero test coverage**:

```bash
# Search results: 0 tests for discovery flows
grep -r "async_step_zeroconf\|async_step_ssdp" wiim/tests/
# No matches found
```

### 2. **No Validation Failure Scenarios**

All existing tests mock successful validation:

```python
return_value=(True, "WiiM Device", "test-uuid-123")  # Always succeeds!
```

But Audio Pro devices **fail validation** during discovery, returning:

```python
return_value=(False, "Audio Pro Speaker", "10.0.0.32")  # Host as fallback
```

### 3. **No Audio Pro Device Testing**

Zero tests for Audio Pro specific models:

- No tests for A10/A15/A28/C10 MkII
- No tests for W-Series devices
- No tests for HTTPS-only devices

### 4. **Missing Conditional Logic Tests**

The bug was in the control flow logic itself:

```python
# BEFORE FIX (Buggy):
elif device_uuid:  # Always True when validation fails!
    # Soft failure handling
elif is_likely_audio_pro:  # NEVER REACHED!

# AFTER FIX:
is_real_uuid = device_uuid and device_uuid != host
elif is_real_uuid:  # Only true for real UUIDs
    # Soft failure handling
elif is_likely_audio_pro:  # NOW CAN BE REACHED!
```

No tests verified this conditional logic order.

## What Testing SHOULD Have Caught This

### Unit Test That Would Have Found It

```python
async def test_audio_pro_zeroconf_discovery_with_validation_failure():
    """Test Audio Pro discovery when validation fails."""

    # Mock failed validation (common for Audio Pro)
    mock_validate = AsyncMock(
        return_value=(False, "Audio Pro Speaker", "10.0.0.32")  # Host as UUID!
    )

    # Test discovery flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=zeroconf_discovery_info
    )

    # THE BUG: Would abort with "cannot_connect"
    # CORRECT: Should offer manual setup
    assert result["reason"] != "cannot_connect"
```

## Why It Happened

### 1. **Success Bias in Tests**

All tests assume everything works perfectly. Real devices fail sometimes.

### 2. **No Real Device Testing**

Developers likely don't have:

- Audio Pro devices
- MkII/W-Series models
- Devices that fail validation

### 3. **Complex Conditional Logic**

The discovery flow has multiple conditional branches that need specific test cases for each path.

### 4. **Missing Integration Tests**

No automated tests with actual zeroconf/SSDP discovery events.

## How to Prevent This

### 1. Add Discovery Flow Tests

✅ Created `test_discovery_audio_pro.py` with comprehensive discovery tests

### 2. Test Failure Scenarios

Every validation function needs tests for:

- Success
- Failure
- Partial failure
- Timeout
- Network errors

### 3. Test All Conditional Branches

Use test coverage tools to ensure every `if/elif/else` path is tested.

### 4. Test Device-Specific Behavior

Add tests for:

- Audio Pro devices
- WiiM devices
- Different firmware versions
- Different protocols (HTTP/HTTPS)

### 5. Add Integration Tests

Test with real discovery events, not just mocked data.

### 6. Use Mutation Testing

Tools like `mutmut` can detect untested code paths.

## Current Test Coverage Gaps

| Feature             | Unit Tests | Integration Tests | Status           |
| ------------------- | ---------- | ----------------- | ---------------- |
| Zeroconf discovery  | ❌ 0       | ❌ 0              | **CRITICAL GAP** |
| SSDP discovery      | ❌ 0       | ❌ 0              | **CRITICAL GAP** |
| Validation failures | ❌ 0       | ❌ 0              | **CRITICAL GAP** |
| Audio Pro devices   | ❌ 0       | ❌ 0              | **CRITICAL GAP** |
| Manual entry        | ✅ 14      | ❌ 0              | Partial          |
| IPv6 handling       | ✅ Yes     | ✅ Yes            | Good             |

## Action Items

1. ✅ **Immediate**: Run the new `test_discovery_audio_pro.py` suite
2. ⏳ **Short-term**: Add more discovery flow tests
3. ⏳ **Medium-term**: Set up integration test suite with real devices
4. ⏳ **Long-term**: Achieve >90% code coverage for config flow

## Lessons Learned

1. **Edge cases ARE the common cases** - Audio Pro devices are common users
2. **Failure handling needs MORE tests than success** - Most bugs are in error paths
3. **Control flow is hard to get right** - Every branch needs explicit testing
4. **Real device testing is essential** - Mocks can't catch API differences
5. **Discovered bugs create patterns** - Similar issues exist elsewhere

## References

- GitHub Issue #80: Audio Pro Compatibility
- GitHub Issue #81: IPv6 Regression (similar testing gap)
- Test file: `tests/unit/test_discovery_audio_pro.py` (NEW)
