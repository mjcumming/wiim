# ADR 0010: Prefer daily use over set-and-forget settings

## Status

Accepted

## Date

2026-11-24

## Context

The WiiM Home app mixes the controls people use while listening with setup screens and preferences they set once. Feature requests often ask Home Assistant to grow toward that whole app. The integration is where those requests become entities, so this is the place the pressure shows up.

pywiim keeps the same guidance for what the library models: [pywiim ADR 023](https://github.com/mjcumming/pywiim/blob/main/docs/design/adr/023-daily-use-surface.md).

## Decision

This is guidance for reviewing a new feature, not a ban.

Prefer features people use as part of daily listening, or readings that change on their own and are worth acting on. Playback, volume, source, grouping, and the EQ choice a listener actually selects are the center. A live device reading someone would automate belongs here too.

Set-and-forget settings are not the focus. A preference someone chooses once, or a control that only repeats a screen in the WiiM Home app, usually stays in the app. That includes one-time setup for accounts, network, and hardware. A request in that group needs a reason beyond "then I do not have to open the app."

A feature can still be accepted when the reason is real. Say what the daily or automated use is, and what it costs a speaker that never uses it. An odd one-off setting is not refused by this guidance on its own, and it is not the kind of feature we go looking for.

Existing entities stay. This guidance applies to what we add.

## Consequences

### Positive

- Reviews have a shared question: who uses this in normal listening, and how often?
- The integration can decline a pure app mirror without treating that as a rule that forbids every uncommon setting.

### Negative / risks

- Guidance can be applied unevenly. Two reviewers can weigh the same request differently, and the written reason on the request is what keeps that honest.

## Notes

Library side: pywiim ADR 023.
