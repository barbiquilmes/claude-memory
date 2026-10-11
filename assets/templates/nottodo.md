---
title: Not-to-do
updated_at: {{updated_at}}
generator: {{generator}}
template: nottodo v2
rules: {{rules}}
---
# Not-to-do

Things the user told Claude never to do. Edit the text freely and change `status` by hand:
`proposed` → `approved` (exported to nottodo.claude.md) or `retired` (kept so it isn't re-proposed).
IDs, evidence and occurrences are maintained by the script.

<!-- entry -->
### {{id}} · {{rule}}
- instead: {{instead}}
- why: {{why}}
- scope: {{scope}}
- status: {{status}}
- occurrences: {{occurrences}}
- evidence: {{evidence}}
<!-- /entry -->
