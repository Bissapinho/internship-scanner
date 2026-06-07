#!/usr/bin/env python3
"""
NUFT (northwesternfintech/2027QuantInternships) -> CSV. Quant-only (hedge funds).
Claude fetch le README brut et l'ecrit en .md ; ce script ne lit que le fichier local.

Usage: python scan_nuft.py <nuft.md> <out.csv> [--sources <sources.json>]
                           [--source "NUFT 2027"] [--bucket hedge_fund_quant] [--today YYYY-MM-DD]
"""
import re, argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import internship_common as ic

def parse_nuft(md_text):
    rows = []
    for block in re.split(r'(?m)^##[ \t]+', md_text)[1:]:  # [ \t]+ : ne pas avaler le \n si titre vide
        lines = block.splitlines()
        company = lines[0].strip() or "(nom manquant)"
        m = re.search(r'\*\*Locations\*\*:[ \t]*([^\n]*)', block)  # [ \t]* : ne pas avaler le \n
        location = m.group(1).strip() if m else ""
        for line in lines:
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            role = cells[0]
            if role.lower() in ("role", "") or set(role) <= set("- "):
                continue
            um = re.search(r'\((https?://[^)]+)\)', cells[1])
            if not um:
                continue
            rows.append({"company": company, "title": role,
                         "location": location, "url": um.group(1).strip()})
    return rows

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("md"); ap.add_argument("csv")
    ap.add_argument("--sources", default=os.path.join(here, "..", "skills", "scan-internships", "sources.json"))
    ap.add_argument("--source", default="NUFT 2027")
    ap.add_argument("--bucket", default="hedge_fund_quant")
    ap.add_argument("--today", default=None)
    a = ap.parse_args()
    scanned = parse_nuft(open(a.md, encoding="utf-8").read())
    ic.print_stats(a.source, ic.commit(scanned, a.csv, a.sources, a.today))

if __name__ == "__main__":
    main()
