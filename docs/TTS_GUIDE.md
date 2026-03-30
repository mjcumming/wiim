# WiiM TTS (Text-to-Speech) Guide

The WiiM integration supports TTS announcements via `media_player.play_media` with `announce: true` and via `tts.speak`. For **multiroom groups**, target the **master** or **group coordinator** entity so every grouped speaker hears the announcement; **slave** entities cannot run these services (see [Group behavior](#group-behavior-master-slave-coordinator) below).

## Developer Tools / Actions (correct payload)

When calling **Developer tools → Actions → media_player.play_media**, use a **flat** `data` payload. Do **not** nest under `media`:

**Correct:**

```yaml
target:
  entity_id: media_player.master_bedroom
data:
  media_content_id: "media-source://tts/tts.google_translate_en_com?message=Testing+from+the+UI"
  media_content_type: music
  announce: true
```

**Wrong (will not work):** nesting under `media`:

```yaml
data:
  announce: true
  media:
    media_content_id: media-source://tts/...
    media_content_type: music
```

## Basic Usage

### Simple TTS Announcement

```yaml
service: media_player.play_media
target:
  entity_id: media_player.living_room
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Hello, this is a test announcement"
  announce: true
```

### TTS with Custom Volume

```yaml
service: media_player.play_media
target:
  entity_id: media_player.living_room
data:
  media_content_type: music
  media_content_id: "media-source://tts/google_translate?message=Volume test"
  announce: true
  extra:
    tts_volume: 75 # 75% volume
```

## Group behavior (master, slave, coordinator)

### What happens on the device

- **Solo** speaker: `media_player.play_media` / `tts.speak` with `announce: true` plays the notification on that unit only.
- **Master** in a multiroom group: the same announcement is played through the **group audio path**. Slaves follow the master, so **they will play the announcement too** (it is still a URL fetched and rendered as part of grouped playback—you do not need to target each slave).
- **Slave** speaker: on LinkPlay / WiiM firmware, starting a **notification-style URL on the slave itself** causes the device to **leave the group**. To avoid breaking groups by accident, Home Assistant **does not** expose `media_player.play_media` (or `announce`) on **slave** `media_player` entities—those actions are only available on **solo**, **master**, and **group coordinator** entities.

### What to target

| Your goal                         | Target entity                                                                 |
| --------------------------------- | ----------------------------------------------------------------------------- |
| Announce to the **whole group**   | The **master** `media_player` for that group, or `media_player.*_group_coordinator` |
| Announce to one **ungrouped** box | That speaker’s `media_player` while it is **solo**                          |
| Slave `media_player`              | **Do not use** for `play_media` / `tts.speak` / announce — use master or coordinator instead |

### Example: group-wide TTS (recommended)

```yaml
# Option A — group coordinator (when the group exists)
service: media_player.play_media
target:
  entity_id: media_player.living_room_group_coordinator
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Dinner is ready"
  announce: true

# Option B — master speaker entity (same effective outcome for announcements)
service: media_player.play_media
target:
  entity_id: media_player.living_room  # Master, not a slave
data:
  media_content_type: music
  media_content_id: "media-source://tts?message=Dinner is ready"
  announce: true
```

### `wiim.play_notification`

Use a **direct HTTP URL** the device can fetch. For a **grouped** home, target the **master** or **group coordinator** so the announcement follows the same rule as above. Avoid pushing notification URLs at a **slave** player if you want the group to stay intact.

## Volume Control

### Default TTS Volume

- **70% of current volume** (minimum 30%)
- Automatically adjusted for optimal TTS clarity

### Custom TTS Volume

```yaml
service: media_player.play_media
target:
  entity_id: media_player.living_room
data:
  media_content_type: music
  media_content_id: "media-source://tts/google_translate?message=Custom volume test"
  announce: true
  extra:
    tts_volume: 80 # 80% volume (0-100)
```

## State Management

TTS announcements automatically:

1. **Save current state** (volume, mute, playback)
2. **Pause current playback** (if playing)
3. **Set TTS volume**
4. **Play TTS audio**
5. **Wait for completion**
6. **Restore original state**

## Error handling

### Slave `media_player` and `tts.speak`

Slave entities **do not** advertise support for `media_player.play_media`, so **`tts.speak`** and **Actions → play_media** with `announce: true` are not valid targets for a slave. That is intentional: on firmware, playing a notification **directly on a slave** would **remove it from the group**. Use the **master** or **`*_group_coordinator`** entity instead; the group will still hear the announcement when you target the master path.

### Network issues

TTS will fail gracefully with network issues and restore original state.

## Integration with TTS Services

### Google Cloud TTS

```yaml
service: tts.cloud_say
data:
  entity_id: media_player.living_room
  message: "Hello from Google Cloud TTS"
```

### Local TTS

```yaml
service: tts.picotts_say
data:
  entity_id: media_player.living_room
  message: "Hello from local TTS"
```

## Automation Examples

### Doorbell Announcement

```yaml
automation:
  - alias: "Doorbell TTS"
    trigger:
      platform: state
      entity_id: binary_sensor.doorbell
      to: "on"
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.living_room_group_coordinator
        data:
          media_content_type: music
          media_content_id: "media-source://tts/google_translate?message=Someone is at the door"
          announce: true
```

### Weather Alert

```yaml
automation:
  - alias: "Weather Alert TTS"
    trigger:
      platform: state
      entity_id: sensor.weather_alert
      to: "severe"
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.living_room
        data:
          media_content_type: music
          media_content_id: "media-source://tts/google_translate?message=Severe weather warning"
          announce: true
          extra:
            tts_volume: 90
```

## Debugging TTS (action not working)

Follow these steps to see where it fails.

### 1. Turn on debug logging

In **Settings → System → Logging**, set:

- **custom_components.wiim** → **Debug**
- (Optional) **homeassistant.components.tts** → **Debug**
- (Optional) **homeassistant.components.media_source** → **Debug**

Or in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.wiim: debug
```

Restart HA, then trigger the action again.

### 2. Trigger the action and read the logs

Use **Developer tools → Actions → media_player.play_media** with:

```yaml
target:
  entity_id: media_player.master_bedroom # use your WiiM entity_id
data:
  media_content_id: "media-source://tts/tts.google_translate_en_com?message=Testing+from+the+UI"
  media_content_type: music
  announce: true
```

Click **Perform action**. Then open **Developer tools → Logs** (or Settings → System → Logs) and look for lines from the WiiM integration.

**What you should see when it works:**

- `[Master Bedroom] Resolving media source: media-source://tts/...`
- `[Master Bedroom] Resolved media source - url: http://..., mime_type: ...`
- `[Master Bedroom] Playing notification via device firmware: http://...`

**If you see an error instead:**

| Log message                                                             | Cause                                             | What to do                                                                                                                                                                                                       |
| ----------------------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| (no WiiM lines at all)                                                  | Service not reaching the entity, or wrong payload | Use flat `data` (no `media:` wrapper). Check **States** for `media_player.master_bedroom` and that it is **available**.                                                                                          |
| `Failed to resolve media source` / TTS error                            | TTS engine or media source problem                | Check **Settings → Voice assistants → Text-to-speech**: the engine in the URL (e.g. `tts.google_translate_en_com`) must exist. Test TTS from Media or another player.                                            |
| `Media source resolved to empty URL`                                    | TTS returned no URL                               | Same as above: fix TTS engine / config.                                                                                                                                                                          |
| `Cannot build playable URL` / `NoURLAvailableError`                     | HA has no Internal URL                            | **Settings → System → Network**: set **Internal URL** to your HA LAN address (e.g. `http://192.168.1.x:8123`).                                                                                                   |
| Action / `tts.speak` “not supported” for entity                         | Target is a **group slave**                       | Use the **master** `media_player` or **`media_player.*_group_coordinator`**. Slaves intentionally cannot run `play_media` / announce (would unjoin the group on device).                                        |
| `Playing notification via device firmware: http://...` but **no sound** | WiiM cannot reach the URL or gets 401             | Internal URL must be the IP the WiiM can reach. Open that `http://...` URL in a browser on the same network; if it asks for login, the WiiM will get 401 (see “No audio even when the URL looks correct” below). |

### 3. Check the entity and payload

- **Developer tools → States**: search for `media_player.master_bedroom` (or your WiiM entity). State should not be `unavailable`.
- Prefer **flat** `data` in Actions (no `media:` wrapper). Example:

```yaml
target:
  entity_id: media_player.master_bedroom
data:
  media_content_id: "media-source://tts/tts.google_translate_en_com?message=Test"
  media_content_type: music
  announce: true
```

### 4. Confirm Internal URL (no sound / URL unreachable)

- **Settings → System → Network** → **Internal URL** = `http://YOUR_HA_IP:8123` (same LAN as the WiiM).
- If Internal URL is empty or `localhost`, the TTS URL sent to the WiiM will be wrong and you get no sound.

### 5. Test TTS and the URL by hand

- In **Media** (or another media player card), try playing the same TTS source; if that fails, fix TTS first.
- After a successful action, copy the URL from the log line `Playing notification via device firmware: <url>`. Open `<url>` in a browser on a device on the same LAN. If you get a login page or 401, the WiiM will too (see next section).

---

## Troubleshooting

### TTS Not Working

1. **Check speaker role**: Ensure the speaker is available and has the correct role
2. **Verify TTS engine**: Make sure your TTS engine is working
3. **Check logs**: Look for TTS-related errors in the logs

### No audio even when the URL looks correct (401 Unauthorized)

If TTS works in the browser but the speaker plays nothing, the device is likely getting **401 Unauthorized** when it fetches the TTS proxy URL. Browsers work because of cookies; the WiiM device has no cookies.

**This is not an integration bug.** The integration resolves media sources to a playable URL and sends that URL to the device. The device then fetches the URL; if Home Assistant requires authentication for that URL, the request fails.

**What to do:**

1. Check with: `curl -I http://HA_IP:8123/api/tts_proxy/...` (if you see 401, the URL is protected).
2. Configure Home Assistant so the TTS proxy (or that URL) is reachable by the device without auth:
   - **Internal URL** in HA (Settings → System → Network) so the device uses the internal URL.
   - **Trusted networks** or **allowlist_unauthenticated_bind_ip** in your HTTP configuration so requests from your LAN (or the device’s IP) are allowed without auth.

See [Home Assistant HTTP documentation](https://www.home-assistant.io/docs/configuration/http/) for details.

### TTS in a dev container

When Home Assistant runs in a **dev container** (e.g. VS Code/Cursor with `core` repo and `--network=host`):

- **Port 8123** is exposed and HA listens on the host, so the WiiM on your LAN can reach HA at **your dev machine’s LAN IP:8123** (e.g. `http://192.168.6.x:8123`).
- TTS often still fails because HA does **not** know that LAN IP by default, so the TTS proxy URL it generates may use `localhost` or a hostname the WiiM cannot reach.

**What to do:**

1. In HA go to **Settings → System → Network** and set **Internal URL** to your dev machine’s LAN address, e.g. `http://192.168.6.XXX:8123` (replace with your host’s IP). That makes HA use this URL when generating the TTS proxy link the WiiM will fetch.
2. Add **trusted_networks** (or equivalent) in `configuration.yaml` under `http:` so requests from your LAN are allowed without auth; otherwise the device may get **401** when fetching the TTS URL. See [Home Assistant HTTP documentation](https://www.home-assistant.io/docs/configuration/http/).

After that, TTS can work from a dev container the same way as on a normal HA install.

**Dev container on WSL on Windows:** Use your **Windows PC's LAN IP** as Internal URL (not the router). On Windows run `ipconfig` and use the IPv4 Address of your Ethernet or Wi-Fi adapter (e.g. `192.168.1.100`). If the WiiM still cannot connect, allow inbound TCP port **8123** in Windows Firewall (Windows Security → Firewall → Advanced, or Admin PowerShell: `New-NetFirewallRule -DisplayName "HA 8123" -Direction Inbound -LocalPort 8123 -Protocol TCP -Action Allow`).

### Spotify Connect: announcements may not interrupt

When the device is used as a **Spotify Connect** target, the firmware may not support interrupting playback for announcements. If you hear no TTS while Spotify is playing, that is a **device/firmware limitation**, not an integration bug. The integration cannot fix it. Use another source (e.g. WiFi) for reliable TTS, or check with WiiM for firmware updates that add this behavior.

### Group Issues

1. **Verify group status**: Check that the group is active
2. **Check master-slave relationship**: Ensure slaves have a valid coordinator
3. **Test individual speakers**: Try TTS on individual speakers first

### Volume Issues

1. **Check current volume**: TTS volume is based on current speaker volume
2. **Verify TTS volume setting**: Custom TTS volume should be 0-100
3. **Test volume restoration**: Original volume should be restored after TTS

## Technical Details

### Supported TTS Engines

- All Home Assistant TTS engines
- Google Cloud TTS
- Local TTS engines (picoTTS, etc.)
- Custom TTS engines

### Media Source Format

TTS uses the standard Home Assistant media source format. The path must include the TTS engine name:

```
media-source://tts/<engine>?message=<text>&language=<lang>
```

Example: `media-source://tts/google_translate?message=Hello` (replace `google_translate` with your configured TTS engine).

### Timeout

TTS completion detection has a 30-second timeout by default.

### State Restoration

- Volume and mute state are always restored
- Playback state is conditionally restored (only if it was playing before TTS)

### WiiM Device Limitations: No playPromptUrl Support

**WiiM firmware does not support the `playPromptUrl` announcement endpoint.** This command exists in some Arylic/Linkplay documentation but returns "unknown command" on WiiM devices. The official WiiM HTTP API (v1.2) and the wiim-httpapi OpenAPI spec do not include `playPromptUrl`.

**How the integration works instead:** TTS announcements use `setPlayerCmd:play:{url}` to play the TTS URL as normal playback. This means:

- **TTS replaces current content** — Unlike devices with true announcement support, there is no ducking or interruption of music; the TTS plays as the new track.
- **Network source required** — The WiiM must be on Network (WiFi) source for URL playback; the integration switches to Network temporarily if needed.
- **URL must be reachable** — The TTS proxy URL (e.g. `http://HA_IP:8123/api/tts_proxy/...`) must be reachable from the WiiM on your LAN (see [Internal URL](#4-confirm-internal-url-no-sound--url-unreachable) and [401 Unauthorized](#no-audio-even-when-the-url-looks-correct-401-unauthorized)).
