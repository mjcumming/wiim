# Contributing to WiiM

The [development rules](docs/DEVELOPMENT-RULES.md) explain where code belongs
and how this integration works with pywiim. The
[architecture guide](docs/ARCHITECTURE.md) describes its components.

## Working on a change

1. Make a focused branch and describe the problem and solution in the PR.
   Link an existing issue when useful.
2. Put Home Assistant behavior in this repository and device/protocol behavior
   in [pywiim](https://github.com/mjcumming/pywiim). Preserve unrelated local
   changes and stage only intended files.
3. Add meaningful regression or behavior tests and run the relevant checks.
   CI runs the full automated integration checks; local pre-commit hooks and
   `bash scripts/check-before-push.sh` are optional early feedback.
4. Review the change in proportion to its risk and address actionable
   feedback. Request independent review when it would help or when requested.
5. Update user docs and the changelog when behavior changes. Add or update an
   [ADR](docs/adr/README.md) only for a durable, non-obvious decision.

Real-device testing is valuable when the behavior depends on a specific
device or firmware and suitable hardware is available. Record what was tested
and note when hardware validation was not performed.

For releases, prepare a manifest version and changelog entry in the PR. Once
the PR is merged, GitHub Actions validates and publishes the release. If the
change needs a new pywiim version, publish and verify that version first; see
[cross-repository work](docs/DEVELOPMENT-RULES.md#rule-2c-cross-repository-pywiim-work-agents--automation).

When reporting a problem, include reproduction steps, expected and actual
behavior, device model and firmware when relevant, and redacted diagnostics.
