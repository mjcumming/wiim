# ADR 0007: Strict capability gating — no integration-side feature detection

## Status

Accepted

## Date

2026-04-21

## Context

The Home Assistant integration must not **infer** device features (model heuristics, `getattr(..., False)` shims, “plugged” hardware state, cached config-entry blobs alone, or ad-hoc HTTP calls). That duplicates **pywiim** responsibility, drifts from the library, and produces bugs like “entity missing after upgrade” or “wrong platform enabled.”

[ADR 0001](0001-thin-glue-layer.md) says logic belongs in pywiim. [ADR 0006](0006-pywiim-capabilities-only.md) says the integration consumes pywiim capability truth only. This ADR makes the **operational contract explicit and testable**.

## Decision

### 1. Single source of truth

For “**may this device expose feature X in Home Assistant?**” the integration uses **only**:

- **`WiiMClient.capabilities`** (the same mapping `Player` reads), after pywiim’s capability detection / `refresh_capabilities()` / firmware refresh paths have run; and/or  
- **`Player.supports_*`** properties **that are defined in pywiim as reading `client.capabilities`** (same underlying data as (1)).

**Forbidden** in `custom_components/wiim/`:

- Inferring support from **hardware/runtime state** (e.g. subwoofer **plugged**) to **register** or **omit** an entity.
- Using **`getattr(player, "supports_foo", False)`** when `supports_foo` is not a documented pywiim capability surface (hides `AttributeError` and invents defaults).
- Using **`config_entry.data["capabilities"]` alone** when a coordinator exists — live **`player.client.capabilities`** must **win** (merged on top) so OTA / refresh cannot lie.

### 2. Concrete integration rules

- **Subwoofer switch / number:** register iff **`player.supports_subwoofer`** (pywiim).
- **12V trigger switch:** register iff **`player.client` exists and `bool(player.client.capabilities.get("supports_trigger_out"))`** after pywiim sets that key during detection.
- **Display light:** register iff **`player.client` exists and `bool(player.client.capabilities.get("supports_display_config"))`** after pywiim sets that key.
- **`get_enabled_platforms`:** build caps as **`dict(explicit_arg or entry.data) | update(dict(player.client.capabilities))`** when the coordinator is in `hass.data`; **`supports_firmware_install`** comes only from that merged dict — **no** `getattr(player, "supports_firmware_install", …)` fallback.
- **`update` platform / firmware sensor attrs:** same rule — use **`player.client.capabilities`** (via `capability_flags`) for **`supports_firmware_install`**, not `getattr` on `Player`.

### 3. Library obligation (pywiim)

pywiim **must** populate `client.capabilities["supports_*"]` keys (via `WiiMCapabilities.detect_capabilities` and friends) for any feature the HA integration is expected to gate. If a flag is missing, the integration treats it as **false** — **do not** compensate in the integration.

## Consequences

### Positive

- One debugging story: **diagnostics → `capabilities` → pywiim version**.
- Upgrades that add detection keys behave predictably after `refresh_capabilities` / cache rules in setup.

### Negative / risks

- Until pywiim ships detection for a key, the integration will **not** expose the entity — correct layering: fix **pywiim**, bump the pin.

## Notes

- UPnP-derived flags (`supports_queue_browse`, etc.) remain defined inside pywiim; the integration still reads **`Player.supports_*`** where those properties are the documented API.
- Workspace boundary: library edits ship from the **pywiim** repository; this ADR governs the **integration** repo ([Rule 2c](../DEVELOPMENT-RULES.md#rule-2c-do-not-edit-the-pywiim-library-from-this-repository-agents--automation)).
