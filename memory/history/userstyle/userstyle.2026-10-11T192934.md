---
title: User style
updated_at: 2026-10-11T19:28:37+02:00
generator: rules-writer v1
template: userstyle v1
rules: 9
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

### US-004 · The user wants a minimal, internally consistent design and challenges redundant or contradictory parts
- apply: Keep schemas and operations as small as possible. Drop fields or ops the user calls redundant (e.g. status, rename). Don't contradict earlier statements; if you got something wrong, say so and restate the corrected version cleanly.
- why: The user said 'no me gusta lo de status. borra ese punto', questioned why rename was needed, and called out 'te estas contradiciendo'.
- scope: global
- status: proposed
- occurrences: 4
- evidence: 2026-08-09 (4)

### US-005 · The user decides names and conventions themselves and expects Claude to adopt them
- apply: When the user proposes a name (table, field, file), use it exactly. Suggest names only when asked, and confirm the interpretation if a typo makes it ambiguous.
- why: They proposed notes/nodes/notes_nodes, 'equivalentid' (later 'merged into'), and 'try consolidate reparent' as names.
- scope: global
- status: proposed
- occurrences: 3
- evidence: 2026-08-09 (3)

### US-006 · The user wants Claude to act directly once they have given a clear direction, without asking another confirmation question
- apply: After the user states a decision, carry it out. Don't re-ask via a multiple-choice question; reserve questions for real ambiguity.
- why: They interrupted an AskUserQuestion about removing rename and simply said 'eliminalo', and answered 'dejalos ahi entonces no hagas nada' to the history-rewrite question.
- scope: global
- status: proposed
- occurrences: 3
- evidence: 2026-08-09 (2), 2026-08-22

### US-007 · The user works across multiple sessions and wants self-contained handoff material (a full plan or a paste-ready prompt)
- apply: When the user says they will continue elsewhere, produce a complete, self-contained plan or a paste-ready plain-text prompt. Include what is done, what is left and the key decisions.
- why: They asked 'generame el plan de accion entero. voy a ejecutarlo en otra sesion' and 'pasame el prompt para seguir alla'.
- scope: global
- status: proposed
- occurrences: 2
- evidence: 2026-08-09 (2)

### US-008 · The user wants Claude to stay out of their personal notes/files unless they explicitly ask, to avoid biasing the answer
- apply: Don't read the user's notes, specs or project docs when answering a general question; answer from general knowledge unless asked to look.
- why: They interrupted Claude's file reads and said they didn't want it reading their notes so as not to be biased.
- scope: global
- status: proposed
- occurrences: 1
- evidence: 2026-08-22

### US-009 · The user wants to learn concepts step by step and be quizzed to check understanding before building
- apply: Explain fundamentals in short pieces, offer check questions, and only move to hands-on setup once they feel solid; have the user run the commands.
- why: They said they don't understand HTTP/TLS/443/SSH, asked to learn along the way, and requested questions to check their knowledge.
- scope: global
- status: proposed
- occurrences: 2
- evidence: 2026-08-22 (2)
