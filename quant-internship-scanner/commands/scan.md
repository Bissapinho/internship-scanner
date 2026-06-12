---
description: Scanne (bimensuel) les stages quant QR/QT/QD & data science en naviguant de reference en reference, met a jour le CSV, le verifie et le formate en Excel
---

Lance le skill `scan-internships` (lis d'abord son `SKILL.md`), puis enchaine `verify-links` et `format-xlsx`.

Deroule attendu :

1. Lis `${CLAUDE_PLUGIN_ROOT}/skills/scan-internships/sources.json`.
2. **Couche DECOUVERTE (crawler borne depth-2)** : fetch les `crawl_seeds.pages`, lance
   `crawl_seeds.py` pour extraire les candidats (ATS allowlist, hors bruit, hors deja-connus),
   suis-les (≤ 2 sauts), injecte via `scan_addjobs.py --source "Crawl:<domaine>"`.
3. **Repos** (NUFT via `scan_nuft.py`, autres README) + **API** (Greenhouse/Lever/Ashby) +
   **WebSearch** (banques/HF Europe + `ds_targets` en `--ds-only`). Chaque couche est independante :
   si une source echoue, note-le et continue.
4. **Resous les `in_europe == "?"`** restants avec ta connaissance geo (ne touche qu'aux `?`).
5. **verify-links** : `verify_links.py <OUT> --report verif_stages.md` (doublons, liens suspects,
   offres perimees). Propose le test des liens morts si l'utilisateur le veut.
6. **format-xlsx** : `format_xlsx.py <OUT> <OUT_xlsx>` → presente le `.xlsx` et donne le recap
   (`+N nouveaux`, total, repartition par bucket, sources en echec).

Regles : un seul CSV persistant `stages_quant_ds.csv` (jamais recree), ecrit UNIQUEMENT par les
scripts. Crawler borne a 2 sauts + allowlist ATS. Tot dans le cycle, peu d'offres ouvertes = normal.

Arguments optionnels : $ARGUMENTS (ex. focus `bank_quant`/`hedge_fund_quant`, ville, annee,
`--include-careers` pour un crawl plus large). Sinon priorite = finance quant en Europe.
