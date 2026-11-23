# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-0999879e` (track: `academic-review`).

This repository contains the complete skill package for this challenge: the skill
definition, the executable entry point and every supporting script needed to run it.
No precomputed answers, no private data and no credentials are included.

## Skill

- Name: `manuscript-quality-structure-audit`
- Summary: Use when a manuscript must be audited for overall quality and structural completeness, requiring section detection, abstract-to-conclusion alignment, abstract-to-body numeric consistency, citation-marker integrity, located unsupported strong claims, severity-rated findings and an explicit unverifiable list.

## Contents

| File |
|------|
| `SKILL.md` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/run_skill.py --case /input/case.json --output /app/output/result.json
```

The entry point is `SKILL.md`; input and output contracts, error handling and a
minimal usage example are documented there.

## Notes

- Pure Python standard library; no network access required.
- The result JSON keeps the input case id, the main results, per-item evidence,
  a run status and an uncertainty section.
