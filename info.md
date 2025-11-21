# WiiM Audio (LinkPlay) Integration

![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Home Assistant integration for WiiM / LinkPlay based audio streamers. Built on the [`pywiim`](https://github.com/mjcumming/pywiim) library for robust device communication.

---

## Features

- **Automatic discovery** of speakers via SSDP/Zeroconf
- Full media‐player support (play/pause, volume, source, seek)
- Multi-room grouping (master/slave) helpers
- Optional diagnostic sensors and maintenance controls

---

{% if not installed %}

### Installation (development)

1. Copy `custom_components/wiim/` to your Home Assistant `custom_components/` directory.
2. Restart Home Assistant.
3. Add the integration via _Settings → Devices & Services_.

_For production users, simply add the repository as a **custom repository** in HACS and install from there._

{% endif %}

---

## Documentation

Full documentation, contribution guide and troubleshooting can be found in the project [README](README.md).
