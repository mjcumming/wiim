# WiiM Integration – Typed Models

Below you can find condensed JSON-Schema excerpts (draft-07) for the key models
used throughout the integration.  _Optional_ fields are marked by
`"nullable": true` and most "extra" fields are accepted via
`additionalProperties: true` for forward-compatibility.

---

### DeviceInfo

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DeviceInfo",
  "type": "object",
  "additionalProperties": true,
  "properties": {
    "uuid":          {"type": ["string", "null"]},
    "name":          {"type": ["string", "null"]},
    "model":         {"type": ["string", "null"]},
    "firmware":      {"type": ["string", "null"]},
    "mac":           {"type": ["string", "null"]},
    "ip":            {"type": ["string", "null"]},
    "release_date":  {"type": ["string", "null"]},
    "hardware":      {"type": ["string", "null"]},
    "wmrm_version":  {"type": ["string", "null"]},
    "mcu_ver":       {"type": ["string", "null"]},
    "dsp_ver":       {"type": ["string", "null"]},
    "preset_key":    {"type": ["integer", "null"]},
    "group":         {"type": ["string", "null"]},
    "master_uuid":   {"type": ["string", "null"]},
    "master_ip":     {"type": ["string", "null"]},
    "version_update":{"type": ["string", "null"]},
    "latest_version":{"type": ["string", "null"]}
  }
}
```

### PlayerStatus

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PlayerStatus",
  "type": "object",
  "additionalProperties": true,
  "properties": {
    "play_state":  {"type": ["string", "null"], "enum": ["play", "pause", "stop", "load", null]},
    "volume":      {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
    "mute":        {"type": ["boolean", "null"]},
    "source":      {"type": ["string", "null"]},
    "mode":        {"type": ["string", "null"]},
    "position":    {"type": ["integer", "null"]},
    "duration":    {"type": ["integer", "null"]},
    "title":       {"type": ["string", "null"]},
    "artist":      {"type": ["string", "null"]},
    "album":       {"type": ["string", "null"]},
    "entity_picture": {"type": ["string", "null"]},
    "cover_url":   {"type": ["string", "null"]},
    "eq_preset":   {"type": ["string", "null"]},
    "wifi_rssi":   {"type": ["integer", "null"]}
  }
}
```

### TrackMetadata

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TrackMetadata",
  "type": "object",
  "additionalProperties": true,
  "properties": {
    "title":          {"type": ["string", "null"]},
    "artist":         {"type": ["string", "null"]},
    "album":          {"type": ["string", "null"]},
    "entity_picture": {"type": ["string", "null"]},
    "cover_url":      {"type": ["string", "null"]}
  }
}
```

### EQInfo

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "EQInfo",
  "type": "object",
  "additionalProperties": true,
  "properties": {
    "eq_enabled": {"type": ["boolean", "null"]},
    "eq_preset":  {"type": ["string", "null"]}
  }
}
```

### SlaveInfo

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SlaveInfo",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "uuid": {"type": ["string", "null"]},
    "ip":   {"type": "string"},
    "name": {"type": "string"}
  },
  "required": ["ip", "name"]
}
```

### MultiroomInfo

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MultiroomInfo",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "role":       {"type": "string", "enum": ["master", "slave", "solo"]},
    "slave_list": {"type": "array", "items": {"$ref": "#/definitions/SlaveInfo"}}
  },
  "required": ["role"]
}
```

---

These definitions are intended for developer reference only.  They are kept
lightweight so that they can be diff-viewed easily in PRs.  For an exhaustive
machine-readable schema run `python -m custom_components.wiim.models` (script
to be added) which prints the full `model_json_schema()` output.
