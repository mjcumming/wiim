# ADR 0008: Group coordinator visibility is hide and show

## Status

Accepted

## Date

2026-10-03

## Context

`media_player.*_group_coordinator` used `available = False` whenever the speaker was not a group master. Home Assistant presents `unavailable` as an error, so a solo or slave speaker looked broken. The same state also meant the speaker could not be reached, so outage alerts and "not in a group" were the same signal.

The entity was always registered. Availability was standing in for absence.

## Decision

Group membership is entity-registry visibility (`hidden_by=integration`). Reachability stays on `available`, which follows coordinator success.

- Solo or slave: entity stays available, integration hides it, state is `idle`, and commands fail.
- Group master: clear an integration hide. A user hide (`hidden_by=user`) is left alone.
- Failed poll: do not change visibility. The entity is `unavailable`.
- The coordinator does not copy the physical player's playback while it is not master.

New entities start hidden (`entity_registry_visible_default = False`).

## Consequences

### Positive

- `unavailable` on the coordinator means the speaker cannot be reached.
- Default device pages and entity pickers show the coordinator only while it is master.

### Negative / risks

- Breaking for automations that used `unavailable` on `*_group_coordinator` as "not in a group". Use `sensor.*_multiroom_role` or `group_status`.
- Hide does not remove a dashboard card that names the entity. That card shows `idle` instead of `unavailable`.
- Forming a group while idle does not change state, so a state trigger does not fire.
- Service calls reach the entity while it is hidden. They fail with an error instead of Home Assistant's unavailable rejection.

## Notes

See the 1.0.105 changelog entry.
