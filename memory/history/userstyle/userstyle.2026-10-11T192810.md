---
title: User style
updated_at: 2026-10-11T19:27:12+02:00
generator: rules-writer v1
template: userstyle v1
rules: 3
---
# User style

How the user likes to work with Claude, distilled from the daily journals. Edit the text freely and
change `status` by hand: `proposed` → `approved` (exported to userstyle.claude.md) or `retired`
(kept so it isn't re-proposed). IDs, evidence and occurrences are maintained by the script.

### US-001 · The user wants to run and drive things themselves (starting servers, clicking through the app) rather than have Claude run them for them
- apply: When the user wants to try or test something, give the exact run command/steps and stay out of the way; don't launch servers or drive the flow yourself unless asked. Offer to check logs if they hit problems.
- why: After Claude started a dev server and smoke-tested the API, the user said 'but I want to run it' and Claude had to kill the process and hand over commands.
- scope: global
- status: proposed
- occurrences: 2
- evidence: 2026-08-02 (2)

### US-002 · The user likes visual maps/diagrams to understand architecture and flows
- apply: When they ask for a map or the flow explained, produce a visual artifact/diagram and summarize the key point briefly in text.
- why: They asked 'can you do a map? of how this works?' and Claude produced a flow-map artifact.
- scope: global
- status: proposed
- occurrences: 1
- evidence: 2026-08-02

### US-003 · The user wants to check how the app runs locally before deploying it
- apply: Prefer local verification (dev server with mocked AWS) before suggesting packaging or deployment steps.
- why: They asked 'help me check how this runs prior to deployment' and tested locally in the browser.
- scope: project:llm-app-template
- status: proposed
- occurrences: 1
- evidence: 2026-08-02
