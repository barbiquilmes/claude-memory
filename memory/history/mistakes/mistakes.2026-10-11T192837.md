---
title: Mistakes
updated_at: 2026-10-11T19:28:10+02:00
generator: rules-writer v1
template: mistakes v1
rules: 3
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

### MS-002 · Don't state design facts that contradict each other inside one answer
- instead: Re-read the answer for consistency before sending, and check every claim such as 'the only mutable table' against the rest of the explanation.
- why: Claude said notes-nodes was the only mutable table and then said that nodes was mutated. The user had to point out the contradiction and ask again.
- scope: global
- status: proposed
- occurrences: 1
- evidence: 2026-08-09

### MS-003 · Don't build a test scenario that mixes several operations to exercise a single one
- instead: Design a minimal scenario that isolates the operation under test (for example a pure rename with no restructuring), and check it makes sense before running it.
- why: The rename test used a restructuring case. Claude blamed the model's bias and then had to admit the example was wrong when the user asked what 'Random Stuff' would be renamed to.
- scope: project:llm-app-template
- status: proposed
- occurrences: 1
- evidence: 2026-08-09
