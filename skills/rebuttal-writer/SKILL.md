---
id: rebuttal-writer
name: rebuttal-writer
version: 1.0.0
description: |-
  Write and organize CS conference rebuttals, author responses, response letters, revision summaries, reviewer-comment ledgers, and conservative resubmission adaptation plans. Use for rebuttal, author response, AC/meta-review response, revision ledger, resubmission to a new venue, 审稿意见回复, 重投迁移. Do not trigger for ordinary manuscript writing.
stages:
  - "publication"
primaryIntent: writing
intents:
  - "writing"
  - "review"
capabilities:
  - "research-planning"
domains:
  - "cs-ai"
keywords:
  - "rebuttal-writer"
  - "rebuttal"
  - "response letter"
  - "reviewer response"
  - "revision note"
  - "审稿回复"
  - "答辩"
source: builtin
status: verified
handoffQuestionMode: partial
privateMaterialSafety: moderate
upstream:
  repo: mikubaka88/CCFA-Skills
  path: rebuttal-writer
  revision: fd5c7e3afcc097d874d296a0e1e8118ae597f847
  license: MIT
---
# CCF Rebuttal Writer

## Core Rule

Handle post-review communication and revision accountability. Responses must be calm, factual, evidence-grounded, and promise only feasible changes. Resubmission adaptation is conservative by default: no new experiments and no bibliography changes unless the user explicitly authorizes them. Follow the user's requested response format: plain text, TeX, reviewer-by-reviewer, issue-grouped, table-first, or short response.

## Modes

- `rebuttal`: reviewer/AC response under a word or time budget.
- `revision-ledger`: reviewer comment -> action -> manuscript location -> owner -> status.
- `response-letter`: revision summary or camera-ready response letter.
- `resubmission`: adapt an already written paper to a new venue with conservative defaults.

## Workflow

1. Identify venue, response format, word budget, deadline, review scores/confidence, and whether this is rebuttal, revision, or resubmission.
2. Parse comments into issue groups by reviewer, concern type, severity, available evidence, response strategy, and promised paper change.
3. Load `references/response-strategy.md` and `../paper-writing/references/prose-quality-guardrails.md`; answer high-impact concerns first: soundness, novelty, missing evidence, incorrect assumptions, and shared concerns.
4. Load `references/revision-ledger.md` whenever promised edits, manuscript locations, resubmission actions, review rounds, or cross-version score changes must be tracked. Update one canonical ledger in place; do not create a separate ledger per round unless the user requests snapshots.
5. For full rebuttals, load `references/tex-templates.md` and use the TeX templates in `assets/templates/` when useful.
6. For resubmission, map old reviewer concerns to the new venue's constraints through `submission-checker`; do not silently add experiments or bibliography changes.
7. Hand off to `paper-writing` for manuscript revisions, `inno-experiment-dev` for authorized new evidence, and `submission-checker` for venue/package checks.

## Adaptive Output Contract

Put the requested response artifact first. For "write rebuttal", output the rebuttal text or TeX first. For "make a ledger", output the ledger first. Use the full structure below for standard multi-reviewer response planning or when the user asks for strategy plus draft:

```text
Mode:
Venue and constraints:
Issue table:
Response strategy:
Draft response or response file:
Promised paper changes:
Revision ledger:
Resubmission adaptation notes:
Claims/promises to avoid:
Next CCFA owner:
Checklist status:
```

## References

- `references/response-strategy.md`: response tactics.
- `references/response-checklists.md`: tone, evidence, promises, and word-budget checks.
- `../paper-writing/references/prose-quality-guardrails.md`: concise, non-defensive response prose and anti-pattern checks.
- `references/tex-templates.md`: reusable TeX response templates.
- `references/revision-ledger.md`: tracking reviewer comments and manuscript actions.
- `../paper-reviewer/references/version-comparison.md`: frozen scoring contract and issue provenance for cross-version review; rebuttal prose must not redefine that contract.
