---
description: Scanne les offres de stages quant + data scientist (Europe), vérifie les liens, met à jour un CSV
---

Lance le skill `scan-internships` (lis d'abord son `SKILL.md`). Exécute **TOUTES** les étapes
ci-dessous dans l'ordre — n'en saute aucune. `CSV = <dossier_user>/stages_quant_ds.csv`,
`SRC = ${CLAUDE_PLUGIN_ROOT}/skills/scan-internships/sources.json`.

1. Lis `SRC`.

2. **Couche NUFT** : `web_fetch` le README brut → fichier `nuft.md` → puis
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/scan_nuft.py nuft.md CSV --sources SRC`

3. **Couche finance (banques + hedge funds Europe)** : pour chaque firme prioritaire (BNP, SocGen,
   Citi, Barclays, DB, HSBC, JPM, DE Shaw, G-Research, Marshall Wace, Man Group, Qube, Capula…),
   `WebSearch` l'offre réelle. **Vérifie chaque lien (étape 5) AVANT de le retenir.** Rassemble les
   offres vivantes dans `jobs_fin.json` ({company,title,location,url}) → puis
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/scan_addjobs.py jobs_fin.json CSV --sources SRC --source "WebSearch finance"`

4. **Couche Data Scientist / ML & AI Engineer** (OBLIGATOIRE — ne pas l'oublier) : parcours
   `ds_targets.companies` (Revolut, Meta, Amazon, Spotify, Booking, Adyen, Wise…). `WebSearch`
   `{company} data scientist OR ML engineer OR AI engineer internship 2027 {city}`. **Vérifie les
   liens (étape 5).** Rassemble dans `jobs_ds.json` → puis
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/scan_addjobs.py jobs_ds.json CSV --sources SRC --source "WebSearch DS" --ds-only`

5. **Vérification des liens (anti-offres-mortes)** : pour chaque URL trouvée par WebSearch,
   `web_fetch` la page. **Écarte** l'offre si la page indique clairement qu'elle est fermée :
   « position has been filled », « no longer accepting / available », « applications closed »,
   « expired », ou page 404 / introuvable. **Garde** l'offre si la page est vivante, OU si elle est
   injoignable / timeout / ambiguë (ne jamais supprimer sur un simple échec de chargement). Ne mets
   dans les `jobs_*.json` que des offres vérifiées vivantes.

6. **Finalisation (TOUJOURS, en dernier)** :
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/finalize.py CSV --sources SRC`
   Ce passage dé-virgule les locations, **recalcule `in_europe`**, retire SWE/doublons — il
   garantit un CSV propre même si une ligne a été ajoutée à la main.

7. Présente le CSV (`mcp__cowork__present_files`) et donne le récap (nouveaux, total, sources en échec).

Arguments optionnels : $ARGUMENTS (ex. `finance only`, `ds only`, une ville, une année).
