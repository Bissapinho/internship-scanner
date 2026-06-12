#!/usr/bin/env python3
"""
finalize.py — passage de normalisation DETERMINISTE, a lancer TOUJOURS en dernier dans /scan.

Il relit le CSV existant (peu importe comment les lignes y sont arrivees : scripts OU agent) et le
remet d'equerre :
  - dé-virgule la colonne location (London, Chicago -> London / Chicago) => plus de colonnes decalees,
  - RECALCULE in_europe a partir de la location (corrige les yes/no/ville errones),
  - supprime les postes SWE, les lignes sans entreprise/url, deduplique,
  - reecrit le CSV au schema fixe 6 colonnes.

C'est le filet qui garantit un CSV propre meme si l'agent a ecrit des lignes a la main.

Usage: python finalize.py <out.csv> [--sources <sources.json>]
"""
import csv, argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import internship_common as ic

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--sources", default=os.path.join(here, "..", "skills", "scan-internships", "sources.json"))
    a = ap.parse_args()

    if not os.path.exists(a.csv):
        print("finalize: aucun CSV a normaliser."); return
    with open(a.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n_before = len(rows)

    rows = ic.clean(rows)                       # de-virgule location, retire SWE / NA / sans url
    ic.annotate(rows, ic.load_geo(a.sources))   # RECALCULE in_europe depuis la location nettoyee

    dedup = {}
    for r in rows:
        dedup[(r["company"], r["title"], r["url"])] = r
    ic.write_csv(a.csv, dedup)
    print(f"[finalize] {n_before} lignes -> {len(dedup)} apres nettoyage/dedup "
          f"(in_europe recalcule, location de-virgulee, SWE retires)")

if __name__ == "__main__":
    main()
