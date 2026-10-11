---
title: Investigations
updated_at: 2026-10-11T19:28:10+02:00
generator: run-day v1
template: investigations v1
entries: 9
---
# Investigations

Questions the user set out to answer, how they were investigated, and what was concluded, newest
first. Generated from the logs by run_day.py; re-running a day replaces that day's entries.

### 2026-08-09 · What would happen if the user ran terraform on the current repo?
- project: llm-app-template
- status: closed
- approach: Claude listed the .tf files, read main.tf/variables.tf, checked for terraform.tfvars and lambda.zip, and ran aws sts get-caller-identity to see whether AWS credentials were configured.
- findings: terraform init would work (local state). plan/apply would fail because there is no terraform.tfvars (sensitive vars missing) and ../lambda.zip does not exist. AWS credentials are configured, so once those are fixed Terraform would create real billable resources in eu-west-1: DynamoDB tables, 2 Lambdas, API Gateway, EventBridge Scheduler, SSM params, S3 + CloudFront, IAM roles.
- conclusion: Terraform can't apply until tfvars are filled in and the Lambda zip is built; after that it would create real infrastructure.
- sessions: 4778d440, 954c9020

### 2026-08-09 · What is missing before pushing the repo to GitHub as a reusable template?
- project: llm-app-template
- status: closed
- approach: Claude reviewed README, main.py, dev.py, git log/status, tracked and ignored files, and grepped for secrets, account IDs and 'innerlog' references. It also checked the git remote and tried the GitHub API.
- findings: App code (main.py, dev.py, consolidate.py, index.html, tests/) was untracked. 'innerlognotes' was hardcoded as a default in about 6 places. PLAN.md is app-specific. .env.example and LICENSE were missing, and pyproject had a placeholder description. No secrets were found in git history. The repo was already pushed to origin; the public API returned 404, so it is likely private.
- conclusion: Claude genericized the defaults to 'yourapp' and added .env.example, a MIT LICENSE and a pyproject description. The user chose to leave PLAN.md and learnings/ as they are. 25–26 tests passed and the changes were committed and pushed. The repo was later marked as a template.
- sessions: 4778d440, 954c9020

### 2026-08-09 · Does the consolidation Lambda work end-to-end on real AWS after the active_nodes/loose fix?
- project: llm-app-template
- status: closed
- approach: Claude redeployed the Lambda with Terraform, invoked innerlognotes-test-consolidation, tailed CloudWatch logs, scanned DynamoDB and called GET /tree through the API.
- findings: The invocation returned ok with 1 operation. All 5 loose nodes (Eye Care, Pain Management, Dental Care, etc.) were attached under a new parent, 'Health & Wellness' (attached=5/5), with no self-merges. terraform plan then showed no drift.
- conclusion: The fix resolved the bug, and the login, write, read and consolidation flow was validated on real AWS.
- sessions: 4778d440, 954c9020

### 2026-08-09 · Does Claude pick the reparent, merge and rename operations correctly in the consolidation prompt?
- project: llm-app-template
- status: closed
- approach: Claude wrote throwaway scripts (try_consolidate_reparent.py, _merge.py, _rename.py) that call the Claude API with hardcoded trees and loose nodes, then ran them.
- findings: Reparent worked: Dental Care was attached under the existing Health & Wellness. Merge was chosen only for Teeth/Tooth, which are literally the same word; Dentist/Teeth and Dentist/Dental Care got create_parent instead. Rename was never chosen; the model created a new 'Fitness' parent and left 'Random Stuff' orphaned. The user questioned whether rename is needed and whether merge could cover it.
- conclusion: The user decided to drop rename from the schema. Claude removed it from consolidate.py and its tests (25 tests pass), redeployed, committed and pushed.
- sessions: 4778d440, 954c9020

### 2026-08-09 · Which tables should the node-based hierarchy use, and which are mutable?
- project: llm-app-template
- status: closed
- approach: Design discussion in conversation: Claude proposed table schemas and the user corrected them over several turns. Claude then used the superpowers:writing-plans skill and read the existing code, tests and Terraform to write an implementation plan.
- findings: The design settled on 3 tables: notes (immutable), nodes (label, parentId, mergedInto, the only mutable one) and notes-nodes (immutable). The user rejected a status field and wanted merges handled in nodes through an alias field, which Claude had initially described inconsistently. The user finally preferred the name mergedInto over equivalentId. A 7-task TDD plan was saved to docs/superpowers/plans/2026-08-09-node-hierarchy-migration.md.
- conclusion: Three-table schema agreed (notes, nodes, notes-nodes) with mergedInto as the alias field. The plan was written for execution in another session.
- sessions: 4778d440, 954c9020

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
