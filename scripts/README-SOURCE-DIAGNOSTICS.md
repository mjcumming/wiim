# Input Source List Diagnostics

This guide helps you determine if input source list issues are caused by **pywiim** or our **integration code**.

## Quick Diagnosis

### Method 1: Direct pywiim Inspection (Recommended)

Use the standalone diagnostic script to see exactly what pywiim is returning:

```bash
cd /workspaces/wiim
python scripts/test-pywiim-sources.py <device_ip> [port]
```

Example:

```bash
python scripts/test-pywiim-sources.py 192.168.1.100
python scripts/test-pywiim-sources.py 192.168.1.100 443
```

This script will show:

- `input_list` from `device_info` (raw API data)
- `available_sources` from Player (pywiim's filtered list)
- Comparison between the two
- Raw API response if accessible

**Interpretation:**

- If `input_list` or `available_sources` is wrong → **pywiim issue**
- If both are correct but HA shows wrong → **integration issue**

### Method 2: Home Assistant Diagnostics

1. Go to **Settings** → **Devices & Services** → **WiiM** → **[Your Device]**
2. Click **Diagnostics**
3. Look for `source_list_diagnostics` section

This shows:

- `available_sources_from_pywiim` - What pywiim Player provides
- `input_list_from_device_info` - What device API returns (via pywiim)
- `displayed_source_list` - What Home Assistant displays

### Method 3: Enable Debug Logging

Add to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.wiim: debug
```

Then check logs for lines like:

```
[Speaker Name] source_list: Using available_sources from pywiim: [...]
[Speaker Name] source_list: After capitalization: [...]
```

### Method 4: Use Test Suite

The test suite now shows pywiim data when testing sources:

```bash
python scripts/test-complete-suite.py <ha_url> --token <token>
```

Look for the source test output which now includes:

- Source list from HA
- Pywiim available_sources
- Pywiim input_list

## Understanding the Data Flow

```
Device API (getStatusEx)
    ↓
pywiim WiiMClient.get_device_info()
    ↓
pywiim Player.device_info.input_list  ← Raw list from device
    ↓
pywiim Player.available_sources        ← Filtered/processed by pywiim
    ↓
Our integration source_list property   ← Capitalized for display
    ↓
Home Assistant UI
```

## Common Issues

### Issue: Missing sources in list

- **Check pywiim first**: Run `test-pywiim-sources.py` to see if pywiim has the source
- If pywiim has it but HA doesn't → Check our `source_list` property logic
- If pywiim doesn't have it → Check device API or pywiim filtering logic

### Issue: Wrong source names

- **Check capitalization**: Our `_capitalize_source_name()` function may need updates
- **Check pywiim**: See what raw names pywiim provides

### Issue: Sources that shouldn't be selectable

- **Check pywiim**: `available_sources` should filter non-selectable sources
- If `available_sources` includes non-selectable → pywiim issue
- If we're using `input_list` instead of `available_sources` → our issue

## Reporting Issues

When reporting source list issues, please include:

1. Output from `test-pywiim-sources.py`
2. Diagnostics data (especially `source_list_diagnostics`)
3. Device model and firmware version
4. What sources are expected vs. what's shown

This helps determine if it's a pywiim issue (upstream) or integration issue (our code).
