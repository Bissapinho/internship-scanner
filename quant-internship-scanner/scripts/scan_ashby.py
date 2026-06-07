#!/usr/bin/env python3
"""
Ashby -> CSV. Pour les labos/startups sur Ashby (OpenAI...).
Endpoint (recupere par Claude, PAS par ce script) :
  https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
Claude ecrit la reponse JSON dans un fichier ; ce script lit ce fichier local.

Usage: python scan_ashby.py <ashby.json> <out.csv> --company "OpenAI"
                            [--sources <sources.json>] [--bucket data_science_ai]
                            [--source "Ashby:OpenAI"] [--today YYYY-MM-DD] [--all]
Par defaut: ne garde que les stages (titre ~ include_type). --all garde tout.
"""
import json, argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import internship_common as ic

def parse_ashby(json_text, company):
    data = json.loads(json_text)
    jobs = data.get("jobs", data if isinstance(data, list) else [])
    rows = []
    for j in jobs:
        title = (j.get("title") or "").strip()
        loc = (j.get("location") or j.get("locationName") or "").strip()
        sec = j.get("secondaryLocations") or []
        if isinstance(sec, list) and sec:
            extra = ", ".join(x.get("location", "") if isinstance(x, dict) else str(x) for x in sec)
            loc = (loc + " | " + extra).strip(" |")
        url = (j.get("jobUrl") or j.get("applyUrl") or "").strip()
        emp = (j.get("employmentType") or "").strip()
        if not title or not url:
            continue
        rows.append({"company": company, "title": title, "location": loc,
                     "url": url, "employmentType": emp})
    return rows

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("csv")
    ap.add_argument("--company", required=True)
    ap.add_argument("--sources", default=os.path.join(here, "..", "skills", "scan-internships", "sources.json"))
    ap.add_argument("--bucket", default="data_science_ai")
    ap.add_argument("--source", default=None)
    ap.add_argument("--today", default=None)
    ap.add_argument("--all", action="store_true", help="garder tous les roles (pas seulement les stages)")
    a = ap.parse_args()

    rows = parse_ashby(open(a.json, encoding="utf-8").read(), a.company)
    kw = ic.load_keywords(a.sources)
    if not a.all:
        rows = [r for r in rows
                if ic.is_internship(r["title"], kw) or "intern" in r["employmentType"].lower()]
    source = a.source or f"Ashby:{a.company}"
    ic.print_stats(source, ic.commit(rows, a.csv, a.sources, a.today))

if __name__ == "__main__":
    main()
