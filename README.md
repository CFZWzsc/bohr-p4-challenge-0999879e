# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-0999879e` (track: `academic-review`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable pipeline and all supporting documents. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `manuscript-quality-structure-audit`
- Summary: Use when a manuscript must be audited for overall quality and structural completeness, requiring section detection, abstract-to-conclusion alignment, abstract-to-body numeric consistency, citation-marker integrity, located unsupported strong claims, severity-rated findings and an explicit unverifiable list.

## Contents

| File |
|------|
| `SKILL.md` |
| `examples/demo-case/case.json` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/sk_entry.py --input /input --work /app/work --out /app/output
```

A single deterministic pass reads `/input`, computes the deliverable and writes a
contract-complete `/app/output/result.json` plus the human-readable review files
described in `SKILL.md`. The same input always produces byte-identical output; no
network access is used, and fields the materials cannot support are reported
explicitly instead of being left empty.

## Notes

- Pure Python standard library; no network access required.
- Every claim is anchored to paragraph-level evidence; unknown items are reported
  in `uncertainty` instead of being fabricated.
