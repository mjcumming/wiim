# Architecture Decision Records (ADRs)

Formal decisions for the WiiM Home Assistant integration live here as short, durable markdown files. Each ADR has a stable number; **do not renumber** published ADRs—add a new one if you reverse or replace a decision.

**Why so few files?** Only the old **Architecture** table (**0001–0003**) and **slave `supported_features`** (**0005**) were formalized initially. Other work is captured in **CHANGELOG** and git history until someone promotes it to a numbered ADR.

## Index

| ADR | Title |
| --- | --- |
| [0000-template.md](0000-template.md) | Template for new ADRs (copy and rename) |
| [0001-thin-glue-layer.md](0001-thin-glue-layer.md) | Thin glue layer; logic belongs in pywiim |
| [0002-test-directory-split.md](0002-test-directory-split.md) | Two test directories (`tests/` vs `scripts/`) |
| [0003-test-driven-development.md](0003-test-driven-development.md) | Test-driven development for regressions |
| [0005-slave-supported-features.md](0005-slave-supported-features.md) | Slave `media_player` `supported_features` (e.g. `PLAY_MEDIA`) |
| [0006-pywiim-capabilities-only.md](0006-pywiim-capabilities-only.md) | Use pywiim `supports_*` / capabilities only — no parallel detection in the integration |
| [0007-capability-gating-strict-contract.md](0007-capability-gating-strict-contract.md) | Strict capability gating: no integration-side feature inference; merged `client.capabilities` |

## How to add an ADR

**Ongoing rule (human + automation):** if a change encodes a **long-lived invariant** or **hard-won trade-off** you do not want reverted by mistake, add an ADR (use **Status: Proposed** until merged if needed). Details: [DEVELOPMENT-RULES.md § Rule 8](../DEVELOPMENT-RULES.md#rule-8-adrs-for-invariants-learned-the-hard-way).

1. Copy [0000-template.md](0000-template.md) to the next number, e.g. `0008-short-slug.md`.
2. Fill **Context**, **Decision**, and **Consequences** (required). Link GitHub issues/PRs in Context or Notes.
3. Set **Status** to `Accepted` when merged, or `Proposed` while under review.
4. Add a row to the table above.
5. If the decision supersedes an older ADR, set the old ADR’s status to `Superseded by ADR-0006` and say so in the new ADR.

## Relationship to `ARCHITECTURE.md`

High-level architecture and patterns remain in [../ARCHITECTURE.md](../ARCHITECTURE.md). **Specific choices with trade-offs** belong in this folder so they are searchable and versioned with the repo.
