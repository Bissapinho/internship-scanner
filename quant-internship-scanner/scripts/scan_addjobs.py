#!/usr/bin/env python3
"""
scan_addjobs.py — injecte dans le CSV des offres collectees par la couche WebSearch.

But : empecher la DERIVE DE COLONNES. La couche WebSearch ne doit JAMAIS ecrire le CSV a la main.
A la place, Claude rassemble les offres trouvees dans un fichier JSON (liste d'objets), et ce
script les nettoie (dont filtre SWE), annote in_europe et upsert via le meme ecrivain deterministe
que NUFT/Ashby. Le schema de sortie reste fixe (6 colonnes).

Format du JSON d'entree : une liste d'objets, seuls company/title/url sont requis.
[
  {"company": "BNP Paribas", "title": "2027 Summer Analyst - Global Markets QR", "location": "London",
   "url": "https://group.bnpparibas/en/careers/job-offer/..."},
  {"company": "D.E. Shaw", "title": "Quantitative Analyst Intern (New York) Summer 2027",
   "location": "New York", "url": "https://www.deshaw.com/careers/...-5890"}
]
(location facultatif ; in_europe en sera deduit, "?" si absent.)

Usage:
  python scan_addjobs.py <jobs.json> <out.csv> [--sources <sources.json>]
                         [--source "WebSearch"] [--today YYYY-MM-DD]
"""
import json, argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import internship_common as ic

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("csv")
    ap.add_argument("--sources", default=os.path.join(here, "..", "skills", "scan-internships", "sources.json"))
    ap.add_argument("--source", default="WebSearch")
    ap.add_argument("--today", default=None)
    a = ap.parse_args()

    data = json.load(open(a.json, encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("jobs", [])
    rows = [{"company": d.get("company", ""), "title": d.get("title", ""),
             "location": d.get("location", ""), "url": d.get("url", "")} for d in data]
    ic.print_stats(a.source, ic.commit(rows, a.csv, a.sources, a.today))

if __name__ == "__main__":
    main()
