#!/usr/bin/env python3
"""
internship_common.py — logique partagee par tous les parseurs du plugin.

Chaque parseur (NUFT, Ashby, WebSearch...) produit une liste de dicts
{company, title, location, url} puis appelle commit() qui :
  - NETTOIE (espaces, supprime lignes sans entreprise / sans url / postes SWE),
  - annote in_europe (yes/no/?) via keywords.geo de sources.json (n'exclut rien),
  - upsert (dedup) dans un CSV unique persistant a 6 colonnes.

Schema de sortie FIXE (6 colonnes) :
  company, title, location, in_europe, url, first_seen

Aucun acces reseau ici : les parseurs lisent des fichiers locaux deja recuperes par Claude.
"""
import os, re, csv, json
from datetime import date

FIELDNAMES = ["company", "title", "location", "in_europe", "url", "first_seen"]

NA_COMPANY = {"", "(nom manquant)", "nom manquant", "unknown", "n/a", "na", "-", "tbd"}

# postes a exclure (SWE / software engineering)
SWE_RE = re.compile(r"\bswe\b|software\s+eng|software\s+dev|software\s+engineer", re.I)

# ---------- nettoyage ----------
def _norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()

def is_swe(title):
    return bool(SWE_RE.search(title or ""))

def clean(rows):
    """Normalise + supprime: entreprise manquante, titre/url vide, postes SWE."""
    out = []
    for r in rows:
        company = _norm(r.get("company"))
        if company.lower() in NA_COMPANY:
            continue
        title = _norm(r.get("title"))
        url = (r.get("url") or "").strip()
        if not title or not url:
            continue
        if is_swe(title):
            continue
        r["company"] = company
        r["title"] = title
        # virgules -> ' / ' pour qu'une location multi-villes ne decale jamais les colonnes
        r["location"] = re.sub(r"\s*,\s*", " / ", _norm(r.get("location")))
        r["url"] = url
        out.append(r)
    return out

# ---------- config geo / keywords ----------
def load_keywords(sources_path):
    if not sources_path or not os.path.exists(sources_path):
        return {}
    return json.load(open(sources_path, encoding="utf-8")).get("keywords", {})

def load_geo(sources_path):
    return load_keywords(sources_path).get("geo")

def europe_label(location, geo):
    """yes / no / ? — derive de la localisation. INCLUSION d'abord : si une ville/region
    europeenne est presente (meme parmi plusieurs villes), c'est 'yes'."""
    if not geo:
        return "?"
    loc = (location or "").lower().strip()
    if not loc:
        return "?"
    for t in geo.get("include_cities", []) + geo.get("include_regions", []):
        if t.lower() in loc:
            return "yes"
    for t in geo.get("exclude", []):
        if t.lower() in loc:
            return "no"
    return "?"

def annotate(rows, geo):
    counts = {"yes": 0, "no": 0, "?": 0}
    for r in rows:
        r["in_europe"] = europe_label(r.get("location", ""), geo)
        counts[r["in_europe"]] += 1
    return counts

def is_internship(title, keywords):
    types = keywords.get("include_type") or ["intern", "stage", "summer", "graduate",
                                             "campus", "placement", "apprenti", "alternance"]
    t = (title or "").lower()
    return any(k.lower() in t for k in types)

# ---------- CSV upsert (dedup, conserve first_seen) ----------
def load_csv(path):
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {(r.get("company", ""), r.get("title", ""), r.get("url", "")): r
                for r in csv.DictReader(f)}

def upsert(existing, scanned, today):
    added = kept = 0
    for s in scanned:
        key = (s["company"], s["title"], s["url"])
        if key in existing:
            row = existing[key]
            if not row.get("first_seen"):
                row["first_seen"] = today
            if not row.get("location"):
                row["location"] = s.get("location", "")
            row["in_europe"] = s.get("in_europe", row.get("in_europe", "?"))
            kept += 1
        else:
            existing[key] = {
                "company": s["company"], "title": s["title"],
                "location": s.get("location", ""), "in_europe": s.get("in_europe", "?"),
                "url": s["url"], "first_seen": today,
            }
            added += 1
    return added, kept

def write_csv(path, rows):
    ordered = sorted(rows.values(), key=lambda r: (r["company"].lower(), r["title"].lower()))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        for r in ordered:
            w.writerow({k: r.get(k, "") for k in FIELDNAMES})

# ---------- orchestration ----------
def commit(scanned, csv_path, sources_path, today=None):
    """Nettoie + annote in_europe + upsert + ecrit le CSV (6 colonnes). Retourne des stats."""
    today = today or date.today().isoformat()
    scanned = clean(scanned)
    counts = annotate(scanned, load_geo(sources_path))
    existing = load_csv(csv_path)
    added, kept = upsert(existing, scanned, today)
    write_csv(csv_path, existing)
    return {"eu": counts, "added": added, "kept": kept, "total": len(existing)}

def print_stats(source, stats):
    c = stats["eu"]
    print(f"[{source}] retenus {c['yes']+c['no']+c['?']} (in_europe {c['yes']} oui/{c['no']} non/{c['?']} ?) "
          f"| +{stats['added']} nouveaux, {stats['kept']} deja vus | total CSV: {stats['total']}")
