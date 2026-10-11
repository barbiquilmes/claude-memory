---
title: Not-to-do
updated_at: 2026-10-11T19:29:34+02:00
generator: rules-writer v1
template: nottodo v2
rules: 4
---
# Not-to-do

Things the user told Claude never to do. Edit the text freely and change `status` by hand:
`proposed` → `approved` (exported to nottodo.claude.md) or `retired` (kept so it isn't re-proposed).
IDs, evidence and occurrences are maintained by the script.

### NT-001 · Don't run or drive the app/dev server yourself when the user wants to test it
- instead: Give the user the exact commands and steps to run it themselves, and offer help only if something breaks
- why: After Claude launched the dev server and smoke-tested it, the user said "but I want to run it", so Claude had to kill the server and hand over.
- scope: global
- status: proposed
- occurrences: 1
- evidence: 2026-08-02

### NT-002 · Don't commit or remove project-specific docs (PLAN.md, learnings/) when preparing the template repo
- instead: Leave PLAN.md and learnings/ as they are, and don't touch or rewrite what is already pushed unless asked
- why: User said "no los voy a commitear" about PLAN.md and learnings/, then answered "dejalos ahi entonces no hagas nada" when offered a way to remove them from the pushed history.
- scope: project:llm-app-template
- status: proposed
- occurrences: 2
- evidence: 2026-08-09 (2)

### NT-003 · Don't read the user's notes or existing spec/plan docs when they want an unbiased answer
- instead: Answer from general knowledge only and wait until the user allows reading project notes or docs
- why: The user rejected the Read/git log tool calls and interrupted, saying they didn't want Claude to read their notes so it wouldn't be biased.
- scope: project:innerlognotes
- status: proposed
- occurrences: 1
- evidence: 2026-08-22

### NT-004 · Don't run broad filesystem searches (e.g. find across the home directory) to locate a missing skill or file
- instead: Check the project directory, or ask the user where the file is
- why: The user rejected and interrupted a `find /Users/barbi -name chargeback-maturity` call while Claude was hunting for the missing skill directory.
- scope: global
- status: proposed
- occurrences: 1
- evidence: 2026-10-03
