# Bissap Marketplace — Cowork plugins

Marketplace perso de plugins Cowork. Contient pour l'instant **quant-internship-scanner**.

## quant-internship-scanner

Scanne les ouvertures de **stages d'été** (summer internships) et exporte les offres dans un
**CSV** avec une colonne `in_europe` (yes/no/?) pour filtrer par zone. Rôles classés par priorité :

- **PRIORITÉ 1 — bank_quant** : quant en banque (BNP Paribas, Société Générale, Citi, Barclays,
  Deutsche Bank, HSBC, JPMorgan EMEA) — quant / strats / model validation / XVA.
- **PRIORITÉ 1 — hedge_fund_quant** : QR / QT / QD en hedge funds (G-Research, Marshall Wace,
  Man Group, Qube/QRT, Capula, Aspect, + bureaux EU de Citadel, DE Shaw, Point72, Jane Street…).
- **Secondaire — data_science_ai / data_analyst / consulting_data** : DS/ML (DeepMind, OpenAI…),
  data analyst, labos data des cabinets — inclus seulement après la finance.

Les offres hors Europe ne sont **pas supprimées** : elles sont marquées `in_europe = no` (US/Asie)
ou `?` (inconnu), pour que tu puisses filtrer selon ton besoin.

### Architecture (4 couches indépendantes, par ordre de priorité)

1. **Aggregator** — listes déjà curées et structurées : repos GitHub maintenus
   (NUFT 2027 Quant, SimplifyJobs, vanshb03) + boards (OpenQuant, The Trackr, AlumnEye).
   La couche la plus rentable, lue en raw Markdown sans anti-bot.
2. **API** — endpoints JSON publics Greenhouse / Lever.
3. **Browse** — Claude in Chrome pour les sites custom en JS (Jane Street, Citadel, DeepMind, BCG…).
4. **Search** — WebSearch en filet de sécurité pour les firmes sans source fiable.

Si une couche échoue (slug invalide, Chrome non connecté…), les autres continuent.

### Installation

Dans Cowork :

```
/plugin marketplace add <ton-user-github>/<ton-repo>
/plugin install quant-internship-scanner@bissap-marketplace
```

### Utilisation

```
/scan
```

Met à jour **un CSV unique persistant** `stages_quant_ds.csv` (upsert, jamais recréé), **6 colonnes** :
`company, title, location, in_europe, url, first_seen`.

La colonne **`in_europe`** (yes / no / ?) est dérivée de la localisation via `keywords.geo`.
**Aucune offre n'est exclue géographiquement** — tu filtres toi-même sur cette colonne.
Les **postes SWE / software engineer sont retirés** automatiquement.

À chaque re-scan, les nouvelles offres sont ajoutées (avec leur `first_seen`) et les offres déjà
présentes sont conservées (dédup par company+title+url). **Toutes les sources écrivent le CSV via
les scripts** (`scan_nuft.py`, `scan_ashby.py`, `scan_addjobs.py`) — jamais à la main, pour éviter
toute colonne décalée.

### Avant le premier vrai scan

Les `slug` des `api_sources` dans
`quant-internship-scanner/skills/scan-internships/sources.json` sont des **hypothèses**.
Vérifie-les (étape 0 du SKILL.md) et passe `verified: true`, ou bascule la firme en `browse`.

### Roadmap

- [x] Parser NUFT (quant) + upsert CSV persistant — fait & testé (`scripts/scan_nuft.py`)
- [ ] Écrire les parseurs API (Greenhouse/Lever) + browse (DeepMind, BCG…) sur le même upsert
- [ ] Vérifier / compléter les slugs Greenhouse & Lever
- [ ] Passer en **scheduled task** quotidienne (notifier uniquement les `NEW`)
- [ ] Sortie alternative en **artifact live** (page qui se rafraîchit) ou Excel

### Structure du repo

```
.
├── .claude-plugin/
│   └── marketplace.json
├── quant-internship-scanner/
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── commands/
│   │   └── scan.md
│   ├── scripts/
│   │   ├── internship_common.py  # nettoyage + filtre SWE + géo + upsert CSV (6 col.)
│   │   ├── scan_nuft.py          # parseur NUFT (hedge funds quant)
│   │   ├── scan_ashby.py         # parseur Ashby JSON (OpenAI/labos IA)
│   │   └── scan_addjobs.py       # injecte les offres WebSearch (banques/HF) sans dérive
│   └── skills/
│       └── scan-internships/
│           ├── SKILL.md
│           └── sources.json
└── README.md
```
