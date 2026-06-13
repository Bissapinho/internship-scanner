---
description: Scanne (bimensuel) les stages quant QR/QT/QD & data science en naviguant de reference en reference, met a jour le CSV, le verifie et le formate en Excel
---

Lance le skill `scan-internships` (lis d'abord son `SKILL.md`). La finalisation (dedup + verif +
Excel + journal) est orchestree par `finalize.py`.

Deroule attendu :

1. **Localise le CSV** (continuite) : `python ${CLAUDE_PLUGIN_ROOT}/scripts/locate_csv.py --roots <dossiers connectes> --default <repo>/data/stages_quant_ds.csv` → utilise ce chemin comme `OUT`.
2. Lis `${CLAUDE_PLUGIN_ROOT}/skills/scan-internships/sources.json`.
3. **Couche DECOUVERTE (crawler borne depth-2)** : fetch les `crawl_seeds.pages`, lance
   `crawl_seeds.py` pour extraire les candidats (ATS allowlist, hors bruit, hors deja-connus),
   suis-les (≤ 2 sauts), injecte via `scan_addjobs.py --source "Crawl:<domaine>"`.
4. **Repos** (NUFT via `scan_nuft.py`, autres README) + **API** (Greenhouse/Lever/Ashby) +
   **WebSearch** (banques/HF Europe + `ds_targets` en `--ds-only`). Chaque couche est independante :
   si une source echoue, note-le et continue.
5. **Resous les `in_europe == "?"`** restants avec ta connaissance geo (ne touche qu'aux `?`).
6. **Finalisation (orchestrateur)** : `python ${CLAUDE_PLUGIN_ROOT}/scripts/finalize.py <OUT> --sources S`
   `[--added N] [--sources-ok "..."] [--sources-fail "..."]` → dedup `--fix`, rapport, Excel, et
   journal `data/scan_log.csv`. Presente le `.xlsx` (`mcp__cowork__present_files`) et relaie le recap.

Regles : un seul CSV persistant `stages_quant_ds.csv` (jamais recree), ecrit UNIQUEMENT par les
scripts. Crawler borne a 2 sauts + allowlist ATS. Tot dans le cycle, peu d'offres ouvertes = normal.

Arguments optionnels : $ARGUMENTS (ex. focus `bank_quant`/`hedge_fund_quant`, ville, annee,
`--include-careers` pour un crawl plus large). Sinon priorite = finance quant en Europe.
