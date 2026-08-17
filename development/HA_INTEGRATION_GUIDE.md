# Home Assistant integration guide reference

> The canonical Home Assistant integration guide for `pywiim` lives in the upstream library repository and is maintained there: <https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_INTEGRATION.md>.
> This file intentionally stays short and points you to that single source of truth so we do not ship a stale duplicate.

## Why we reference the upstream doc

- The upstream `pywiim` team updates the guide alongside library changes, so linking avoids drift.
- Pulling the latest content is as simple as opening the URL above; no sync process is needed for everyday work.
- Documentation reviews stay focused on our project-specific additions instead of copy-paste churn.

## Quick reminders (read the upstream doc for full detail)

- Prefer the `Player` wrapper when integrating with Home Assistant’s `DataUpdateCoordinator`; it handles caching, HTTP + UPnP merging, and exposes convenient properties.
- Use `PollingStrategy` from the library to adapt polling intervals instead of hardcoding scan intervals.
- When you enable UPnP queue operations or event subscriptions, create the UPnP client inside the integration and pass it to `Player` and (optionally) `UpnpEventer`.
- Group operations (`join_group`, `leave_group`) are already orchestrated by the library—call them and rely on the callback to update entities.

Refer to the full upstream guide whenever you need code samples, diagrams, or the complete checklist.

## API Reference

> The complete API reference for `pywiim` is also maintained upstream: <https://github.com/mjcumming/pywiim/blob/main/docs/integration/API_REFERENCE.md>.
> This provides detailed documentation for all classes, methods, and models in the library.

When you need detailed API documentation for `WiiMClient`, `Player`, models, exceptions, or any API mixins, refer to the upstream API reference guide.

## Working offline or auditing changes

If you truly need a local snapshot (for example while traveling without internet), fetch it ad hoc and avoid committing the downloaded copy:

```bash
# Fetch the HA integration guide
curl -L https://raw.githubusercontent.com/mjcumming/pywiim/main/docs/integration/HA_INTEGRATION.md \
  -o /tmp/ha_integration_guide.md

# Fetch the API reference guide
curl -L https://raw.githubusercontent.com/mjcumming/pywiim/main/docs/integration/API_REFERENCE.md \
  -o /tmp/api_reference_guide.md
```

Review them locally, then delete the temporary files when done. Should we ever need to vendor a copy again, make sure to document the source commit hash in the PR description so reviewers know which upstream version was imported.

## Version Tracking

This guide should be reviewed and updated whenever the `pywiim` library version is updated in `manifest.json`.

**Current pywiim version requirement:** See `custom_components/wiim/manifest.json` for the current minimum version.

**Update process:**

1. When updating `pywiim` version in `manifest.json`, update the review date below
2. Fetch the latest upstream guides to check for changes
3. Update this file's review date and note any significant changes
4. Document the version update in `CHANGELOG.md`

_Last reviewed against upstream on 2026-08-17 (pywiim 2.3.5: Sound / Sound Lite
audio output catalog is Speaker Out; hardware 7 maps to Speaker Out on those
models and remains HDMI Out on Amp Ultra; Bluetooth Out is source=1). Keep using
`Player.supports_*` only — do not add HA fallbacks._

**Notable upstream changes (2.2.16):** `set_display_enabled(True)` now enables adaptive brightness (`auto_sense_enable=1`) by default so the LCD actually relights; optional `auto_sense_enable` keyword on client and player (pass `0` for fixed brightness). See [API_REFERENCE.md](https://github.com/mjcumming/pywiim/blob/main/docs/integration/API_REFERENCE.md) (Display section).

**Notable upstream changes (2.2.17):** `curpos` / `totlen` parsing is source-aware for long local URL and USB/UDisk media,
and `vendor=UDisk*` status on WiiM Ultra normalizes to source `usb`. No breaking changes were found in the upstream integration
guide or API reference.

**Notable upstream changes (2.2.18):** no Home Assistant integration API changes required.

**Notable upstream changes (2.2.19):** read-only WiiM helpers for `getAudioInputCapbility`, Eq10HP graphic EQ, and
room-correction diagnostics. No Home Assistant integration API changes required. Integration pin updated so HA Core 2026.6 /
Python 3.14 installs retry pywiim dependency resolution with a fresh requirement string.

**Notable upstream changes (2.3.0):** `available_sources` / `source_catalog` now overlay the read-only WiiM input APIs
(`getModeRename`, `getAudioInputEnable`, `getAudioInputCapbility`) on WiiM devices — user custom input labels are shown,
disabled inputs are hidden, and the authoritative input list fills gaps left by `plm_support` guessing. `set_source()` resolves
the custom label plus the previous/canonical names, so the integration consumes this transparently through the existing
`source` / `source_name` / `select_source` surface. No Home Assistant integration API changes required ([Issue #257](https://github.com/mjcumming/wiim/issues/257)).

**Notable upstream changes (2.1.98):** WiiM Ultra LCD control uses `setLightOperationBrightConfig` via `Player.set_display_enabled` / `set_display_config`. `set_display_enabled(True)` applies `DISPLAY_DEFAULT_BRIGHTNESS` (100) when turning on unless `default_bright` is passed; brightness uses a **1–100** device scale (`DISPLAY_BRIGHTNESS_MIN` / `DISPLAY_BRIGHTNESS_MAX`).

**Capability refresh after firmware OTA:** `WiiMClient.refresh_capabilities()` and `_detect_capabilities(force=True)` re-run runtime probes when the client was constructed with cached `capabilities`. Home Assistant integrations that persist capabilities should use this when live firmware no longer matches cached metadata; see upstream [HA_INTEGRATION.md](https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_INTEGRATION.md) (firmware / capabilities note) and [API_DESIGN_PATTERNS.md](https://github.com/mjcumming/pywiim/blob/main/docs/design/API_DESIGN_PATTERNS.md) (Library Support).
