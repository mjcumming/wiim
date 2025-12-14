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

_Last reviewed against upstream on 2025-12-14 (pywiim 2.1.54 - Documentation refresh; no functional changes)._
