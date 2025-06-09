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
| `sensor.<device>_preset_slots` | `10` | Number of preset buttons available on the device |
| `sensor.<device>_wmrm_version` | `4.2` | WiiM/LinkPlay multi-room protocol version |

## Optional Diagnostic Sensors

These are **disabled unless you enable "Diagnostic entities"** in the device options dialog.

| Entity | Source Field |
|--------|--------------|
| `sensor.<device>_firmware_date` | `Release` |
| `sensor.<device>_hardware`      | `hardware` / `project` |
| `sensor.<device>_mcu_version`   | `mcu_ver` |
| `sensor.<device>_dsp_version`   | `dsp_ver` |

## Automations & Templates

```yaml
# Notify when a new firmware is ready
automation:
  - alias: WiiM Firmware Available
    trigger:
      - platform: state
        entity_id: update.living_room_firmware
        to: 'on'          # update entity becomes available
    action:
      - service: notify.mobile_app_phone
        data:
          message: "New WiiM firmware ready for Living-Room!  Hit *Install* in HA to update."
```

```yaml
# Show build date in a Markdown card
#{% set date = states('sensor.living_room_firmware_date') %}
WiiM build date: **{{ date[:4] }}-{{ date[4:6] }}-{{ date[6:] }}**
```

## Technical Reference

All values originate from the HTTP call:

```
GET /httpapi.asp?command=getStatusEx
```

Field mapping:

| HTTP Key        | Entity            |
|-----------------|-------------------|
| `firmware`      | sensor.*_firmware / update.installed_version |
| `NewVer`        | update.latest_version |
| `VersionUpdate` | update.available |
| `preset_key`    | sensor.*_preset_slots |
| `wmrm_version`  | sensor.*_wmrm_version |

See the full LinkPlay API spec at Arylic's developer page and the community OpenAPI file for additional details. 