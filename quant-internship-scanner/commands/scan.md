---
description: Scanne les offres de stages quant / data science (Europe en priorité) et met à jour un CSV
---

Lance le skill `scan-internships` (lis d'abord son `SKILL.md`).

Déroulé attendu :

1. Lis `${CLAUDE_PLUGIN_ROOT}/skills/scan-internships/sources.json`.
2. **Couche agrégateurs / API** (la plus fiable) :
   - NUFT : `web_fetch` le README brut → écris-le dans un fichier `.md` → lance
     `python ${CLAUDE_PLUGIN_ROOT}/scripts/scan_nuft.py <md> <dossier_user>/stages_quant_ds.csv --sources ${CLAUDE_PLUGIN_ROOT}/skills/scan-internships/sources.json`
   - Ashby (OpenAI, labos) : `web_fetch` le JSON → fichier → `scan_ashby.py ... --company "OpenAI"`.
   - Si un endpoint (Greenhouse/site propre) timeout, **note-le et continue**.
3. **Couche WebSearch** pour les firmes prioritaires (banques + hedge funds Europe : BNP, SocGen,
   Citi, DE Shaw, G-Research, Marshall Wace…) non couvertes par les repos : extrais les vrais
   liens d'offre et upsert-les dans le même CSV.
4. **Résolution agentique** : relis les lignes `in_europe == "?"` et tranche-les (yes/no) avec ta
   connaissance géographique, puis réécris le CSV.
5. Présente `stages_quant_ds.csv` (UNIQUE, mis à jour en place — jamais recréé) et donne le récap :
   `+N NEW`, `M OPEN`, `K CLOSED`, et les sources en échec.

Arguments optionnels : $ARGUMENTS (ex. focus `bank_quant` / `hedge_fund_quant`, ville, année).
Sinon, priorité = finance quant en Europe (voir `_priority` de `sources.json`).
