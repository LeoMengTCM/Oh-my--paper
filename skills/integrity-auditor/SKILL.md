---
id: integrity-auditor
name: integrity-auditor
version: 1.0.0
description: |-
  Audit CS conference or journal paper integrity: claim-support alignment, result-to-claim consistency, numeric consistency, terminology consistency, figure/table-to-text consistency, existing citation existence, BibTeX metadata, and citation-context support. Use for evidence audit, citation audit, consistency check, 引用核验, claim审计, 数字一致性. Do not perform full scientific review or broad literature search.
stages:
  - "publication"
primaryIntent: review
intents:
  - "review"
capabilities:
  - "research-planning"
domains:
  - "cs-ai"
keywords:
  - "integrity-auditor"
  - "integrity"
  - "claim check"
  - "citation audit"
  - "number consistency"
  - "terminology"
  - "figure check"
  - "一致性核验"
  - "引用核查"
source: builtin
status: verified
handoffQuestionMode: partial
privateMaterialSafety: moderate
upstream:
  repo: mikubaka88/CCFA-Skills
  path: integrity-auditor
  revision: fd5c7e3afcc097d874d296a0e1e8118ae597f847
  license: MIT
---
# CCF Integrity Auditor

## Core Rule

Trace each important claim to supplied evidence, each number to supplied results, and each citation to a real cited work and a supported citation context. Mark unsupported items instead of repairing them by invention.

## Modes

- `claim-audit`: claim-support and result-to-claim consistency.
- `numeric-audit`: numbers, units, table/figure/text agreement, deltas, and metric direction.
- `citation-audit`: already cited papers, BibTeX metadata, duplicate keys, DOI/arXiv/venue sanity, and citation-context support.
- `full`: all integrity checks.

## Workflow

1. Identify supplied manuscript, figures/tables/results, bibliography, `ccfa.yaml`, and requested audit mode.
2. Build a claim-evidence matrix and mark each claim as supported, partially supported, unsupported, overstated, or unclear.
3. Cross-check all reported values across text, tables, figures, captions, abstracts, and conclusions.
4. For citation audit, verify only existing citations unless the user asks for new literature; broad search belongs to `inno-deep-research`.
5. For any questionable citation, separate metadata problems from context-support problems.
6. Hand off to `paper-reviewer` for full scientific judgment and to `paper-writing` for safe wording edits.
7. If the numbers and claims are consistent but the figure/table layout, caption placement, palette, float order, or rendered readability is weak, hand off to `inno-figure-gen`.

## Output Contract

```text
Mode:
Artifacts checked:
Claim-evidence matrix:
Numeric consistency findings:
Citation metadata findings:
Citation-context findings:
Severity:
Safe edit suggestions:
Next CCFA owner:
No-invention status:
```
