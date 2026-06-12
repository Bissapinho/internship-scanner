---
name: format-xlsx
description: Transforme le CSV des stages (stages_quant_ds.csv) en classeur Excel propre et lisible — couleurs par categorie de role, badges Europe, liens cliquables, onglets Toutes/Europe/Finance quant/Resume. A utiliser apres un scan, ou quand l'utilisateur veut un joli tableur Excel de ses offres de stage.
---

# Format XLSX — rendre le CSV des stages en Excel mis en forme

Le **CSV reste la base de donnees canonique** (deterministe, dedup, diff entre scans). Ce skill
en derive un **classeur Excel lisible** sans jamais le modifier — sortie de presentation seulement.

## Entree / sortie

- Entree : `stages_quant_ds.csv` (9 colonnes : company,title,location,in_europe,bucket,source,url,first_seen,last_seen).
- Sortie : `stages_quant_ds.xlsx`.

## Procedure

1. Verifie que le CSV existe (sinon lance d'abord le skill `scan-internships`).
2. Lance :
   ```
   python ${CLAUDE_PLUGIN_ROOT}/scripts/format_xlsx.py <dossier_user>/stages_quant_ds.csv \
       <dossier_user>/stages_quant_ds.xlsx
   ```
3. Presente le `.xlsx` avec `mcp__cowork__present_files`.

## Ce que produit le classeur

- **Onglet Resume** : compte par categorie (bucket) et par localisation (Europe/?/hors).
- **Onglet Toutes** : toutes les offres, triees finance quant d'abord.
- **Onglet Europe** : `in_europe ∈ {yes, ?}` (cibles prioritaires geographiquement).
- **Onglet Finance quant** : buckets `bank_quant` + `hedge_fund_quant`.
- Mise en forme : en-tete fige + filtres auto + volets geles ; **couleur de ligne par categorie** ;
  **badge couleur** sur Europe (vert/rouge/orange) ; colonne **Lien cliquable** ("ouvrir l'offre").

Le script est sans reseau et idempotent : on peut le relancer apres chaque scan pour rafraichir le `.xlsx`.

## Dependance

`openpyxl` (preinstalle dans le bac-a-sable). Si absent : `pip install openpyxl --break-system-packages`.
