---
title: Mistakes
updated_at: 2026-10-11T19:27:12+02:00
generator: rules-writer v1
template: mistakes v1
rules: 1
---
# Mistakes

Errors Claude made on its own, turned into rules that would prevent them. Edit the text freely and
change `status` by hand: `proposed` → `approved` (exported to mistakes.claude.md) or `retired`
(kept so it isn't re-proposed). IDs, evidence and occurrences are maintained by the script.

### MS-001 · Don't run and test the app yourself when the user asks for help checking how it runs
- instead: Give the exact run commands and URLs, let the user run it, and only debug or read logs when they ask.
- why: Claude started the dev server and smoke-tested the API itself (including real Claude calls), so the user had to say "but I want to run it" and Claude had to kill the server and start over.
- scope: global
- status: proposed
- occurrences: 1
- evidence: 2026-08-02
