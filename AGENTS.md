# Agent / contributor context (WiiM Home Assistant integration)

**Start here:** [docs/DEVELOPMENT-RULES.md — Rules map (read this first)](docs/DEVELOPMENT-RULES.md#rules-map-read-this-first) — what this repo does, how it uses **pywiim**, how we communicate, contracts (changelog, manifest, ADRs), and ADR workflow.

**Structure:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — coordinator, entities, data flow.

**Durable decisions:** [docs/adr/README.md](docs/adr/README.md) — numbered ADRs; see [Rule 8 — invariants learned the hard way](docs/DEVELOPMENT-RULES.md#rule-8-adrs-for-invariants-learned-the-hard-way).

**Contribution checklist:** [CONTRIBUTING.md](CONTRIBUTING.md)

We maintain **both** repositories ([wiim](https://github.com/mjcumming/wiim), [pywiim](https://github.com/mjcumming/pywiim)). Put fixes in the **right layer**: HA entities/services/coordinator → integration; HTTP/API/`Player`/`Group`/parsing → **pywiim** (then bump the integration dependency if needed). See **[Rule 2b](docs/DEVELOPMENT-RULES.md#rule-2b-fix-in-the-right-repository-integration-vs-pywiim)**.

**Agent/workspace boundary:** This workspace may include a sibling **pywiim** checkout at `../pywiim`. You may edit that checkout when the fix belongs in the library, but keep **wiim** and **pywiim** as separate git repos with separate commits/PRs/releases. Do not vendor or copy pywiim into this repo. See **[Rule 2c](docs/DEVELOPMENT-RULES.md#rule-2c-cross-repository-pywiim-work-agents--automation)**.

pywiim documents Home Assistant usage under **`docs/integration/`** in that repo (e.g. [HA_INTEGRATION.md](https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_INTEGRATION.md)). Use **`wiim-pywiim.code-workspace`** here for the combined workspace, or **`../pywiim/pywiim.code-workspace`** for pywiim-only work.
