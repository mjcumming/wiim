# Diagnostics Overview

The integration surfaces diagnostic data through a **single sensor** while reporting firmware-update availability via Home Assistant's standard Update entity.

| Entity | State | Purpose |
| ------ | ----- | ------- |
| `sensor.<device>_device_status` | "Wi-Fi −55 dBm", "Online", or "Offline" | Holds every field returned by `getStatusEx` (firmware strings, hardware model, Wi-Fi details, uptime, group info, …) as **attributes**.  If RSSI is present the state shows the signal strength; otherwise it falls back to a simple Online/Offline indicator. |
| `update.<device>_firmware` | Disabled by default | Becomes visible when the speaker has already downloaded an update.  Clicking **Install** triggers a reboot; the LinkPlay firmware applies the staged update automatically. |

## How to view the attributes
1. **Developer Tools → States** → choose the *Device Status* sensor and inspect the *Attributes* box.
2. On the **device page** click the *Device Status* entity, then the information icon (ℹ️). The side-panel lists all attributes.
3. Use them directly in automations or templates:

```jinja
{{ state_attr('sensor.kitchen_device_status', 'firmware') }}
{{ state_attr('sensor.kitchen_device_status', 'wifi_rssi') | int(-100) }}
```

### Attribute reference (commonly present)

| Key | Example | Notes |
| --- | ------- | ----- |
| `connection` | `wifi` / `wired` | Inferred from presence of RSSI.
| `firmware` | `4.6.415133.36` | Main firmware version string.
| `release` | `20221104` | Build date (if provided).
| `project` | `W281` | Hardware/board identifier.
| `wifi_rssi` | `-55` | dBm, absent on Ethernet.
| `wifi_channel` | `11` | 2.4 GHz / 5 GHz channel number.
| `uptime` | `86400` | Seconds since last reboot.
| `group` | `master` / `slave` / `solo` | Current multi-room role.
| `preset_key` | `6` | Number of physical preset buttons.

Additional vendor-specific keys (BLE FW, DSP FW, WMRM version, etc.) are included when available.

**Tip:** Because *Device Status* is categorised as *diagnostic* it doesn't clutter dashboards unless you add it to a card, yet the data is always just a click away when you need it.
