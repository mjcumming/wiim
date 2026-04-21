# ADR 0005: Group slave `media_player` entities advertise full media features

## Status

Accepted

## Date

2026-04-20

## Context

When a WiiM is a **slave** in a multiroom group, LinkPlay / WiiM firmware may **remove that device from the group** if notification-style or URL playback is started **on the slave’s own HTTP API** rather than through the group/master path.

Historically, the integration hid `PLAY_MEDIA`, `BROWSE_MEDIA`, `MEDIA_ANNOUNCE`, and related bits from slaves in `_update_supported_features()` to reduce accidental group breaks and to steer TTS at the master or `*_group_coordinator`.

That approach collides with **ecosystem consumers** (for example Music Assistant’s `hass_players` provider) that treat `MediaPlayerEntityFeature.PLAY_MEDIA` in `supported_features` as a gate for “is this a usable HA media player,” causing slave entities to disappear from those UIs after grouping ([issue #223](https://github.com/mjcumming/wiim/issues/223)).

## Decision

**Slaves use the same `supported_features` rules as solo/master players** for:

- `PLAY_MEDIA`, `BROWSE_MEDIA`, `MEDIA_ANNOUNCE`, `SELECT_SOURCE`, `CLEAR_PLAYLIST`
- `MEDIA_ENQUEUE` when `_has_queue_support()` is true

We **do not** strip these bits solely because `player.is_slave` is true.

Users and automations that need a **stable grouped experience** (especially TTS and announcements) should still prefer the **master** or **`media_player.*_group_coordinator`**; targeting a slave remains valid but may change group membership per firmware.

## Consequences

### Positive

- Third-party integrations that filter on `PLAY_MEDIA` can register and use slave entities.
- One consistent capability model; fewer “mystery unsupported” states for advanced users.

### Negative / risks

- Easier to trigger firmware behavior that **unjoins** a slave if `play_media` / announce is sent at the slave entity.
- Documentation must spell out the trade-off clearly (see [../TTS_GUIDE.md](../TTS_GUIDE.md)).

## Notes

Transport commands (play/pause/seek/next/previous for many paths) are still routed to the master via pywiim where applicable; **URL / notification playback** uses the entity’s player HTTP client. Supersedes the “hide `PLAY_MEDIA` on slaves” approach documented in changelog **1.0.76** (2026-03-30).
