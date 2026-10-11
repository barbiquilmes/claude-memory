---
title: Mistakes
updated_at: {{updated_at}}
generator: {{generator}}
template: mistakes v1
rules: {{rules}}
---
# Mistakes

Errors Claude made on its own, turned into rules that would prevent them. Edit the text freely and
change `status` by hand: `proposed` → `approved` (exported to mistakes.claude.md) or `retired`
(kept so it isn't re-proposed). IDs, evidence and occurrences are maintained by the script.

<!-- entry -->
### {{id}} · {{rule}}
- instead: {{instead}}
- why: {{why}}
- scope: {{scope}}
- status: {{status}}
- occurrences: {{occurrences}}
- evidence: {{evidence}}
<!-- /entry -->
