---
title: Not-to-do
updated_at: 2026-10-11T19:34:45+02:00
generator: rules-writer v1
template: nottodo v2
rules: 7
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
- occurrences: 2
- evidence: 2026-10-03, 2026-10-04

### NT-005 · Don't overwrite or reuse an existing skill folder when asked to create a skill from a different template
- instead: Create a new skill folder with the name the user gives and leave the existing skill untouched
- why: User interrupted Claude as it was about to replace the existing plot-payments skill with the notebook template and said 'no! create a new one payments-plot-notebook'.
- scope: project:claude-skills
- status: proposed
- occurrences: 1
- evidence: 2026-10-04

### NT-006 · Don't read or look at an existing skill the user said to ignore
- instead: Build the new skill only from the template and the referenced script, and don't open the excluded skill
- why: User said 'Ignore already created skill plot-payments. You are not allowed to see it'.
- scope: project:claude-skills
- status: proposed
- occurrences: 1
- evidence: 2026-10-04

### NT-007 · Don't add Co-Authored-By trailers to commit messages
- instead: Write plain commit messages with no Co-Authored-By line
- why: The user rejected the commit tool call and said to remove the Co-Authored-By note.
- scope: global
- status: proposed
- occurrences: 1
- evidence: 2026-10-11
