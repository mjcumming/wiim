# Basic WiiM Lovelace Cards

## Simple Media Control Card

```yaml
type: media-control
entity: media_player.living_room_speaker
```

## Group Control Card

```yaml
type: media-control
entity: media_player.living_room_group
```

## Button Controls for Groups

```yaml
type: horizontal-stack
cards:
  - type: button
    tap_action:
      action: call-service
      service: script.wiim_party_mode
    name: Party Mode
    icon: mdi:party-popper
  - type: button
    tap_action:
      action: call-service
      service: script.wiim_ungroup_all
    name: Ungroup All
    icon: mdi:speaker-off
```

## Entities Card for Device Status

```yaml
type: entities
title: WiiM System Status
entities:
  - entity: sensor.living_room_multiroom_role
    name: Living Room Role
  - entity: sensor.kitchen_multiroom_role
    name: Kitchen Role
  - entity: sensor.bedroom_multiroom_role
    name: Bedroom Role
```

## Mini Media Player (Custom Card)

If you have mini-media-player installed:

```yaml
type: custom:mini-media-player
entity: media_player.living_room_speaker
artwork: cover
info: scroll
volume_stateless: true
group: true
```

## Volume Control Grid

```yaml
type: grid
square: false
columns: 2
cards:
  - type: media-control
    entity: media_player.living_room
  - type: media-control
    entity: media_player.kitchen
  - type: media-control
    entity: media_player.bedroom
  - type: media-control
    entity: media_player.living_room_group
```
