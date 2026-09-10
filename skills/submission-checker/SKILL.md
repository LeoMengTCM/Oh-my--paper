---
id: submission-checker
name: submission-checker
version: 1.0.0
description: |-
  Check CS conference submission readiness: venue LaTeX/template/page/anonymity/camera-ready rules, LaTeX/PDF build, metadata, fonts, supplementary files, artifact/reproducibility package, code/data/model release plan, licenses, seeds, and policy freshness. Use for submission check, venue format, NeurIPS/CVPR/ICML template/page limit, artifact package, 投稿检查, 会议格式. Do not polish manuscript content.
stages:
  - "publication"
primaryIntent: review
intents:
  - "review"
  - "delivery"
capabilities:
  - "research-planning"
domains:
  - "cs-ai"
keywords:
  - "submission-checker"
  - "submission"
  - "camera ready"
  - "anonymity"
  - "page limit"
  - "template check"
  - "supplementary"
  - "投稿检查"
  - "匿名"
  - "页数"
source: builtin
status: verified
handoffQuestionMode: partial
privateMaterialSafety: moderate
upstream:
  repo: mikubaka88/CCFA-Skills
  path: submission-checker
  revision: fd5c7e3afcc097d874d296a0e1e8118ae597f847
  license: MIT
---
# CCF Submission Checker

## Core Rule

Treat submission as a build, venue-policy, page-budget, and artifact-readiness gate. Use local venue guides for expected rules, then require official-policy freshness for final decisions. Do not rewrite paper content.

## Modes

- `venue-format`: template, page limit, anonymity, author block, supplementary and camera-ready rules.
- `package-check`: LaTeX/PDF build, metadata, fonts, page count, file structure, and submission checklist.
- `artifact`: code/data/model release plan, environment, seeds, hardware, licenses, artifact README, and reproducibility appendix.
- `full`: venue + package + artifact.

## Workflow

1. Identify venue/year/track, submission mode, project directory, TeX/PDF files, supplementary/artifact files, and deadline pressure.
2. Read `ccfa.yaml` when available. If absent, proceed with supplied files and state that project-state tracking is unavailable.
3. For venue questions, read `../paper-writing/references/venue-guides/index.md` and the specific venue guide before checking official freshness.
4. For package checks, inspect compile status, page count, target page budget, anonymity, fonts, PDF metadata, template path, references, supplementary files, and required forms.
5. For artifact checks, build a reproducibility checklist: code, data, models, environment, seeds, hardware, license, access restrictions, and README.
6. Hand off to `paper-writing` for text/page rewrites: compression when over limit, expansion when a full manuscript is materially underfilled, and normal polishing when within budget. Hand off to `inno-experiment-dev` for missing reproducibility experiments, `inno-figure-gen` for figure/table float order, caption placement, font, clipping, palette, or visual readability fixes, and `rebuttal-writer` for post-review response packaging.

## Output Contract

```text
Mode:
Venue and rule freshness:
Files checked:
Pass/fail checklist:
Build/package issues:
Anonymity/page/font/metadata issues:
Length budget status:
Artifact/reproducibility issues:
Required fixes:
Next CCFA owner:
```
