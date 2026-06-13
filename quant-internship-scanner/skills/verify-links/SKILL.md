---
name: verify-links
description: Controle qualite du CSV des stages — detecte doublons et quasi-doublons, liens malformes ou suspects, offres perimees (last_seen ancien, probablement fermees), et teste les liens morts en HTTP. Peut nettoyer/dedupliquer le CSV. A utiliser apres un scan, ou quand l'utilisateur veut verifier que les liens marchent et qu'il n'y a pas de doublons.
---

# Verify Links — controle qualite du CSV des stages

> **Chemin du CSV** : utilise le meme `OUT` que le scan, resolu via `locate_csv.py` (Etape 0 du
> skill `scan-internships`) — typiquement `<repo>/data/stages_quant_ds.csv`. Ne devine pas un autre chemin.

Audit **deterministe** (sans reseau) + **test de liens morts** (le reseau est fait par Claude).
Garantit un CSV propre : pas de doublons, liens valides, offres fermees reperees.

> **Prerequis** : le CSV doit EXISTER dans un dossier **connecte a Cowork** (ex. `<dossier_user>/stages_quant_ds.csv`).
> Si le fichier est absent, le script s'arrete avec une erreur claire (il ne cree jamais un CSV vide). Lance `/scan` d'abord.

**Dedup ELARGIE (pas seulement le lien exact).** Deux lignes sont consideres comme un meme stage si
**meme entreprise** ET (**meme URL normalisee** — http/https, www, slash final et parametres de
tracking ignores — OU **meme titre normalise** — casse, ponctuation et annee ignorees). `--fix`
les fusionne (garde le meilleur lien : non-suspect > https > plus court ; conserve le plus ancien
`first_seen`, le dernier `last_seen`, l'union des sources).

> `OUT = <dossier_user>/stages_quant_ds.csv`, `S = ${CLAUDE_PLUGIN_ROOT}/skills/scan-internships/sources.json`,
> `V = ${CLAUDE_PLUGIN_ROOT}/scripts/verify_links.py`.

## 1. Audit (toujours)

```
python $V OUT --sources S --stale-days 45 --report <dossier_user>/verif_stages.md
```
Detecte : doublons exacts, **quasi-doublons** (meme entreprise+titre, URLs differentes), liens
**malformes** ou **suspects** (LinkedIn/Indeed/agregateurs = pas des pages de candidature),
`in_europe` invalide ou `?` restants, **offres perimees** (`last_seen` > 45 j → probablement fermees),
buckets manquants. Le rapport markdown liste les cas a traiter.

## 2. Nettoyer / dedupliquer (si l'audit signale des soucis)

```
python $V OUT --sources S --fix
```
Re-normalise (espaces, filtre SWE, re-annote geo + bucket) et **deduplique** via l'ecrivain
deterministe. Conserve `first_seen`/`last_seen`/`source`. Idempotent.

## 3. Tester les liens morts (HTTP — Claude fait le reseau)

Le script **n'accede pas au reseau**. Procede en 3 temps :

1. Emets la liste des URLs a tester :
   ```
   python $V OUT --emit-check urls.json
   ```
2. **Claude teste chaque URL** par petits lots avec `mcp__workspace__web_fetch` (ou Chrome si JS).
   Une URL est "morte" si : erreur reseau, 404/410, ou page "offre expiree/cloturee". Rassemble les
   URLs mortes dans `dead.json` (liste de chaines). **Borne** : teste en priorite les offres
   Europe et les plus anciennes ; ne teste pas 500 liens d'un coup.
3. Applique le resultat :
   ```
   python $V OUT --apply-dead dead.json          # liste seulement (revue)
   python $V OUT --apply-dead dead.json --drop    # SUPPRIME les lignes mortes du CSV
   ```

## Enchainement recommande

`scan-internships` → `verify-links` (audit + fix + liens morts) → `format-xlsx` (Excel propre).
Apres le fix, **reformate** le `.xlsx` pour refleter le CSV nettoye.
