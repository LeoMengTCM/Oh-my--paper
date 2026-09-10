# Source Notes

Use this file only when source provenance matters, when updating venue assumptions, or when explaining where exemplar records came from.

## Shared Registry

The authoritative CCFA source inventory is:

```text
../../_shared/source-registry.yaml
```

Do not duplicate long URL lists in this skill. Add or update public source records in the shared registry, then run:

```powershell
python ..\_shared\scripts\check_sources.py
```

## Writing-Skill Use Rules

- Use source records only for provenance, venue-policy checks, exemplar source tracking, and update auditing.
- Use exemplar papers only to extract transferable writing moves: section structure, paragraph roles, claim-evidence patterns, figure/table narration, and reviewer-facing rhythm.
- Do not copy paper wording, claims, examples, technical content, or distinctive phrasing.
- Before a real submission, verify the target venue's current author instructions, review criteria, page limits, anonymity policy, supplementary material rules, artifact policy, and ethics requirements from official venue pages.
- Before claiming award status in a paper, slide, README, or public text, verify the current official venue award page.

## Local Records

Local PDFs under `paper_ref/` are convenience copies for exemplar analysis. Treat the shared registry as the source record and the local PDFs as optional inspection artifacts. If a local PDF is missing or stale, use public source records only after respecting private-material safety from `../../_shared/privacy-and-evidence.md`.
