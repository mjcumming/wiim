# WiiM Audio for Home Assistant

If you like WiiM Audio, [star the repository](https://github.com/mjcumming/wiim). It helps other people find it.

<p align="center">
  <img src="images/logo.png" alt="WiiM Audio logo" width="200"/>
</p>

[![GitHub Release](https://img.shields.io/github/release/mjcumming/wiim.svg)](https://github.com/mjcumming/wiim/releases)
[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/default)
[![Installs](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.wiim.total&label=installs&color=41BDF5&logo=home-assistant&cacheSeconds=3600)](https://analytics.home-assistant.io/custom_integrations.json)
[![Home Assistant](https://img.shields.io/badge/home%20assistant-2024.12.0+-blue.svg)](https://www.home-assistant.io/)
[![CI](https://img.shields.io/github/actions/workflow/status/mjcumming/wiim/tests.yaml?branch=main&label=CI)](https://github.com/mjcumming/wiim/actions/workflows/tests.yaml)
[![License](https://img.shields.io/github/license/mjcumming/wiim.svg)](LICENSE)

WiiM Audio connects WiiM streamers, amplifiers and speakers to Home Assistant, along with speakers from other brands built on the same LinkPlay platform, such as Audio Pro and Arylic. Each speaker becomes a media player. The settings you'd otherwise open the WiiM Home app for become entities you can put on a dashboard or use in an automation: the equalizer, the audio output, the subwoofer, the display and the firmware update. It talks to the speakers directly over your network and needs no cloud account.

## What you can do with it

- Group the whole house with one tap, then move the volume of every speaker with one slider while each room keeps its own level.
- Switch the amplifier to the TV input when the TV turns on, load a movie EQ preset, and go back to your music preset afterwards.
- Power an amplifier from the streamer's 12V trigger when music starts, and cut it when the music stops.
- Send the living room streamer to Bluetooth headphones at 10 pm and back to the amplifier in the morning.
- Turn the subwoofer off and dim the screen and status LED at the kids' bedtime.
- Wake up to a radio preset and fall asleep with a sleep timer.
- Put the current source, sample rate and bit depth on a dashboard, and install speaker firmware updates from Home Assistant.

## How it compares with the built-in integrations

Home Assistant includes two integrations for these speakers: [WiiM](https://www.home-assistant.io/integrations/wiim/), added in 2026.4, and [LinkPlay](https://www.home-assistant.io/integrations/linkplay/). If playback, grouping and presets are all you need, they cover that. WiiM Audio is for when you also want the rest of this table on dashboards and in automations.

The table shows what each integration's documentation lists. "Not listed" means its page doesn't mention the feature.

| | WiiM Audio | Built-in WiiM | Built-in LinkPlay |
| --- | --- | --- | --- |
| Speakers | WiiM, Audio Pro, Arylic and other LinkPlay brands | WiiM models | LinkPlay-based players |
| Media player with multiroom grouping | Yes | Yes | Yes |
| Presets | Yes | Yes | Yes |
| Audio output select | Yes | Yes | Not listed |
| Playback queue | Add, play from a position, remove and read, on speakers with a queue | Browse | Not listed |
| Equalizer, parametric EQ and RoomFit | Yes | Not listed | Not listed |
| Subwoofer, balance and channel | Yes | Not listed | Not listed |
| Sleep timer and alarms | Yes, on WiiM devices | Not listed | Not listed |
| Firmware update entity | Yes, on WiiM devices | Not listed | Not listed |
| Reboot and clock sync | Yes | Not listed | Yes |

WiiM Audio and the built-in WiiM integration share the internal name `wiim`, so only one of them runs. Once WiiM Audio is installed and Home Assistant has restarted, Home Assistant loads it in place of the built-in one, and the install dialog in Home Assistant 2026.11 and newer warns you about this.

If you've already set up speakers with the built-in WiiM integration, delete them there before you install WiiM Audio, and add them again afterwards. The two integrations identify their entities differently, so a setup carried over from one to the other can leave you with duplicate or unavailable entities. To go back, follow [Remove the integration](#remove-the-integration). The built-in LinkPlay integration has its own name and keeps running, so a speaker added to both appears twice.

## Supported speakers

| Brand | Models |
| --- | --- |
| WiiM | Mini, Pro, Pro Plus, Amp, Amp Pro, Amp Ultra, Ultra, Sound, Sound Lite |
| Audio Pro | Original, W-generation and MkII speakers, such as the Addon C10, A10, A15 and A28 |
| Arylic | Up2Stream boards and the S10+ |
| Other LinkPlay brands | Edifier MS50A, DOSS, Dayton Audio, iEast and others |

WiiM, Audio Pro and Arylic speakers each have a profile that covers how that brand's firmware behaves. Audio Pro MkII speakers need a secured connection, which the integration sets up for you. Other LinkPlay speakers are identified when you add them and use a general profile.

The hardware this has been run against, with the firmware and where each record comes from, is in [pywiim's tested devices list](https://github.com/mjcumming/pywiim/blob/main/docs/user/TESTED_DEVICES.md). The integration and the library share that one list, and it has a section on how to add your speaker.

Speakers differ in what they can do, and a firmware update can change it. When you add a speaker, the integration asks it what it supports and creates only the entities that work on it. That's why a WiiM Mini has fewer entities than a WiiM Ultra.

You need Home Assistant 2024.12.0 or newer, on the same network as the speakers.

## Install

WiiM Audio installs from the Marketplace, which is part of Home Assistant 2026.11 and newer. On older versions, use [HACS](https://hacs.xyz/). The steps are the same, with HACS in the sidebar in place of **Settings** > **Marketplace**, and **Download** in place of **Install**.

If you use the built-in WiiM integration, read [the note on switching](#how-it-compares-with-the-built-in-integrations) first.

This button opens WiiM Audio in either one. It's labelled for HACS and works in both.

[![Open WiiM Audio in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mjcumming&repository=wiim&category=integration)

1. Use the button above, or go to **Settings** > **Marketplace** and search for "WiiM Audio".
2. Select **Install**.
3. Restart Home Assistant.

To install by hand, download `wiim.zip` from the [latest release](https://github.com/mjcumming/wiim/releases/latest). In your Home Assistant configuration folder, the one that holds `configuration.yaml`, create `custom_components/wiim` and extract the zip into it. Then restart.

### Beta versions

Betas are published as GitHub pre-releases, and you only get them if you ask for them. Go to **Settings** > **Devices & services**, open the Marketplace integration (or HACS), and open the WiiM Audio device. Its **Pre-release** switch is disabled at first: enable the entity in its settings, then turn the switch on. Turn it off to stay on stable releases.

## Add your speakers

Home Assistant finds speakers on your network by itself. Go to **Settings** > **Devices & services**, where discovered speakers appear at the top of the page, and add each one.

To add a speaker yourself, select **Add integration**, search for **WiiM** and enter the speaker's IP address. Inside Home Assistant the integration is called WiiM; WiiM Audio is its name in the Marketplace and HACS. This button opens the same dialog:

[![Add WiiM to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=wiim)

Each speaker is a device of its own. A speaker that's grouped with one you've added is picked up too, and if Home Assistant can't find its address it asks you for it. If a speaker's IP address changes, open the three-dot menu of its entry, select **Reconfigure** and enter the new one. Reserving the address in your router keeps it from changing.

Select **Configure** on a speaker's entry to change its options:

| Option | Default | What it does |
| --- | --- | --- |
| Volume Step Size | 5% | How far one volume up or volume down step moves, from 1% to 50% |
| Maintenance Buttons | Off | Adds **Reboot** and **Sync Time** buttons to the device |

## Entities

| Entity | What it does | Created |
| --- | --- | --- |
| Media player | Playback, volume, source, sound mode, media browser, grouping and announcements | Always |
| Group Master media player | Controls a whole group through the speaker that leads it | Always, and hidden until the speaker leads a group |
| Audio Output Mode select | Picks the hardware output or a paired Bluetooth device | When the speaker can switch outputs |
| EQ Preset select | Off, the speaker's presets, or Custom | When the speaker has an equalizer |
| Parametric EQ Preset select | Loads a saved parametric EQ preset, or turns it off | When the speaker has parametric EQ |
| RoomFit select | Applies a saved room correction profile, or turns it off | When the speaker has a saved profile |
| Channel select | Stereo, Left, Right or Mono | When the speaker can change its output channel |
| Channel balance number | Left/right balance from -1.0 to 1.0 | When the speaker supports it |
| Subwoofer switch, Main speaker bass switch, Subwoofer Level number | Turn the subwoofer output on or off, keep bass in the main speakers, and set the subwoofer level from -15 to +15 dB | When the speaker has a subwoofer output |
| 12V trigger switch | Turns the trigger output on or off | WiiM Ultra, Pro and Pro Plus |
| DAC Filter select | Picks the digital filter used for the analog line output | When the speaker reports its filters |
| Standby Timeout select | How long the speaker stays idle before standby, from 30 seconds to 4 hours, or Never | When the speaker reports the setting |
| LED light | Turns the status LED on or off | Always |
| Display light | Turns the screen on or off and sets its brightness | WiiM Ultra, Amp Ultra and Sound |
| Firmware Update | Shows a new firmware version and installs it | WiiM devices |
| Multiroom Role sensor | Solo, Master or Slave | Always |
| Current Input sensor | The current source, including streaming services | Always |
| Diagnostic sensors | Device Status, Firmware, Bluetooth Output, Audio Quality, Sample Rate, Bit Depth and Bit Rate | Device Status and Firmware always, the others when the speaker reports them |
| WiiM Voice Remote device | A separate device linked to the speaker, with a **Volume adjustment step** select (Fine Adjustment, Small Step, Medium Step, Large Step or Quick Adjustment), a **Battery** sensor and a **Connected** sensor. A **Signal strength** sensor is there too, disabled by default. Battery, signal strength and the volume adjustment step are unavailable while the remote is not connected | When the speaker supports a remote and one is paired |
| Reboot and Sync Time buttons | Restart the speaker, or set its clock from Home Assistant | When the Maintenance Buttons option is on |

The YAML samples below are actions. Paste one into **Developer tools** > **Actions** to try it, or use it as a step in an automation or a script.

## Multiroom

Group speakers with Home Assistant's own grouping, either from the media player's dialog or with the `media_player.join` and `media_player.unjoin` actions. Groups made in the WiiM Home app show up in Home Assistant as well.

```yaml
action: media_player.join
target:
  entity_id: media_player.living_room
data:
  group_members:
    - media_player.kitchen
    - media_player.bedroom
```

The speaker you target leads the group, and its Multiroom Role sensor reads Master. The others follow it and read Slave. A speaker on its own reads Solo. Joining adds speakers to the group that's already there. To take one out, call `media_player.unjoin` on it.

Each speaker also has a group media player, `media_player.<speaker>_group_master`. It plays, pauses and skips for the whole group, mutes every member, and its volume slider moves every member while keeping the differences between them. Home Assistant hides it until its speaker leads a group, and an action sent to it at any other time fails with an error. A dashboard card that names it still shows it.

## Sound

The EQ Preset select and the media player's sound mode are the same list, so you can use whichever fits your dashboard. For your own curve, `wiim.set_eq` takes ten band values from -12 to +12 dB.

The Parametric EQ Preset and RoomFit selects load what you've saved in the WiiM Home app. Home Assistant switches between those presets and room correction profiles; creating and measuring them stays in the app.

## Sources and outputs

On WiiM devices the source list follows the WiiM Home app. An input you renamed there shows its new name, and an input you turned off there is hidden. The Current Input sensor also reports streaming services such as Spotify, so an automation can react when someone starts casting.

The Audio Output Mode select lists the outputs your model has, such as Line Out, Optical Out or Speaker Out. Bluetooth devices you've paired in the WiiM Home app appear in the same list as `BT: <name>`.

```yaml
action: select.select_option
target:
  entity_id: select.living_room_audio_output_mode
data:
  option: "BT: Bedroom Headphones"
```

## Playing media

The media browser has a **Presets** folder with the presets you saved in the WiiM Home app, next to your Home Assistant media sources. `media_player.play_media` plays a URL or anything from a media source. To play a preset from an automation:

```yaml
action: wiim.play_preset
target:
  entity_id: media_player.kitchen
data:
  preset: 1
```

On speakers with a playback queue, such as the WiiM Pro and Pro Plus, `media_player.play_media` with `enqueue: add` or `enqueue: next` adds to the queue, and the `wiim.play_queue`, `wiim.remove_from_queue` and `wiim.get_queue` actions work with it. The media player's `queue_position` and `queue_count` attributes show where playback is.

## Announcements

Any text-to-speech engine in Home Assistant can speak through a speaker. Replace `tts.home_assistant_cloud` with your own TTS entity:

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: "Someone's at the front door."
```

`media_player.play_media` with `announce: true` and `wiim.play_notification` do the same for a sound file. To reach a whole group, target the speaker that leads it or its group media player.

The speaker fetches the audio from Home Assistant over your network. If an announcement stays silent, check the local network address in **Home Assistant URL** under **Settings** > **System** > **Network**. The speaker needs an `http://` address with your Home Assistant's IP, such as `http://192.168.1.10:8123`.

The [TTS guide](docs/TTS_GUIDE.md) has more examples.

## Sleep timer and alarms

WiiM devices have a sleep timer and three alarms. This action stops the bedroom speaker in an hour. The longest timer is two hours, which is 7200 seconds.

```yaml
action: wiim.set_sleep_timer
target:
  entity_id: media_player.bedroom
data:
  sleep_time: 3600
```

`wiim.clear_sleep_timer` cancels the timer. `wiim.update_alarm` creates or changes an alarm, with its time in UTC. The [user guide](docs/user-guide.md) has an example.

## Actions

| Action | What it does |
| --- | --- |
| `wiim.play_preset` | Plays a preset saved in the WiiM Home app, by number |
| `wiim.play_url` | Plays audio from a URL, such as a radio stream or a file |
| `wiim.play_playlist` | Plays an M3U playlist from a URL |
| `wiim.play_notification` | Plays a sound from a URL as an announcement |
| `wiim.play_queue` | Starts playing the queue at a position |
| `wiim.remove_from_queue` | Removes the item at a position from the queue |
| `wiim.get_queue` | Returns the queue with title, artist, album and URL |
| `wiim.set_eq` | Sets an EQ preset or ten custom band values |
| `wiim.set_sleep_timer` | Stops playback after a number of seconds |
| `wiim.clear_sleep_timer` | Cancels the sleep timer |
| `wiim.update_alarm` | Creates or changes one of the three alarms |
| `wiim.set_channel_balance` | Sets the left/right balance |
| `wiim.scan_bluetooth` | Scans for nearby Bluetooth devices |
| `wiim.sync_time` | Sets the speaker's clock from Home Assistant |
| `wiim.reboot_device` | Restarts the speaker |

The [user guide](docs/user-guide.md) has the fields and an example for each action, and the [automation cookbook](docs/automation-cookbook.md) has longer automations.

## How it stays in sync

A speaker tells Home Assistant when its play state, volume or track changes, so those show up right away. The integration also asks every speaker for its state on a schedule: about once a second while it's playing and every 5 seconds when it's idle, with older LinkPlay hardware asked less often.

The first path needs the speaker to be able to connect back to Home Assistant, which some container and VLAN setups prevent. When it can't, the scheduled checks carry on and changes show up a few seconds later. To see which path you have, download the diagnostics as described under [Troubleshooting](#troubleshooting) and look at `connection_info.upnp_events`: an `event_count` above zero means the speaker is reaching Home Assistant.

A speaker that stops answering becomes unavailable and comes back without a restart when it answers again.

## Known limitations

- Don't count on the music coming back after an announcement. On Spotify, AirPlay, Bluetooth and the physical inputs, the announcement always replaces what was playing. On a network source (a preset, a radio stream, a URL or a USB drive) the integration uses the speaker's own announcement command, which is meant to lower the music and resume it but rarely does in practice.
- An announcement sent to a speaker that's following a group can take that speaker out of the group.
- Streaming services such as Spotify show as the current source, but you can't start them from the source list. Start them from their own app.
- The RoomFit select is created when the speaker has a saved profile. After you save the first one in the WiiM Home app, reload the speaker's entry from its three-dot menu.
- `wiim.scan_bluetooth` and `wiim.set_channel_balance` use commands that aren't part of the published WiiM API, so a firmware update can break them.

## Troubleshooting

The [FAQ and troubleshooting guide](docs/faq-and-troubleshooting.md) covers the common problems. When you report one, attach the diagnostics: go to **Settings** > **Devices & services** > **WiiM**, open the speaker's device and select **Download diagnostics**. IP addresses, MAC addresses and Wi-Fi names are removed from the file.

Report bugs and ask questions in [GitHub Issues](https://github.com/mjcumming/wiim/issues).

## Remove the integration

Delete each speaker under **Settings** > **Devices & services** > **WiiM**, then uninstall WiiM Audio in the Marketplace or HACS and restart Home Assistant.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) explains how to set up a development environment and what a pull request needs. Reports from speakers that aren't in the table above are especially useful. Device communication lives in the [pywiim](https://github.com/mjcumming/pywiim) library, so a problem with how a speaker is detected or controlled usually belongs there.

## Credits

WiiM Audio is built on [pywiim](https://github.com/mjcumming/pywiim), an async Python library for WiiM and LinkPlay devices. It draws on earlier work in [python-linkplay](https://github.com/Velleman/python-linkplay) and the original [LinkPlay custom integration](https://github.com/nagyrobi/home-assistant-custom-components-linkplay).

## License

MIT. See [LICENSE](LICENSE).

This project isn't affiliated with WiiM or LinkPlay. All trademarks belong to their owners.
