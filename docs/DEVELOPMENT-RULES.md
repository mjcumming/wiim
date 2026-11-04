# Development rules and guidelines

## Rules map (read this first)

WiiM is a Home Assistant integration built on the separately maintained
[pywiim](https://github.com/mjcumming/pywiim) library. This document covers
the shared development and release principles. See
[ARCHITECTURE.md](ARCHITECTURE.md) for data flow,
[CONTRIBUTING.md](../CONTRIBUTING.md) for the contribution checklist, and
[docs/adr/](adr/README.md) for durable decisions.

Use these rules with judgment. Keep changes focused, describe the problem in
the PR, and link an existing issue when useful. Ask when a decision needs
information or authorization that is unavailable; routine implementation
choices do not require a separate issue, discussion, or design sign-off.
Explicit maintainer instructions take precedence over a guideline.

## Code ownership

### Rule 2b: Fix in the right repository (integration vs pywiim)

| WiiM integration | pywiim |
| --- | --- |
| Home Assistant entities, services, coordinator, config flow, registry, and translations | Device communication, protocol parsing, capabilities, `Player`, `Group`, and device state |

Keep this integration a thin adapter over pywiim. Use Home Assistant public
APIs and do not modify Home Assistant core or duplicate protocol handling
here. Refer to pywiim's
[integration guides](https://github.com/mjcumming/pywiim/tree/main/docs/integration)
instead of maintaining duplicate copies.

### Rule 2c: Cross-repository pywiim work (agents / automation)

The sibling `../pywiim` checkout may be edited for library work. Keep the
repositories, commits, PRs, and releases separate; do not vendor the library.
Preserve unrelated work in both checkouts and use separate worktrees when
needed.

When an integration change needs a new library version:

1. Test, review, publish, and verify the pywiim release first.
2. Update `custom_components/wiim/pywiim-version.txt` and run
   `python scripts/sync-pywiim-version.py --write` to synchronize the manifest
   and development requirement.
3. Test the integration against the published package and document any
   user-visible changes.

An unrelated WiiM change that works with its existing published pin need not
wait for a separate pywiim fix. Never release an integration that depends on
an unpublished library version. Do not make an empty product release for a
rules-only or documentation-only change.

## Implementation and validation

- Make the smallest change that fixes the problem in its owning layer.
- Use type hints, actionable errors, contextual logging, and existing Home
  Assistant and pywiim patterns. Keep code clear and cohesive; file or
  function length alone is not a reason to split it.
- Add focused tests for changed behavior and meaningful failure paths. Bug
  fixes should have a regression test when practical. Do not add tests that
  merely restate the implementation.
- Run relevant tests during development. GitHub CI is the authoritative merge
  gate. `bash scripts/check-before-push.sh` is an optional local preflight;
  it includes a patch-coverage check but does not run every GitHub action.
  Coverage settings are in [codecov.yml](../codecov.yml).
- Test on a real device when the change depends on device or firmware
  behavior and a suitable device is available. Preserve its settings and
  record model and firmware. State clearly when real-device validation was
  not performed.
- Review changes in proportion to risk and resolve actionable feedback.
  A maintainer may review routine work themselves; request independent review
  when it would help or when requested. Do not claim an independent review
  occurred when it did not.

Preserve existing local Git hook configuration. Local hooks are optional and
should not silently rewrite unrelated files; do not run the full test suite
multiple times merely because separate tools offer the same check.

### Rule 8: ADRs for invariants learned the hard way

Add or update a numbered [ADR](adr/README.md) for a durable, non-obvious
contract or trade-off that future changes could accidentally reverse. Use
`Proposed` while a decision is in review when appropriate. Most fixes need
tests and, when user-visible, a changelog entry; they do not need a new ADR.

## Release

Put a meaningful changelog entry and manifest version in the reviewed PR.
Merging a version change to `main` triggers the
[automatic release workflow](../.github/workflows/auto-release.yml), which
validates HACS and waits for CI on that commit. Verify the workflow and
published release; do not describe a release as installed or device-tested
without that evidence.

Update existing user and developer documentation when behavior changes. Keep
temporary progress notes out of the permanent documentation.
