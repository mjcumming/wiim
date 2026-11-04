# ADR 0009: Preserve EQ selectors and distinguish state from presets

## Status

Proposed

## Date

2026-11-03

## Context

EQ state can differ by input, and the active graphic curve may be unsaved. A single `Off` or `Flat` symptom can therefore have different causes. The Audio Pro A10 reported a valid preset list that disappeared before it reached Home Assistant ([#187](https://github.com/mjcumming/wiim/issues/187)); a WiiM Pro Plus reported unsaved bands with an empty preset name ([#302](https://github.com/mjcumming/wiim/issues/302)). The PEQ selector also needed an inactive state and a way to turn PEQ off ([#301](https://github.com/mjcumming/wiim/issues/301)).

Existing automations use the separate graphic and parametric selectors. Combining them would require an entity and option migration that is unnecessary for these fixes.

On a tested WiiM Pro, while a saved PEQ profile was active, `EQGetBand` still named the prior graphic preset with graphic EQ off; the PEQ-specific read reported the active PEQ name. Neither response alone describes both selectors.

## Decision

- Keep the existing graphic and PEQ selector identities and saved-preset option names. A combined selector requires a separate design and migration plan.
- Represent unknown state as unknown. Graphic `Off` means graphic EQ is inactive; PEQ may still be active. PEQ `Off` means PEQ is inactive. Do not infer full bypass unless both relevant states are known to be inactive.
- Show an active unsaved graphic curve as `Custom`, and show a device-reported active name even if it is missing from the preset list. These are state labels, not promises that they can be loaded; selecting an observed-only label does not send a preset command.
- Provide a PEQ disable option even when there are no saved presets. If `Off` or the disable label is already a saved preset name, use a distinct disable label so the saved option remains loadable.
- Use pywiim's capability flags, current-input state, and command methods. pywiim owns device response validation, source tracking, readback, and reconciliation; HA does not infer device protocol support or force a coordinator refresh after a command. Yamaha sound programs require separate device evidence and must not be exposed as generic WiiM presets merely because the device uses Linkplay.

## Consequences

### Positive

- Existing selector entities and saved-preset automations remain usable while state can distinguish inactive, custom, and unknown.
- Device-specific behavior has one owner in pywiim, and both selectors update from its reconciled state.

### Negative / risks

- Two selectors require the user to understand that only one EQ type can be active on the WiiM devices where that behavior has been observed.
- An observed-only option cannot be reloaded until the device exposes it as a saved preset. A disable label can vary when saved preset names collide.

## Notes

- For a device reporting WiiM-style EQ, capture redacted, read-only `EQGetBand` and `EQGetList` responses with the active source and playback status. Compare inputs separately, then trace the list through transport validation, the `Player` cache, capability gating, and HA options, including retry after a failed read.
- Test app changes, startup/reload, source changes, failed reads, switching both EQ types, and persistence beyond two configuration polls. For live tests, record and restore the prior device state where possible and report any state that could not be restored. Report real-device confirmation separately from fixture-based tests.
- The library's [ADR 017](https://github.com/mjcumming/pywiim/blob/main/docs/design/adr/017-eq-off-and-dynamic-preset-resolution.md), with amendments proposed in [pywiim PR #37](https://github.com/mjcumming/pywiim/pull/37), records the protocol and state contract. The existing custom-band service uses pywiim's verified graphic writer after the dependency update; no new HA controls are added for PEQ editing.
- For this change, publish and verify the pywiim version containing the required API first, then pin that published version and validate the integration against it before release. General cross-repository rules remain in [Rule 2c](../DEVELOPMENT-RULES.md#rule-2c-cross-repository-pywiim-work-agents--automation).
