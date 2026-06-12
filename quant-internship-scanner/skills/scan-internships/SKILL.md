---
name: scan-internships
description: Scanne (cadence bimensuelle, 2x/mois) les stages d'ete quant (QR/QT/QD), data science poussee et finance quant en EUROPE, en NAVIGUANT de reference en reference (crawler borne depth-2) a partir de repos/boards, puis en injectant les offres dans un CSV canonique. A utiliser quand l'utilisateur veut chercher, decouvrir, lister ou suivre des stages quant / data science.
---

# Scan Internships — Stages quant & data science (v0.2, crawler + bimensuel)

Ce skill **decouvre** et collecte les offres de **stages d'ete** en **quant (QR/QT/QD)**,
**finance quant** et **data science poussee**, puis les ecrit dans un **CSV canonique unique**
(`stages_quant_ds.csv`). Cadence cible : **2x par mois** (bimensuel), pas hebdomadaire.

**Nouveaute clef vs v0.1 :** le plugin ne se contente plus d'une liste figee. Il **navigue de
reference en reference** : il part de pages-seed riches en liens (repos agregateurs, boards),
en extrait des liens vers de **nouvelles firmes / job boards**, les suit (profondeur **bornee a
2 sauts**, domaines en allowlist), et en tire des offres. Decouverte large mais maitrisee.

Architecture **hybride, a couches independantes** : si une couche echoue, les autres continuent.
On privilegie la couche la plus fiable (API/repos) avant le browsing. Les sources, mots-cles et
config du crawler vivent dans `sources.json` (meme dossier). **Lis-le en premier.**

**Schema CSV de sortie (9 colonnes, ecrit UNIQUEMENT par les scripts) :**
```
company,title,location,in_europe,bucket,source,url,first_seen,last_seen
```
`bucket` ∈ {bank_quant, hedge_fund_quant, data_scientist, data_science_ai, data_analyst, consulting_data}.
`in_europe` ∈ {yes,no,?}. `last_seen` est rafraichi a chaque scan → sert a reperer les offres fermees.

**Filtre TITRE (strict) :** on ne garde QUE des stages/internships. Gardes : intern, internship,
stage, summer (un « summer analyst » de banque EST un stage). **Rejetes en dur** par les scripts :
apprenticeship / apprenti / alternance / work-study, et les postes graduate / new grad qui ne sont
pas aussi des stages, ainsi que SWE. **Le CSV doit vivre dans un dossier connecte a Cowork.**

> Chemins : `R = ${CLAUDE_PLUGIN_ROOT}`, `S = $R/skills/scan-internships/sources.json`,
> `OUT = <dossier_user>/stages_quant_ds.csv`. **Tous les scripts sont sans reseau** : Claude fetch,
> les scripts parsent/ecrivent. **N'ecris JAMAIS le CSV a la main** (cause n°1 de colonnes decalees).

---

## Etape 1 — Couche DECOUVERTE (crawler "de reference en reference")

C'est le moteur central. Profondeur **max 2 sauts** (`crawl.max_depth`).

**Hop 0 — seeds.** Pour chaque page de `crawl_seeds.pages`, fetch-la :
- repos GitHub / pages texte → `mcp__workspace__web_fetch` (README brut).
- boards a rendu JS (OpenQuant, The Trackr) → **Claude in Chrome** (`navigate` + `get_page_text`).
Ecris chaque page dans un fichier local (`seed1.html`, `seed2.md`...).

**Extraction des candidats.** Lance le crawler sur les pages recuperees :
```
python $R/scripts/crawl_seeds.py seed1.html seed2.md --out queue.json \
    --csv OUT --sources S --found-on "<url_seed>" --max 60
```
→ `queue.json` = liste filtree `{url, kind, domain, company_guess, found_on}`. Le script :
- ne garde que les **domaines ATS de confiance** (greenhouse/lever/ashby/workday/...) + (option
  `--include-careers`) les pages "careers",
- **ignore le bruit** (LinkedIn, Indeed, reseaux sociaux) et les **domaines deja dans le CSV**,
- devine l'entreprise depuis le slug/anchor.

**Hop 1 — suivre les candidats.** Pour chaque entree de `queue.json` (priorise `kind: ats_board`
et `job_posting`), fetch l'URL (web_fetch pour les API/JSON ATS ; Chrome pour le HTML JS). Extrais
les offres en `{company, title, location, url}`. Si une page liste encore d'autres boards et qu'on
est **a moins de 2 sauts**, tu peux relancer `crawl_seeds.py` dessus (**hop 2 = profondeur max,
on s'arrete**).

**Injection.** Rassemble les offres trouvees dans un JSON et upsert-les (jamais a la main) :
```
python $R/scripts/scan_addjobs.py crawl_jobs.json OUT --sources S --source "Crawl:<domaine>"
```

> Borne stricte : ne JAMAIS suivre un lien au-dela de 2 sauts depuis une seed, ni un domaine hors
> allowlist `crawl.ats_domains`. C'est ce qui empeche le crawler de partir dans tous les sens.

## Etape 2 — Couche Repos/Agregateurs (rentable, structuree)

- **NUFT** (`github_nuft`, quant-only) : fetch le README brut → `nuft.md` → puis
  ```
  python $R/scripts/scan_nuft.py nuft.md OUT --sources S --bucket hedge_fund_quant --source "NUFT 2027"
  ```
  Structure = section `## Firme` + sous-table `|Role|Links|`. Sections vides = pas de role ouvert (normal).
- Autres `github_readme` (Simplify, vanshb03, LorenzoLaCorte) : gros README, **pagine** la lecture
  ou grep tes mots-cles. Rassemble en JSON → `scan_addjobs.py ... --source "<repo>"`.
- **Saisonnalite** : tot dans le cycle (ete→automne) la plupart des firmes n'ont pas ouvert
  (Jane Street ouvre en juillet, Two Sigma en aout). Un resultat maigre est NORMAL — signale-le.

## Etape 3 — Couche API (Greenhouse / Lever / Ashby, GET sans auth)

Pour chaque `api_sources`, recupere le JSON via `mcp__workspace__web_fetch` :
- **Greenhouse** : `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`
- **Lever** : `https://api.lever.co/v0/postings/{slug}?mode=json`
- **Ashby** : `https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true`
  → ecris la reponse en fichier → `scan_ashby.py ashby.json OUT --company "OpenAI" --sources S`.
Si un endpoint timeout : **note-le, passe la source en echec, continue** (jamais de curl/python requests).

## Etape 4 — Couche WebSearch (banques + hedge funds Europe, + DS pousse)

LE moteur pour les cibles prioritaires souvent injoignables (DE Shaw, BNP, SocGen, G-Research,
Marshall Wace...) et pour les `ds_targets`. Pour chaque firme/`search_fallback.query_templates`,
lance une `WebSearch` (ajoute un terme geo Europe). **Garde uniquement les liens d'offre reelle**
(page d'application), jamais articles/agregateurs, **jamais d'URL inventee**. Rassemble en JSON →
```
python $R/scripts/scan_addjobs.py jobs.json OUT --sources S --source "WebSearch"
# DS pur (filtre deterministe data scientist / ML / AI eng, rejette research/applied scientist) :
python $R/scripts/scan_addjobs.py jobs_ds.json OUT --sources S --source "WebSearch DS" --ds-only
```

## Etape 5 — Browse cible (Chrome, sites JS sans API)

Pour les `browse_sources` non couverts par l'API/crawl, utilise **Claude in Chrome**
(`navigate` + `get_page_text`, qui rend le JS). Couche plus lente/fragile : apres l'API. Si Chrome
indisponible, **saute** et note-le. AlumnEye = surtout pour les **dates de campagnes** FR.

---

## Etape 6 — Resolution geo + finalisation

Les scripts annotent `in_europe` et classent `bucket` automatiquement. Apres tous les scripts :
**resous les `in_europe == "?"`** restants en relisant le CSV et en corrigeant avec ta connaissance
geo (ex. « Santa Clara » → no, « Munich » → yes). Ne touche QU'AUX `?`. Si tu reecris, utilise un
writer CSV — jamais d'edition texte brute.

## Etape 7 — Format + verif (chaine complete)

Apres le scan, enchaine les deux autres skills du plugin :
1. **`verify-links`** : `python $R/scripts/verify_links.py OUT --sources S --report verif.md`
   (doublons, liens suspects, offres perimees). Pour tester les liens morts en HTTP, vois ce skill.
2. **`format-xlsx`** : `python $R/scripts/format_xlsx.py OUT <dossier_user>/stages_quant_ds.xlsx`
   → classeur Excel mis en forme (onglets Toutes / Europe / Finance quant / Resume).

Presente le `.xlsx` (`mcp__cowork__present_files`) et donne le recap : `+N nouveaux`, total,
repartition par bucket, sources en echec.

---

## Cadence bimensuelle (2x/mois)

Ce workflow est concu pour tourner **2 fois par mois** (planifiable plus tard via une scheduled
task — l'utilisateur la posera lui-meme). En mode planifie non-interactif : les couches
crawl(web_fetch)/repos/API/WebSearch tournent seules ; la couche **Chrome necessite une session
active** → si absente, saute-la et signale-le. Le CSV est persistant : `last_seen` permet de voir
ce qui n'est plus reapparu (offres probablement fermees, reperees par `verify-links`).

## Robustesse

- **Independance des couches** : une exception sur une source n'arrete jamais le scan. Logue, continue.
- **Pas de contournement reseau** : si web_fetch/WebSearch bloque, signale-le, ne passe pas par curl/requests.
- **Borne du crawler** : depth ≤ 2, allowlist ATS uniquement. Ne jamais ratisser hors de ce cadre.
- **Un seul CSV, jamais recree** : upsert par cle (company+title+url), `first_seen` conserve.
