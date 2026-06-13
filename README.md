# Bissap Marketplace — Cowork plugins

Marketplace perso de plugins Cowork. Contient pour l'instant **quant-internship-scanner** (v0.2).

## quant-internship-scanner

Scanne les ouvertures de **stages d'été** (summer internships) en **quant (QR/QT/QD)**, **finance
quant** et **data science poussée**, puis maintient un **CSV canonique** unique (`stages_quant_ds.csv`)
avec une colonne `in_europe` (yes/no/?) et un `bucket` (catégorie de rôle). Cadence cible :
**bimensuelle (2×/mois)**.

Rôles classés par priorité :

- **PRIORITÉ 1 — bank_quant** : quant en banque (BNP Paribas, Société Générale, Citi, Barclays,
  Deutsche Bank, HSBC, JPMorgan EMEA) — quant / strats / model validation / XVA.
- **PRIORITÉ 1 — hedge_fund_quant** : QR / QT / QD en hedge funds (G-Research, Marshall Wace,
  Man Group, Qube/QRT, Capula, Aspect, + bureaux EU de Citadel, DE Shaw, Point72, Jane Street…).
- **data_scientist** : stages **Data Scientist / ML Engineer / AI Engineer** en grosse boîte
  tech/fintech Europe (Revolut, Meta, Amazon, Spotify, Booking, Adyen, Wise…). Research/applied
  scientist & AI researcher exclus via `scan_addjobs.py --ds-only`.
- **Secondaire** : data_science_ai / data_analyst / consulting_data.

Les offres hors Europe ne sont **pas supprimées** : elles sont marquées `in_europe = no` (US/Asie)
ou `?` (inconnu), pour filtrer selon le besoin.

### Filtre titre (v0.2)

On ne garde **que des stages / internships** : intern, internship, stage, summer (un « summer
analyst » de banque est un stage). Rejetés en dur : **apprenticeship / apprenti / alternance /
work-study**, les postes **graduate / new grad** qui ne sont pas aussi des stages, et les postes SWE.

### Architecture (couches indépendantes, par ordre de priorité)

0. **Découverte / crawler (v0.2)** — `crawl_seeds.py` part de pages-seed (repos, boards), en extrait
   les liens vers de **nouvelles firmes / job boards** et les suit **de référence en référence**,
   profondeur **bornée à 2 sauts** et **allowlist d'ATS** (greenhouse/lever/ashby/workday…). Le bruit
   (LinkedIn, Indeed…) et les domaines déjà connus sont ignorés.
1. **Aggregator** — repos GitHub maintenus (NUFT 2027 Quant, SimplifyJobs, vanshb03) + boards.
2. **API** — endpoints JSON publics Greenhouse / Lever / Ashby.
3. **Browse** — Claude in Chrome pour les sites custom en JS.
4. **Search** — WebSearch en filet de sécurité (banques + hedge funds Europe, + cibles data scientist).

Principe clé : **seuls les scripts écrivent le CSV** (déterministe, anti-décalage de colonnes) ;
l'agent collecte et passe des JSON aux scripts. Aucun accès réseau dans les scripts.

### Schéma CSV (9 colonnes)

```
company,title,location,in_europe,bucket,source,url,first_seen,last_seen
```

`last_seen` est rafraîchi à chaque scan → permet de repérer les offres qui n'ont pas réapparu
(probablement fermées).

### Dossier `data/` (persistance de l'historique)

Le scanner maintient **un seul CSV canonique**, `data/stages_quant_ds.csv`, qui sert de base de
données persistante : à chaque scan, les offres sont **upsertées** (les nouvelles ajoutées avec leur
`first_seen`, les anciennes conservées avec `last_seen` rafraîchi). C'est ce qui permet de suivre
l'évolution des offres dans le temps et de repérer celles qui ont fermé.

- Le dossier `data/` **existe dans le repo** (suivi via `.gitkeep`), mais son **contenu est
  gitignoré** : le CSV et ses sauvegardes restent **locaux**, jamais commités.
- À chaque écriture, l'ancien CSV est copié en `stages_quant_ds.csv.bak` (sauvegarde rotative) —
  un scan raté reste récupérable.
- Avant chaque scan, `scripts/locate_csv.py` retrouve ce CSV parmi les dossiers connectés pour
  garantir qu'on **réutilise toujours le même historique** (jamais de redémarrage à zéro).

### Skills & commandes

- **`scan-internships`** (`/scan`) — découverte + collecte multi-couches → met à jour le CSV.
- **`verify-links`** (`/verify`) — audit qualité : doublons et **quasi-doublons** (URL normalisée
  + titre normalisé), liens suspects/morts (test HTTP par l'agent), offres périmées ; `--fix`
  déduplique et nettoie.
- **`format-xlsx`** (`/format`) — génère un classeur Excel mis en forme (onglets Toutes / Europe /
  Finance quant / Résumé, couleurs par bucket, liens cliquables).

La fin de chaîne est orchestrée par `scripts/finalize.py` (une commande : dedup `--fix` + rapport +
Excel + **journal** `data/scan_log.csv`, une ligne par scan : date, total, +N, périmées, sources OK/échec).

Le CSV vit dans un dossier **connecté à Cowork** ; les skills `verify`/`format` s'arrêtent avec une
erreur claire si le CSV n'existe pas (ils n'en créent jamais un vide).

### Évolution possible

Le workflow est prévu pour tourner en **tâche planifiée 2×/mois**. En mode non-interactif, les
couches crawler(web_fetch)/repos/API/WebSearch tournent seules ; la couche Chrome nécessite une
session active.
