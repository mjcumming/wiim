# getEQ → EQGetBand Migration Analysis

**Date**: 2025-01-27
**Issue**: `getEQ` endpoint doesn't exist on WiiM devices (returns "unknown command")
**Solution**: Migrate to `EQGetBand` endpoint
**Status**: Analysis and considerations

---

## 🔍 **Current Situation**

### **Problem**
- `getEQ` endpoint returns `"unknown command"` on WiiM devices
- Our code uses `getEQ` in multiple places
- `EQGetBand` is the correct endpoint and works

### **Discovery**
From device testing:
```bash
curl -k "https://192.168.1.68/httpapi.asp?command=getEQ"
# Returns: "unknown command"

curl -k "https://192.168.1.68/httpapi.asp?command=EQGetBand"
# Returns: Full EQ configuration with preset and band data
```

---

## 📊 **Response Format Comparison**

### **getEQ (Doesn't Work)**
```json
"unknown command"
```

### **EQGetBand (Works)**
```json
{
  "status": "OK",
  "EQLevel": 1,
  "source_name": "wifi",
  "EQStat": "On",
  "Name": "Flat",
  "pluginURI": "http://moddevices.com/plugins/caps/Eq10HP",
  "channelMode": "Stereo",
  "EQBand": [
    {"index": 0, "param_name": "band31hz", "value": 50},
    {"index": 1, "param_name": "band63hz", "value": 50},
    // ... 8 more bands
  ]
}
```

---

## 🔧 **Code Locations Requiring Changes**

### **1. Constants (`const.py`)**

**Current:**
```python
API_ENDPOINT_EQ_GET = "/httpapi.asp?command=getEQ"
```

**Should Be:**
```python
API_ENDPOINT_EQ_GET = "/httpapi.asp?command=EQGetBand"
```

**Impact**: Low - just endpoint string change

---

### **2. API Client (`api_eq.py`)**

**Current Usage:**
```python
async def get_eq(self) -> dict[str, Any]:
    return await self._request(API_ENDPOINT_EQ_GET)
```

**Considerations:**
- ✅ Method signature stays the same
- ✅ Return type stays the same (dict)
- ✅ Response format is compatible (both return dict)
- ⚠️ **Field names differ** - need to verify parsing

**Response Field Mapping:**
- `EQGetBand` has `"Name"` field (preset name)
- Our code looks for: `["EQ", "eq_preset", "eq_mode", "sound_mode", "preset"]`
- **Need to add `"Name"` to the field search list**

---

### **3. EQ Status Heuristic (`api_eq.py` line 75-77)**

**Current:**
```python
# heuristic: if /getEQ succeeds, EQ subsystem exists – treat as enabled
try:
    await self._request(API_ENDPOINT_EQ_GET)
    return True
except Exception:
    return False
```

**Considerations:**
- ✅ Logic stays the same (just different endpoint)
- ✅ If `EQGetBand` succeeds, EQ subsystem exists
- ⚠️ **Should verify response has `"status": "OK"`** to confirm success

**Recommendation:**
```python
# heuristic: if EQGetBand succeeds, EQ subsystem exists – treat as enabled
try:
    response = await self._request(API_ENDPOINT_EQ_GET)
    # Verify we got a valid response (not "unknown command")
    if isinstance(response, dict) and response.get("status") == "OK":
        return True
    return False
except Exception:
    return False
```

---

### **4. EQ Info Fetching (`coordinator_eq.py` line 116)**

**Current:**
```python
eq_data = await coordinator.client.get_eq()
if eq_data:
    # ROBUST detection of 'unknown command' responses
    raw_response = eq_data.get("raw", "")
    if (
        isinstance(raw_response, str)
        and raw_response.strip()
        and ("unknown command" in raw_response.lower() or "unknow command" in raw_response.lower())
    ):
        _LOGGER.info(
            "[WiiM] %s: Device responded 'unknown command' to getEQ – permanently disabling EQ polling",
            coordinator.client.host,
        )
        coordinator._eq_supported = False
        return EQInfo.model_validate(eq_dict)
```

**Considerations:**
- ⚠️ **Unknown command detection** - This check is still valid (some devices might not support `EQGetBand` either)
- ⚠️ **Error message** - Should update to say "EQGetBand" instead of "getEQ"
- ✅ **Response parsing** - Need to handle `EQGetBand` format

**Response Parsing Updates Needed:**
```python
# Extract eq_enabled from EQStat field
if "eq_enabled" not in eq_dict:
    eq_stat = eq_data.get("EQStat", "").lower()
    if eq_stat == "on":
        eq_dict["eq_enabled"] = True
    elif eq_stat == "off":
        eq_dict["eq_enabled"] = False

# Extract EQ preset from Name field (add to existing field search)
for field_name in ["Name", "EQ", "eq_preset", "eq_mode", "sound_mode", "preset"]:
    preset_val = eq_data.get(field_name)
    if preset_val is not None and str(preset_val).strip() not in ["", "unknown", "none"]:
        eq_dict["eq_preset"] = preset_val
        break
```

---

### **5. Error Messages**

**Locations:**
1. `coordinator_eq.py` line 126: `"Device responded 'unknown command' to getEQ"`
2. `coordinator_eq.py` line 166: `"EQ not supported by device - both getEQ and EQGetStat failed"`
3. `API_GUIDE.md` line 203: References to `getEQ` in defensive programming examples

**Updates Needed:**
- Change "getEQ" to "EQGetBand" in error messages
- Update API guide examples

---

## 🎯 **Field Mapping Strategy**

### **EQGetBand Response Fields → Our Model**

| EQGetBand Field | Our Model Field | Notes |
|----------------|-----------------|-------|
| `"Name"` | `eq_preset` | Preset name (e.g., "Flat", "Rock") |
| `"EQStat"` | `eq_enabled` | "On" → True, "Off" → False |
| `"status"` | (validation) | "OK" confirms success |
| `"EQBand"` | (not used) | 10-band EQ data (for custom EQ) |

### **Preset Extraction Priority**

Current code checks (in order):
1. `"EQ"` - Usually display name
2. `"eq_preset"` - Standard field
3. `"eq_mode"` - Alternative field
4. `"sound_mode"` - Alternative field
5. `"preset"` - Generic field

**Should Add:**
- `"Name"` - **Add as first priority** (EQGetBand uses this)

---

## ⚠️ **Important Considerations**

### **1. Backward Compatibility**

**Question**: Do any LinkPlay devices (non-WiiM) support `getEQ`?

**Risk**: If we change to `EQGetBand`, we might break support for some LinkPlay devices.

**Mitigation**:
- Test with Audio Pro devices (if available)
- Keep fallback logic for "unknown command"
- Consider device detection to use correct endpoint

**Recommendation**:
- Change to `EQGetBand` (it's the correct endpoint)
- Keep robust error handling for unsupported devices
- If `EQGetBand` fails, fall back gracefully (same as current behavior)

---

### **2. Response Format Differences**

**Current Code Expectations:**
- Looks for `"raw"` field for unknown command detection
- Looks for various preset field names
- Looks for `"enabled"` field for EQ status

**EQGetBand Reality:**
- No `"raw"` field (it's a proper JSON response)
- Uses `"Name"` for preset (not in our search list)
- Uses `"EQStat"` for status (not `"enabled"`)

**Solution**: Update parsing logic to handle both formats (if needed) or just `EQGetBand` format.

---

### **3. Unknown Command Detection**

**Current Logic:**
```python
raw_response = eq_data.get("raw", "")
if "unknown command" in raw_response.lower():
    # Mark as unsupported
```

**EQGetBand Behavior:**
- If device doesn't support `EQGetBand`, it will return `"unknown command"` as a string (not JSON)
- Our `_request()` method might wrap this differently

**Need to Test:**
- What happens when `EQGetBand` returns "unknown command"?
- Does it come back as `{"raw": "unknown command"}` or just `"unknown command"`?

---

### **4. Heuristic in get_eq_status()**

**Current:**
```python
# If EQGetStat fails, try getEQ as heuristic
try:
    await self._request(API_ENDPOINT_EQ_GET)
    return True  # EQ subsystem exists
except Exception:
    return False
```

**Considerations:**
- This heuristic is still valid with `EQGetBand`
- Should verify response is valid (not "unknown command")
- Should check `"status": "OK"` to confirm success

---

## 📝 **Recommended Changes**

### **Priority 1: Update Endpoint Constant**

```python
# const.py
API_ENDPOINT_EQ_GET = "/httpapi.asp?command=EQGetBand"
```

### **Priority 2: Update Response Parsing**

```python
# coordinator_eq.py - fetch_eq_info()
# Add "Name" to preset field search (first priority)
for field_name in ["Name", "EQ", "eq_preset", "eq_mode", "sound_mode", "preset"]:
    preset_val = eq_data.get(field_name)
    # ... existing logic

# Extract eq_enabled from EQStat
if "eq_enabled" not in eq_dict:
    eq_stat = eq_data.get("EQStat", "").lower()
    if eq_stat == "on":
        eq_dict["eq_enabled"] = True
    elif eq_stat == "off":
        eq_dict["eq_enabled"] = False
```

### **Priority 3: Update Heuristic**

```python
# api_eq.py - get_eq_status()
try:
    response = await self._request(API_ENDPOINT_EQ_GET)
    # Verify valid response
    if isinstance(response, dict) and response.get("status") == "OK":
        return True
    return False
except Exception:
    return False
```

### **Priority 4: Update Error Messages**

```python
# coordinator_eq.py
"[WiiM] %s: Device responded 'unknown command' to EQGetBand – permanently disabling EQ polling"
"[WiiM] %s: EQ not supported by device - both EQGetBand and EQGetStat failed"
```

### **Priority 5: Update API Guide**

- Update defensive programming examples
- Note that `getEQ` doesn't exist, use `EQGetBand`

---

## 🧪 **Testing Requirements**

### **Test Cases**

1. **Normal Operation**
   - Device supports `EQGetBand`
   - Response parsed correctly
   - Preset extracted from `"Name"` field
   - EQ enabled status from `"EQStat"` field

2. **Unsupported Device**
   - Device returns "unknown command"
   - Gracefully falls back
   - Marks EQ as unsupported

3. **EQ Disabled**
   - `"EQStat": "Off"`
   - Correctly sets `eq_enabled = False`
   - Preset still extracted (if available)

4. **Custom EQ**
   - `"Name"` might be "Custom" or similar
   - Should handle gracefully

5. **Heuristic Test**
   - `EQGetStat` fails
   - `EQGetBand` succeeds
   - Should return `True` for EQ enabled

---

## 🚨 **Risks & Mitigations**

### **Risk 1: Breaking Non-WiiM Devices**

**Risk**: Some LinkPlay devices might only support `getEQ`, not `EQGetBand`

**Mitigation**:
- Test with Audio Pro devices
- Keep robust error handling
- If `EQGetBand` fails, device will gracefully disable EQ (same as current behavior)

**Likelihood**: Low (most LinkPlay devices use same API)

---

### **Risk 2: Response Format Changes**

**Risk**: `EQGetBand` response format might differ from what we expect

**Mitigation**:
- We've tested actual device response
- Response format is well-documented in API guide
- Parsing logic is flexible (checks multiple field names)

**Likelihood**: Low (we have actual device response)

---

### **Risk 3: Unknown Command Detection**

**Risk**: Unknown command detection might not work with `EQGetBand`

**Mitigation**:
- Test with device that doesn't support EQ
- Verify error handling still works
- Keep fallback logic

**Likelihood**: Low (error handling is robust)

---

## ✅ **Migration Checklist**

- [ ] Update `API_ENDPOINT_EQ_GET` constant
- [ ] Update preset field search to include `"Name"` (first priority)
- [ ] Update `eq_enabled` extraction to use `"EQStat"` field
- [ ] Update heuristic in `get_eq_status()` to verify response
- [ ] Update error messages (2 locations)
- [ ] Update API guide examples
- [ ] Test with WiiM device (should work)
- [ ] Test with Audio Pro device (if available)
- [ ] Test error handling (unsupported device)
- [ ] Update unit tests
- [ ] Verify integration tests pass

---

## 📚 **References**

- [API Guide - EQGetBand Documentation](API_GUIDE.md#get-current-eq-settings)
- [WiiM Play Codebase Review](WIIMPLAY_CODEBASE_REVIEW.md) - Confirms `EQGetBand` usage
- [OpenAPI Spec](https://github.com/cvdlinden/wiim-httpapi) - Documents `EQGetBand`

---

## 🎯 **Conclusion**

**Migration is straightforward** with these considerations:

1. ✅ Endpoint change is simple (one constant)
2. ✅ Response format is compatible (both return dict)
3. ⚠️ Field names differ - need parsing updates
4. ⚠️ Error messages need updating
5. ⚠️ Need to test with various devices

**Recommendation**: Proceed with migration, but:
- Test thoroughly with different devices
- Keep robust error handling
- Update all references to `getEQ`
- Verify backward compatibility

