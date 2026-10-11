---
title: Events
updated_at: 2026-10-11T19:28:10+02:00
generator: run-day v1
template: events v1
entries: 17
---
# Events

Things that happened to systems, models and features, newest first. Generated from the logs by
run_day.py; re-running a day replaces that day's entries, so edit the prompt rather than this file.

### 2026-08-09 · llm-app-template repo (GitHub barbiquilmes/llm-app-template) · app code, LICENSE (MIT), .env.example committed and pushed; 'innerlognotes' defaults genericized to 'yourapp'
- impact: App code was previously untracked; repo is now usable as a template.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · llm-app-template repo · marked as GitHub template repository (private)
- impact: Allows creating new repos from it via 'Use this template'.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · innerlognotes repo (GitHub barbiquilmes/innerlognotes) · created as private repo from llm-app-template and cloned locally
- impact: Clean single initial commit; deps installed, ruff hook enabled, 25 tests pass; still needs .env and tfvars for a real deploy.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · innerlognotes-test AWS stack (eu-west-1) · deployed via Terraform and validated end-to-end (login, notes, categorization, tree, consolidation)
- impact: Live test showed consolidation grouped 5 loose nodes under new parent 'Health & Wellness'.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · consolidation Lambda (consolidate.py) · found bug: active_nodes included loose nodes, so Claude emitted self-merges; fixed and redeployed
- impact: Verified on real AWS: no self-merges, all 5 nodes attached.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · consolidation Lambda operation names · operation names switched to English (create_parent, reparent, merge) and CloudWatch logging added
- impact: Deployed to innerlognotes-test Lambda.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · nodes table / main.py and consolidate.py · added updatedAt field to nodes and deployed to both Lambdas
- impact: Confirmed on a new node in real DynamoDB; older nodes lack it.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · consolidation 'rename' operation · removed from consolidate.py, tests and prompt, redeployed, committed and pushed
- impact: Manual tests showed Claude never chose rename; consolidation now has 3 ops; 25 tests pass.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · innerlognotes-test AWS infrastructure · destroyed with terraform destroy (29 resources, S3 bucket emptied manually after first attempt failed)
- impact: All test tables, Lambdas, API Gateway, CloudFront and SSM params deleted; test data lost; Terraform state empty.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · Anthropic API key in .env · found exposed in plain text in conversation, rotation recommended
- impact: Not committed to git (.env is gitignored); rotation advised in two sessions, not confirmed done.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · llm-app-template node-hierarchy migration plan · implementation plan written (nodes + notes-nodes tables replacing bronze/silver/categories/topics)
- impact: Plan only saved in docs/superpowers/plans; not executed in this session.
- project: llm-app-template
- sessions: 4778d440, 954c9020

### 2026-08-09 · gh CLI · installed via brew and authenticated to GitHub
- impact: Enabled repo creation and template flag.
- project: llm-app-template
- sessions: 4778d440, 954c9020

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
