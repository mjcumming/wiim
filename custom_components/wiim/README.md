# WiiM / LinkPlay Integration for Home Assistant

`custom_components/wiim` turns WiiM (and many LinkPlay-based) streamers into `media_player` entities in Home Assistant. A virtual **group player** keeps multi-room setups in sync and offers one-stop volume and transport control.

---

## Highlights

• _Broad feature coverage_ – playback control, presets, equaliser, grouping, diagnostics.
• _No extra libraries_ – uses `aiohttp`, which ships with Home Assistant.
• _Responsive UI_ – async polling adapts between 1–10 s depending on activity.
• _Multi-room support_ – master / guest roles, per-speaker volume & mute, virtual group player.
• _Standard HA patterns_ – Config Flow, Options Flow, helpers (`number`, `button`, …) and services.

---

## Feature Matrix

| Category        | Details                                                                                                                                        |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Transport**   | Play / Pause / Stop / Next / Previous · seek/position slider · standby toggle                                                                  |
| **Volume**      | Absolute 0–100 % · configurable volume step (per-device) · mute toggle · group-wide volume levelling                                           |
| **Equaliser**   | Enable / disable EQ · select preset · 10-band custom curve (-12 dB … +12 dB)                                                                   |
| **Presets**     | Front-panel preset keys 1-6 via `play_preset` service                                                                                          |
| **Metadata**    | Title · Artist · Album · Cover art · Position · Shuffle / Repeat · Streaming service (Spotify, Tidal, …)                                       |
| **Discovery**   | SSDP/UPnP (`MediaRenderer:1`) · Zeroconf `_linkplay._tcp` · automatic re-import of existing LinkPlay groups                                    |
| **Multi-room**  | Create new group · Join / Leave any LinkPlay master · Virtual **Group Player** entity · Attributes: `group_members`, `group_role`, `master_ip` |
| **Entities**    | `media_player` (device) · `media_player` (group) · `sensor.group_role` · `number` (poll interval, volume step) · `button` (reboot, sync-time)  |
| **Services**    | `media_player.play_preset` · `media_player.toggle_power` · `wiim.reboot_device` · `wiim.sync_time`                                             |
| **Diagnostics** | Reboot, clock sync, Wi-Fi RSSI / channel sensors _(coming soon)_                                                                               |
| **Config**      | Poll interval (1-60 s) · Volume step (1-50 %) via Options Flow                                                                                 |

---

## Multi-room 101

WiiM (and generic LinkPlay) speakers can form synchronous groups. This integration mirrors that model with **one virtual group entity per master**.

🔹 **Master** – the speaker that originates the audio stream.
🔹 **Guest** – speakers that receive audio from the master.

When a master with guests is detected, the integration instantly creates `media_player.<group_name> (Group)`:

• **Playback controls** (play/pause/next/prev) map _only_ to the master – exactly like the physical remote.
• **Group volume** adjusts members relatively, preserving their offsets.
• **Mute** toggles every member; the group is reported as muted only when _all_ members are muted.
• **Attributes** expose per-member volume, mute, and IP, so you can build advanced Lovelace cards.

Because every member keeps its own device entity you can still fine-tune individual speakers while using the group.

---

## Installation

### Via HACS (Recommended)

1. In HACS → _Custom Repositories_ add `https://github.com/yourusername/ha-wiim` as type _Integration_.
2. Search for **"WiiM Audio (LinkPlay)"** and click _Install_.
3. Restart Home Assistant.

### Manual Copy

1. Extract / clone this repo.
2. Copy the folder `custom_components/wiim` into `<config>/custom_components/` on your HA server.
3. Restart Home Assistant.

---

## Configuration & Options

1. Open _Settings → Devices & Services_.
2. Devices are auto-discovered; if none appear, click **Add Integration** → search _WiiM Audio (LinkPlay)_ and enter the speaker's IP.
3. Tick **Enable multi-room import** if you want existing LinkPlay groups to appear instantly.
4. After setup, click **Configure** on the integration tile to adjust:
   • _Polling interval_ (default 5 s)
   • _Volume step_ (default 5 %)

Changes apply immediately – no restart required.

---

## Provided Entities

| Platform       | Entity ID example                        | Notes                                        |
| -------------- | ---------------------------------------- | -------------------------------------------- |
| `media_player` | `media_player.living_room_speaker`       | One per device                               |
| `media_player` | `media_player.downstairs_group (Group)`  | Virtual entity for each master with ≥1 guest |
| `sensor`       | `sensor.living_room_speaker_group_role`  | `solo`, `master`, or `guest`                 |
| `number`       | `number.living_room_speaker_volume_step` | 1–50 % increment                             |
| `button`       | `button.living_room_speaker_reboot`      | Soft-reboot device                           |

---

## Home Assistant Services

| Service                     | Payload example                                        | Description              |
| --------------------------- | ------------------------------------------------------ | ------------------------ |
| `media_player.play_preset`  | `{ "entity_id": "media_player.kitchen", "preset": 3 }` | Press preset key 1-6     |
| `media_player.toggle_power` | `{ "entity_id": "media_player.kitchen" }`              | Standby ↔ On             |
| `wiim.reboot_device`        | `{ "entity_id": "media_player.kitchen" }`              | Reboot speaker           |
| `wiim.sync_time`            | `{ "entity_id": "media_player.kitchen" }`              | Sync speaker clock to HA |

The standard `media_player.join` / `unjoin` services work out of the box for grouping.

---

## FAQ

**Playback lags behind UI by a few seconds**
➡️ Increase the _poll interval_ in Options or check your Wi-Fi quality.

**Group volume slider jumps unpredictably**
➡️ Remember the group sets members _relatively_. If one speaker is at 100 %, increasing group volume won't raise others beyond that.

**A guest device shows `unavailable`**
➡️ The master is offline or the network blocked mDNS. Power-cycle the master or re-join the group.

For advanced troubleshooting enable debug logging:

```yaml
logger:
  default: warning
  logs:
    custom_components.wiim: debug
```

---

## Contributing

Pull requests are welcome! Make sure your code is formatted with `black` (120 cols), linted with `ruff`, and that all tests pass (`pytest -q`).

---

© 2025 WiiM Custom Integration Project – MIT License
