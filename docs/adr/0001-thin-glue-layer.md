# ADR 0001: Thin glue layer between Home Assistant and pywiim

## Status

Accepted

## Date

2025-11-30

## Context

The integration must stay maintainable as device behavior grows in **pywiim**. Duplicating protocol logic in `custom_components/wiim` increases drift and bug surface.

The decision was first captured in `docs/ARCHITECTURE.md` with date **2025-11-28**; that file was **added to git** on **2025-11-30** (`43fe79e`).

## Decision

Treat this repository as a **thin glue layer**: create HA entities, read state from pywiim, and call pywiim APIs. **Do not** implement device communication, multiroom protocol details, or long-lived state machines in the integration when they belong in the library.

## Consequences

### Positive

- Clear ownership: pywiim is the place to fix device bugs once.
- Easier testing: integration tests focus on HA wiring, not firmware.

### Negative / risks

- Some fixes feel “slower” because they require a pywiim release and dependency bump.

## Notes

See [../ARCHITECTURE.md](../ARCHITECTURE.md) (Core principles).
