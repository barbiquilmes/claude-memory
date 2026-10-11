---
title: Investigations
updated_at: 2026-10-11T19:27:12+02:00
generator: run-day v1
template: investigations v1
entries: 4
---
# Investigations

Questions the user set out to answer, how they were investigated, and what was concluded, newest
first. Generated from the logs by run_day.py; re-running a day replaces that day's entries.

### 2026-08-02 · Where did the user leave off in the project: was it tested locally and has it been deployed?
- project: llm-app-template
- status: closed
- approach: Claude inspected git status/log, PLAN.md, the directory tree, and searched for terraform.tfvars, tfstate, and lambda.zip build artifacts.
- findings: 18 tests pass locally and dev.py provides a moto-mocked AWS dev server with real Claude calls. There is no terraform.tfvars, no tfstate and no lambda.zip, so nothing is deployed. Application code is uncommitted and PLAN.md checkboxes are all unchecked.
- conclusion: Tested locally but not deployed; the work is uncommitted and Tasks 9–10 (packaging and terraform apply) are not done.
- sessions: 954c9020

### 2026-08-02 · Does the app run correctly locally before deployment?
- project: llm-app-template
- status: closed
- approach: Claude used the run skill to start dev.py and curl-tested healthz, login, notes, categories and topics. The user then ran the server and index.html themselves.
- findings: The API works end-to-end: login succeeds, wrong credentials return 401, and a real Claude categorization returned a category. The user confirmed in the browser that login, saving a note and categorization worked (categories 'Health' and 'Testing'). One side observation was that dentist and knee notes were both categorized as 'Healthcare'.
- conclusion: The app works locally end-to-end (login, save, categorize, list).
- sessions: 954c9020

### 2026-08-02 · What does the app do, how will notes look in the DynamoDB tables, and when do Haiku calls, topics and categories get created?
- project: llm-app-template
- status: closed
- approach: Claude read main.py, dev.py and consolidate.py and mapped the test notes onto the tables. It also published a flow diagram artifact (artifact-design skill).
- findings: There are two Haiku touchpoints. On save, one call categorizes the note and writes to notes, notes-cat-bronze and categories. Nightly consolidation makes two calls that merge synonyms and group categories into topics, then rewrites silver, categories and topics. Topics and silver are empty until consolidation has run, so GET /topics returning [] is expected.
- conclusion: A category is the per-note tag created at save time. A topic is a broader grouping created only by the nightly job. The UI reads from bronze.
- sessions: 954c9020

### 2026-08-02 · What is the best design for an evolving category hierarchy (with renames, a hierarchy map, and a future 2D embeddings map), and how would it work incrementally over 3 weeks?
- project: llm-app-template
- status: open
- approach: Claude reasoned from the current two-level schema (categories plus topics) and the user's example notes. It compared full rebuild with incremental diff and traced a 3-week example.
- findings: Claude recommended a generic node tree (id, label, parentId) with notes pointing to a nodeId, so renames and merges need no note rewrites. It recommended incremental diff operations (create parent, reparent, merge, rename) over a full nightly rebuild, with validation against cycles and orphans. Embeddings (e.g. Voyage plus UMAP) would be a separate pipeline. The user had not yet accepted a design; Claude offered to move to DynamoDB table design or prompt prototyping.
- conclusion: —
- sessions: 954c9020
