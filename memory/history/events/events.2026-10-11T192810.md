---
title: Events
updated_at: 2026-10-11T19:27:12+02:00
generator: run-day v1
template: events v1
entries: 5
---
# Events

Things that happened to systems, models and features, newest first. Generated from the logs by
run_day.py; re-running a day replaces that day's entries, so edit the prompt rather than this file.

### 2026-08-02 · innerlognotes local dev server (dev.py) · run locally and smoke-tested end-to-end with mocked AWS and real Claude calls; user then ran it in the browser
- impact: Login, save note, Claude categorization, note listing and categories confirmed working locally; the dev server started by Claude was stopped afterward to free port 8000.
- project: llm-app-template
- sessions: 954c9020

### 2026-08-02 · innerlognotes AWS deployment · checked and found not deployed
- impact: No terraform.tfvars, state or lambda package exists, so nothing runs in AWS. PLAN.md Tasks 9–10 (packaging, terraform apply) are not done.
- project: llm-app-template
- sessions: 954c9020

### 2026-08-02 · innerlognotes application code (main.py, consolidate.py, index.html, tests, dev.py) · found uncommitted in the working tree; last commit was Jun 21
- impact: App code, frontend and 18 passing tests were never committed. PLAN.md checkboxes are all still unchecked.
- project: llm-app-template
- sessions: 954c9020

### 2026-08-02 · innerlognotes categorization · observed inconsistent categorization in testing: dentist and knee notes both became "Healthcare" in the first test
- impact: Flat category strings may not match the PLAN.md examples. Consolidation has never run, so the topics and silver tables are empty.
- project: llm-app-template
- sessions: 954c9020

### 2026-08-02 · innerlognotes category design · redesign proposed: replace flat categories and topics with an evolving node tree (nodeId/parentId) and incremental diff-based consolidation
- impact: Design discussion only, nothing implemented. Embedding map left as a separate future pipeline.
- project: llm-app-template
- sessions: 954c9020
