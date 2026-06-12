---
description: Genere un classeur Excel mis en forme (couleurs par categorie, badges Europe, liens cliquables, onglets) a partir du CSV des stages
---

Lance le skill `format-xlsx` (lis d'abord son `SKILL.md`).

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/format_xlsx.py <dossier_user>/stages_quant_ds.csv \
    <dossier_user>/stages_quant_ds.xlsx
```

Puis presente le `.xlsx` (`mcp__cowork__present_files`). Le CSV reste la base canonique : ce
classeur n'est qu'une vue de presentation, regenerable a chaque scan. Si le CSV n'existe pas
encore, lance d'abord `/scan`.
