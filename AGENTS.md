# Agent / contributor context (WiiM Home Assistant integration)

**Start here:** [docs/DEVELOPMENT-RULES.md — Rules map (read this first)](docs/DEVELOPMENT-RULES.md#rules-map-read-this-first) — what this repo does, how it uses **pywiim**, how we communicate, contracts (changelog, manifest, ADRs), and ADR workflow.

**Structure:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — coordinator, entities, data flow.

**Durable decisions:** [docs/adr/README.md](docs/adr/README.md) — numbered ADRs; see [Rule 8 — invariants learned the hard way](docs/DEVELOPMENT-RULES.md#rule-8-adrs-for-invariants-learned-the-hard-way).

**Contribution checklist:** [CONTRIBUTING.md](CONTRIBUTING.md)

We maintain **both** repositories ([wiim](https://github.com/mjcumming/wiim), [pywiim](https://github.com/mjcumming/pywiim)). Put fixes in the **right layer**: HA entities/services/coordinator → integration; HTTP/API/`Player`/`Group`/parsing → **pywiim** (then bump the integration dependency if needed). See **[Rule 2b](docs/DEVELOPMENT-RULES.md#rule-2b-fix-in-the-right-repository-integration-vs-pywiim)**.

**Agent/workspace boundary:** This workspace may include a sibling **pywiim** checkout at `../pywiim`. You may edit that checkout when the fix belongs in the library, but keep **wiim** and **pywiim** as separate git repos with separate commits/PRs/releases. Do not vendor or copy pywiim into this repo. See **[Rule 2c](docs/DEVELOPMENT-RULES.md#rule-2c-cross-repository-pywiim-work-agents--automation)**.

pywiim documents Home Assistant usage under **`docs/integration/`** in that repo (e.g. [HA_INTEGRATION.md](https://github.com/mjcumming/pywiim/blob/main/docs/integration/HA_INTEGRATION.md)). Use **`wiim-pywiim.code-workspace`** here for the combined workspace, or **`../pywiim/pywiim.code-workspace`** for pywiim-only work.

## Cursor Cloud specific instructions

- Use Python 3.13 for this repository. CI, mypy, and `make check-python` all require it.
- On Ubuntu Cloud Agent VMs, install Python 3.13 from the deadsnakes PPA and install `libturbojpeg` before creating the venv.
- Recommended local venv: `/workspace/.venv`.
- Install dependencies with:

  ```bash
  python3.13 -m venv /workspace/.venv
  . /workspace/.venv/bin/activate
  pip install --upgrade pip setuptools wheel
  pip install --constraint=.github/workflows/constraints.txt -r requirements_test.txt
  pip install pycares==4.4.0 aiodns==3.4.0
  mkdir -p build
  ```

- Keep the explicit `pycares==4.4.0` repair step. A later dependency pass can otherwise leave `pycares` at 5.x, which breaks `aiodns` during pytest startup with `AttributeError: module 'pycares' has no attribute 'ares_query_a_result'`.
- Standard verification command: `bash scripts/check-before-push.sh`.
- To smoke-test the host app, run Home Assistant from the venv with a config directory that symlinks `custom_components/wiim`, then check `http://127.0.0.1:8123/api/` returns `401` for unauthenticated access.
