# ADR 0003: Test-driven development for regressions

## Status

Accepted

## Date

2025-11-30

## Context

Regressions in media, multiroom, and coordinator behavior are expensive to catch without automated tests.

First captured in `docs/ARCHITECTURE.md` (**2025-11-28**); file **added to git** **2025-11-30** (`43fe79e`).

## Decision

For bug fixes and non-trivial behavior changes, prefer **TDD**: add or extend a failing test that reproduces the issue, then fix until green.

## Consequences

### Positive

- Prevents the same class of bug from returning silently.

### Negative / risks

- Slightly higher upfront cost for small fixes; skip only when a test is genuinely impractical (then document why in the PR).

## Notes

See [../DEVELOPMENT-RULES.md](../DEVELOPMENT-RULES.md) and [../TESTING-CONSOLIDATED.md](../TESTING-CONSOLIDATED.md).
