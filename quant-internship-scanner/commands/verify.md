---
description: Verifie le CSV des stages — doublons, liens suspects/morts, offres perimees — et peut le nettoyer/dedupliquer
---

Lance le skill `verify-links` (lis d'abord son `SKILL.md`).

1. **Audit** : `python ${CLAUDE_PLUGIN_ROOT}/scripts/verify_links.py <dossier_user>/stages_quant_ds.csv \
   --report <dossier_user>/verif_stages.md` (doublons, quasi-doublons, liens suspects, `in_europe`
   manquants, offres perimees `last_seen > 45j`).
2. **Nettoyage** (si besoin) : meme commande avec `--fix` (dedup + normalise).
3. **Liens morts (HTTP)** : `--emit-check urls.json` → Claude teste les URLs par lots
   (`mcp__workspace__web_fetch`) → ecrit `dead.json` → `--apply-dead dead.json [--drop]`.

Apres un `--fix`, relance `/format` pour rafraichir le `.xlsx`. Arguments : $ARGUMENTS
(ex. `--stale-days 30`).
