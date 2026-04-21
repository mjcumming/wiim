# ADR 0002: Split automated tests and manual / device scripts

## Status

Accepted

## Date

2025-11-30

## Context

Fast CI needs pytest-only tests; real hardware and long-running scenarios need a separate place so contributors know what to run locally vs in CI.

First captured in `docs/ARCHITECTURE.md` (**2025-11-28**); file **added to git** **2025-11-30** (`43fe79e`).

## Decision

- **`tests/`** — Automated pytest suite; must run in CI and stay fast where possible.
- **`scripts/`** — Manual or real-device validation, longer scenarios, and tooling that is not part of the default pytest collection.

## Consequences

### Positive

- Clear expectations for PRs vs optional device validation.

### Negative / risks

- Two places to look for “a test”; document new checks in the right tree.

## Notes

See [../TESTING-CONSOLIDATED.md](../TESTING-CONSOLIDATED.md).
