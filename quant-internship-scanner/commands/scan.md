---
description: Scanne les offres de stages d'été quant / data science et exporte un CSV
---

Lance le skill `scan-internships`.

Suis son workflow complet : lis `sources.json`, exécute la couche API puis (si Chrome dispo) la
couche Browse, puis le filet WebSearch, filtre, déduplique, et écris le CSV
`stages_quant_ds_YYYY-MM-DD.csv` dans le dossier de l'utilisateur.

Arguments optionnels de l'utilisateur (s'il y en a) : $ARGUMENTS
(ex. une année cible différente, un focus "finance only" ou "data science only", ou une ville).
Si vide, utilise les réglages par défaut de `sources.json`.

Termine par le récap : nombre d'offres par couche et sources en échec.
