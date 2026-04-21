# ADR 0006: Use pywiim capability flags only — no parallel “capability” logic in the integration

## Status

Accepted (operational detail expanded in [ADR 0007](0007-capability-gating-strict-contract.md))

## Date

2026-04-20

## Context

Home Assistant entities (switches, numbers, selects, etc.) must be created and gated consistently. **pywiim** already exposes what the device can do via **`Player.supports_*`** and the underlying **`client.capabilities`** mapping populated by the library (see pywiim’s capability detection and refresh paths).

Duplicating or second-guessing that information inside `custom_components/wiim`—for example inferring support from unrelated state, hard-coding model lists, or issuing ad-hoc HTTP/probes from the integration—creates drift with pywiim, false negatives/positives, and bugs that are fixed in the wrong layer (see [ADR 0001](0001-thin-glue-layer.md)).

## Decision

The integration **must** treat **pywiim’s published capability API as the single source of truth** for whether a feature exists on a given player:

- Prefer **`coordinator.player.supports_<feature>`** (and equivalent documented pywiim properties) when deciding whether to register an entity or expose a service.
- **Do not** implement parallel “capability detection” in the integration (raw requests, model string switches, heuristics on unrelated attributes) when pywiim already exposes or should expose a `supports_*` flag.
- If pywiim’s capability is wrong, missing, or set too late for HA: **fix or extend pywiim** and bump the bundled dependency—**not** add a long-lived workaround in the integration.

Runtime **state** (e.g. “subwoofer plugged”, current EQ band) may still be read from player state or async getters pywiim documents; that is not the same as inventing a second **support** matrix in the integration.

## Consequences

### Positive

- One place to fix wrong support detection: pywiim.
- Clearer issue triage: diagnostics + pywiim version explain entity visibility.
- Aligns with the thin glue layer ([ADR 0001](0001-thin-glue-layer.md)).

### Negative / risks

- Some user-visible fixes require a **pywiim release** and `pywiim-version.txt` bump before the integration can improve.

## Notes

- If a needed **`supports_*`** does not exist in pywiim yet, add it there (with tests) rather than encoding the rule in HA.
- Related upstream cleanup (capability probes living in pywiim’s detector rather than scattered modules) is **pywiim’s** responsibility; this ADR binds **this repo** to consume the result correctly.
