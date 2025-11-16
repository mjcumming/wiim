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

## Working offline or auditing changes

If you truly need a local snapshot (for example while traveling without internet), fetch it ad hoc and avoid committing the downloaded copy:

```bash
curl -L https://raw.githubusercontent.com/mjcumming/pywiim/main/docs/integration/HA_INTEGRATION.md \
  -o /tmp/ha_integration_guide.md
```

Review it locally, then delete the temporary file when done. Should we ever need to vendor a copy again, make sure to document the source commit hash in the PR description so reviewers know which upstream version was imported.

_Last reviewed against upstream on 2025-11-16._
