---
title: Not-to-do
updated_at: 2026-10-11T19:27:12+02:00
generator: rules-writer v1
template: nottodo v2
rules: 1
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
