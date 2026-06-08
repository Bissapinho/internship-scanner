---
name: scan-internships
description: Scanne les ouvertures de stages d'été (summer internships) en data science et quantitative finance chez les grandes firmes (D.E. Shaw, Citadel, QuantumBlack, Jane Street, HRT, etc.) et exporte les offres trouvées dans un fichier CSV. À utiliser quand l'utilisateur veut chercher, lister ou suivre des offres de stage quant / data science.
---

# Scan Internships — Stages quant & data science

Ce skill collecte les offres de **stages d'été** (summer internships) en **data science** et
**quantitative finance**, puis les écrit dans un **CSV**.

L'architecture est **hybride et à couches indépendantes** : si une couche échoue, les autres
continuent. On privilégie toujours la couche la plus fiable (API) avant de tomber sur le browsing.

Les sources et mots-clés vivent dans `sources.json` (même dossier). **Lis ce fichier en premier.**

---

## Étape 0 — (à faire une fois) Vérifier les slugs

Les `slug` des `api_sources` sont des **hypothèses**. Avant le premier vrai scan, vérifie chacun :

- Greenhouse : `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`
- Lever : `https://api.lever.co/v0/postings/{slug}?mode=json`

Si l'URL renvoie une liste de jobs → mets `"verified": true` dans `sources.json`.
Si elle renvoie 404 → le slug est faux : cherche le bon (WebSearch `{company} greenhouse OR lever careers`)
ou bascule la firme dans `browse_sources`.

---

## Étape 1 — Couche Agrégateurs (LA PLUS RENTABLE, à faire en premier)

Avant toute chose, exploite `aggregator_sources` : des listes déjà curées (repos GitHub maintenus +
boards quant/finance) qui couvrent d'un coup QR/QT/QD, data analyst, data science/AI et le consulting data.

- `type: github_nuft` (NUFT) → **quant-only**. Le README n'est PAS un tableau plat : c'est une
  section `## Firme` par entreprise, avec une sous-table `|Role|Links|`. **Beaucoup de sections
  sont vides** tant que le rôle n'est pas ouvert — ignore-les. Source plus propre : les fichiers
  `./data/*.yml` du repo. (Vérifié juin 2026 : branche `main` OK.)
- `type: github_readme` (Simplify, vanshb03) → gros README (≈70 Ko), **pagine** la lecture
  (offset/limit) ou grep les lignes contenant tes mots-clés. Tableau plat
  Company / Role / Location / Link. Si 404 : la branche a changé (essaie `main` ↔ `dev`).
- **Saisonnalité** : tôt dans le cycle (été → automne) la plupart des firmes n'ont pas encore
  ouvert (Jane Street ouvre en juillet, Two Sigma en août). Un résultat quasi vide est normal,
  pas une erreur — signale-le dans le récap.
- `type: browse` (OpenQuant, The Trackr, AlumnEye) → rendu JS, passe par Claude in Chrome (étape 3).

Classe chaque offre dans un `role_bucket` (`keywords.role_buckets`) : `quant_finance`, `data_analyst`,
`data_science_ai`, `consulting_data`. Ce bucket ira dans le CSV.

## Étape 2 — Couche API (Greenhouse / Lever, rapide et fiable)

Pour chaque entrée de `api_sources`, récupère le JSON via la couche réseau autorisée.

**Greenhouse** — `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`
Chaque job : `title`, `location.name`, `absolute_url`, `updated_at`.

**Lever** — `GET https://api.lever.co/v0/postings/{slug}?mode=json`
Chaque job : `text` (titre), `categories.location`, `hostedUrl`, `createdAt`.

Ces endpoints sont du JSON public : utilise `mcp__workspace__web_fetch`. Si bloqué, NE PAS
contourner par curl/python — passe la source en échec et continue.

---

## Étape 3 — Couche Browse (Claude in Chrome, pour sites JS / sans API)

Pour chaque entrée de `browse_sources`, utilise les outils **Claude in Chrome** :
`mcp__Claude_in_Chrome__navigate` puis `mcp__Claude_in_Chrome__get_page_text` (rend le JS,
contrairement à web_fetch). Applique les filtres décrits dans le champ `note` de chaque source.

- Cette couche est **plus lente et plus fragile** : exige un navigateur connecté. Traite-la
  après l'API. Si Chrome n'est pas dispo, **saute cette couche** et note-le dans le rapport
  final — ne bloque jamais le scan entier.
- **AlumnEye** est précieux surtout pour les *dates de campagnes* (ouverture/fermeture des
  summers) des écoles de commerce FR. Récupère ces dates si présentes.

---

## Étape 4 — Couche WebSearch (LE moteur pour banques + hedge funds Europe)

C'est la couche la plus importante pour les cibles prioritaires (DE Shaw, BNP, SocGen, G-Research,
Marshall Wace…), dont les sites propres sont souvent injoignables et qui ne sont pas dans les repos.

Pour chaque firme prioritaire / `search_fallback.extra_companies`, lance une `WebSearch` avec les
`query_templates` (ajoute un terme géo Europe). Garde uniquement les liens menant à une **offre
réelle** (page d'application), jamais des articles ou agrégateurs génériques. **Vérifie que l'URL
n'est pas factice** (pas d'URL inventée — uniquement celles réellement renvoyées par la recherche).

Rassemble ces offres dans un fichier JSON (`jobs.json`, liste de `{company, title, location, url}`),
puis injecte-les via `scan_addjobs.py` (voir Étape 6). **N'écris jamais ces lignes dans le CSV à
la main** — c'est la cause n°1 des colonnes décalées.

---

## Étape 5 — Filtrage (Europe + priorité banque/HF)

Garde une offre seulement si les TROIS conditions sont vraies :

1. **Titre** : contient un mot de `keywords.include_title` **ET** un mot de `keywords.include_type`.
   **Les postes SWE / software engineer sont exclus automatiquement par les scripts.**
2. **GÉO — colonne `in_europe` (ne rien exclure)** : dérive `in_europe` de la localisation via
   `keywords.geo` → `"yes"` si elle matche `include_cities`/`include_regions`, `"no"` si elle
   matche `exclude` (US/Asie), `"?"` si inconnue. **Garde TOUTES les offres** ; l'utilisateur
   filtre ensuite sur cette colonne dans le CSV.

   **Résolution agentique des `?`** : le matching par sous-chaîne ne reconnaît pas tout (codes
   d'État US, villes inconnues). Après le scan, relis les lignes `in_europe == "?"` et corrige-les
   en `yes`/`no` avec ta propre connaissance géographique (ex. « Santa Clara » → no, « Munich » →
   yes), puis réécris le CSV. Ne touche qu'aux `?`, laisse les `yes`/`no` du script.
3. **Année** : correspond à `target_year` (ou prochaine campagne d'été évidente). Si absente,
   garde et marque `year = "à confirmer"`.

**Priorité** : les buckets `bank_quant` et `hedge_fund_quant` (priority 1) passent en tête.
`data_science_ai`, `data_analyst`, `consulting_data` (priority 3) sont secondaires — inclus
seulement après, jamais au détriment des offres finance.

**Nettoyage automatique (fait par les scripts via `internship_common.clean`)** : normalisation des
espaces, suppression des lignes **sans entreprise** / sans titre / sans url, et **suppression des
postes SWE / software engineer**.

**Déduplique** par (entreprise + titre + url).

---

## Étape 6 — Sortie CSV (UPSERT dans un fichier unique persistant)

**Règle clé : on ne recrée JAMAIS un nouveau CSV.** Le scan met à jour **un seul fichier
persistant** dans le dossier de l'utilisateur : `stages_quant_ds.csv` (sans date dans le nom).

En-tête EXACT (6 colonnes, rien d'autre) :

```
company,title,location,in_europe,url,first_seen
```

`in_europe` ∈ {yes, no, ?}. Upsert (clé = `company` + `title` + `url`) : offre nouvelle → ajoutée
avec `first_seen` = aujourd'hui ; offre déjà présente → conservée (on garde son `first_seen`).
Dédup par cette clé.

### ⚠️ RÈGLE ABSOLUE — n'écris JAMAIS le CSV à la main

Toutes les sources (NUFT, Ashby, **et surtout WebSearch**) passent par les scripts du plugin, qui
sont les SEULS à écrire le CSV. Écrire ou éditer le CSV toi-même provoque des colonnes décalées
(« oui » dans url, ville dans in_europe, etc.). Donc :

**NUFT** : `web_fetch` le README brut → fichier `nuft.md` → puis
```
python ${CLAUDE_PLUGIN_ROOT}/scripts/scan_nuft.py nuft.md <dossier_user>/stages_quant_ds.csv \
    --sources ${CLAUDE_PLUGIN_ROOT}/skills/scan-internships/sources.json
```

**Ashby (OpenAI/labos)** : `web_fetch` le JSON → fichier `ashby.json` → puis
```
python ${CLAUDE_PLUGIN_ROOT}/scripts/scan_ashby.py ashby.json <dossier_user>/stages_quant_ds.csv \
    --company "OpenAI" --sources ${CLAUDE_PLUGIN_ROOT}/skills/scan-internships/sources.json
```

**WebSearch** (banques + hedge funds Europe) : rassemble les offres trouvées dans un fichier JSON
(liste d'objets `{company, title, location, url}`) → puis
```
python ${CLAUDE_PLUGIN_ROOT}/scripts/scan_addjobs.py jobs.json <dossier_user>/stages_quant_ds.csv \
    --sources ${CLAUDE_PLUGIN_ROOT}/skills/scan-internships/sources.json --source "WebSearch"
```

Tous les scripts appliquent automatiquement : nettoyage, **filtre SWE** (postes software engineer
supprimés), annotation `in_europe`, upsert. Aucun accès réseau dans les scripts.

Après tous les scripts, **résous les `in_europe == "?"`** restants en relisant le CSV et en
corrigeant avec ta connaissance géo (ne touche qu'aux `?`). Si tu réécris le CSV, utilise un
writer CSV (préserve les guillemets) — n'édite jamais le texte brut à la main. Puis présente le fichier
(`mcp__cowork__present_files`) et donne le récap (`+N nouveaux`, total, sources en échec).
Tôt dans le cycle, peu d'offres sont ouvertes — un résultat maigre est normal.

---

## Notes de robustesse

- **Indépendance des couches** : une exception sur une source ne doit jamais arrêter le scan.
  Enveloppe chaque source, logue l'échec, continue.
- **Pas de contournement réseau** : si web_fetch/WebSearch est bloqué, signale-le, ne passe pas
  par curl/wget/python requests.
- **Évolution** : une fois le CSV validé, ce même workflow peut tourner en *scheduled task*
  quotidienne (la couche API tourne seule ; la couche Chrome nécessite une session active).
