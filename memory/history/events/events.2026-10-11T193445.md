---
title: Events
updated_at: 2026-10-11T19:29:59+02:00
generator: run-day v1
template: events v1
entries: 30
---
# Events

Things that happened to systems, models and features, newest first. Generated from the logs by
run_day.py; re-running a day replaces that day's entries, so edit the prompt rather than this file.

### 2026-10-11 · Claude Code global settings (~/.claude/settings.json) · cleanupPeriodDays set to 365
- impact: Chat transcripts are now retained for 1 year instead of the default 30 days; other settings were preserved.
- project: claude-memory
- sessions: 52063c70, f5faaff3

### 2026-10-04 · plot-payments skill · created under .claude/skills/plot-payments from the create-python-skill template, with plotting logic ported from scripts/plot_payments_2026.py, pinned requirements and SKILL.md; test-run successfully
- impact: Skill runs and writes a PNG plus manifest to outputs/plot-payments/. Several parallel sessions built it independently with different test data. The final run on real data (data/payments_2026.parquet) passed validate.py (ok: true).
- project: claude-skills
- sessions: 0c6dd2c5, 44c753f1, 511cfc23, 58fb9138, 77b6e0a0, 79bfe2ea, ac4afc31, e1e10ce8, e4733b7b, fc71dd00

### 2026-10-04 · payments-plot-notebook skill · created from the create-notebook-skill template after the user rejected reusing plot-payments; test-run and passed validate.py
- impact: Produces an executed notebook, plot and manifest in outputs/payments-plot-notebook/. Registered Jupyter kernel 'Python 3.12 (payments-plot-notebook)'. Test run: Apr 1 – Oct 3 2026, avg CBK rate 9.55%, avg maturity 88.2% (maturing).
- project: claude-skills
- sessions: 0c6dd2c5, 44c753f1, 511cfc23, 58fb9138, 77b6e0a0, 79bfe2ea, ac4afc31, e1e10ce8, e4733b7b, fc71dd00

### 2026-10-04 · uv config (~/.config/uv/uv.toml) · found broken: duplicate key 'python-preference' causes TOML parse error
- impact: uv pip compile failed in one session; other sessions did not hit it. Not fixed in the transcript.
- project: claude-skills
- sessions: 0c6dd2c5, 44c753f1, 511cfc23, 58fb9138, 77b6e0a0, 79bfe2ea, ac4afc31, e1e10ce8, e4733b7b, fc71dd00

### 2026-10-03 · chargeback-maturity skill · created via new-python-skill scaffold, with 13 passing tests and validation ok
- impact: Skill computes chargeback maturity curves and period maturity status (immature <80%, maturing, ok ≥99%), with optional split by column.
- project: claude-skills
- sessions: 04665134, 14db837b, 332358bd, 6189177b, 77438bbb, a51ee220

### 2026-10-03 · data/payments.parquet · generated as synthetic dataset (500 rows, 54 chargebacks, Jan 2024)
- impact: Provides test input for the chargeback-maturity skill; Jan 2024 judged fully mature (100%, status ok) when run.
- project: claude-skills
- sessions: 04665134, 14db837b, 332358bd, 6189177b, 77438bbb, a51ee220

### 2026-10-03 · data/payments_2026.parquet · created as synthetic dataset (2,924 rows, 2026-04-01 to 2026-10-03) with unarrived chargebacks left as NaT
- impact: Models an immature/maturing period; maturity curve computed from it showed recent cohorts with low maturity.
- project: claude-skills
- sessions: 04665134, 14db837b, 332358bd, 6189177b, 77438bbb, a51ee220

### 2026-10-03 · plot-payments skill · created from the simple template and smoke-tested with synthetic data
- impact: Produces a two-panel plot of daily USD volume and chargeback rate with maturity; test run wrote a PNG and manifest.
- project: claude-skills
- sessions: 04665134, 14db837b, 332358bd, 6189177b, 77438bbb, a51ee220

### 2026-10-03 · scripts/plot_payments_2026.py · created and then parameterized with --input and --curve arguments
- impact: Used to generate plots for both the 2024 and 2026 parquets (outputs/payments_2024_plot.png, payments_2026_plot.png).
- project: claude-skills
- sessions: 04665134, 14db837b, 332358bd, 6189177b, 77438bbb, a51ee220

### 2026-10-03 · chargeback-maturity skill · found not installed in the skill directory in later sessions: requirements.txt not found and Glob found no files
- impact: Runs from the project path failed; cause not resolved. Earlier session found the project directory name has a trailing space, which may be related.
- project: claude-skills
- sessions: 04665134, 14db837b, 332358bd, 6189177b, 77438bbb, a51ee220

### 2026-10-03 · chargeback-maturity skill runs · emitted NumPy 1.x/2.x compatibility warning from system numexpr
- impact: Harmless stderr noise; results were correct.
- project: claude-skills
- sessions: 04665134, 14db837b, 332358bd, 6189177b, 77438bbb, a51ee220

### 2026-09-27 · innerlognotes Lambda (login / webauthn) · diagnosed slow passkey login: cold starts of about 2.7–2.8s init on a Lambda left at the default 128 MB memory
- impact: The /webauthn/login/start round trip delays the passkey prompt by about 5s. The suggested fix is to raise memory_size to 512–1024 MB in terraform/lambda.tf. It had not been applied yet; the user was asked whether to proceed.
- project: innerlognotes
- sessions: 93179c14, a4872b16

### 2026-09-27 · innerlognotes production Lambda · production code version identified as commit 3fed6f6 (last modified 2026-08-16)
- impact: Nothing has been deployed since then, and main.py has no uncommitted drift.
- project: innerlognotes
- sessions: 93179c14, a4872b16

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
