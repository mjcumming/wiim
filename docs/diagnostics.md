# WiiM Integration – Diagnostics

The integration surfaces a small set of **device-health** entities based on the `getStatusEx` endpoint.  They are lightweight (one extra API call every 30 s) and provide quick insight when things go wrong.

## Firmware Update Indicator

| Entity | Description |
|--------|-------------|
| `update.<device>_firmware` | Signals when the speaker has downloaded a newer firmware and is ready to install.  Click **Install** to reboot the device – LinkPlay applies the update automatically during boot. |

**Limitations**
* The HTTP-API does **not** allow us to trigger a download – the device must have staged the update itself.
* If the vendor has not published an OTA package, the entity will simply stay in the *Up-to-date* state.

## Always-on Sensors

| Entity | Example | Notes |
|--------|---------|-------|
| `sensor.<device>_firmware` | `4.6.415145` | Current firmware build number |

## Optional Diagnostic Sensors

These are **disabled unless you enable "Diagnostic entities"** in the device options dialog.

| Entity | Source Field |
|--------|--------------|
| `sensor.<device>_preset_slots` | `preset_key` |
| `sensor.<device>_wmrm_version` | `wmrm_version` |
| `sensor.<device>_firmware_date` | `Release` |
| `sensor.<device>_hardware`      | `hardware` |
| `sensor.<device>_project`       | `project` |
| `sensor.<device>_mcu_version`   | `mcu_ver` |
| `sensor.<device>_dsp_version`   | `dsp_ver` |