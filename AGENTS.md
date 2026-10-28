# Agent / contributor context (WiiM Home Assistant integration)

**Start here:** [docs/DEVELOPMENT-RULES.md — Rules map (read this first)](docs/DEVELOPMENT-RULES.md#rules-map-read-this-first) — what this repo does, how it uses **pywiim**, how we communicate, contracts (changelog, manifest, ADRs), and ADR workflow.

**Structure:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — coordinator, entities, data flow.

**Durable decisions:** [docs/adr/README.md](docs/adr/README.md) — numbered ADRs; see [Rule 8 — invariants learned the hard way](docs/DEVELOPMENT-RULES.md#rule-8-adrs-for-invariants-learned-the-hard-way).

**Contribution checklist:** [CONTRIBUTING.md](CONTRIBUTING.md)

We maintain **both** repositories ([wiim](https://github.com/mjcumming/wiim), [pywiim](https://github.com/mjcumming/pywiim)). Put fixes in the **right layer**: HA entities/services/coordinator → integration; HTTP/API/`Player`/`Group`/parsing → **pywiim** (then bump the integration dependency if needed). See **[Rule 2b](docs/DEVELOPMENT-RULES.md#rule-2b-fix-in-the-right-repository-integration-vs-pywiim)**.

**Agent/workspace boundary:** This workspace may include a sibling **pywiim** checkout at `../pywiim`. You may edit that checkout when the fix belongs in the library, but keep **wiim** and **pywiim** as separate git repos with separate commits/PRs/releases. Do not vendor or copy pywiim into this repo. See **[Rule 2c](docs/DEVELOPMENT-RULES.md#rule-2c-cross-repository-pywiim-work-agents--automation)**.

pywiim documents Home Assistant usage under **`docs/integration/`** in that repo (e.g. [HA_INTEGRATION.md](https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_INTEGRATION.md)). Use **`wiim-pywiim.code-workspace`** here for the combined workspace, or **`../pywiim/pywiim.code-workspace`** for pywiim-only work.

## Cursor Cloud

Cloud Agents use Python 3.13 from the deadsnakes PPA. Project dependencies are installed into `~/.local/wiim-venv`. `python3`, `pip`, `pytest`, `ruff`, `flake8`, `mypy`, and `hass` on `PATH` are symlinks to that virtualenv under `/usr/local/bin`.

- CI-equivalent checks: `ruff check custom_components/wiim --line-length 120`, `flake8 custom_components/wiim --max-line-length=120 --extend-ignore=E203,W503`, `mypy --strict custom_components/wiim`, and `pytest tests/`.
- `bash scripts/setup.sh` stops before it creates `./config` here, because `pre-commit install` exits when `core.hooksPath` is set. Leave that git config alone.
- Run Home Assistant with `bash scripts/develop`. It serves http://localhost:8123 and uses the gitignored `./config` directory, with `custom_components/wiim` symlinked in. This environment does not have `/home/vscode/.local/ha-venv` or a `/workspaces/core` checkout. There are no WiiM speakers on the agent network; use `pytest` and the config-flow UI for local verification.
