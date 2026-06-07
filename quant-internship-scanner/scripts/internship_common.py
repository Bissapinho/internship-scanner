#!/usr/bin/env python3
"""
internship_common.py — logique partagee par tous les parseurs du plugin.

Chaque parseur (NUFT, Ashby...) produit une liste de dicts {company, title, location, url}
puis appelle commit() qui :
  - NETTOIE les lignes (espaces/retours-ligne, supprime celles sans entreprise),
  - annote in_europe (yes/no/?) via keywords.geo de sources.json (n'exclut rien),
  - upsert dans un CSV unique persistant (NEW/OPEN/CLOSED, colonne 'applied' preservee).

Aucun acces reseau ici : les parseurs lisent des fichiers locaux deja recuperes par Claude.
"""
import os, re, csv, json
from datetime import date

FIELDNAMES = ["company", "title", "role_bucket", "location", "in_europe", "source",
              "url", "first_seen", "last_seen", "status", "applied"]

# noms d'entreprise consideres comme manquants -> ligne supprimee
NA_COMPANY = {"", "(nom manquant)", "nom manquant", "unknown", "n/a", "na", "-", "tbd"}

# ---------- nettoyage ----------
def _norm(s):
    """Collapse espaces/retours-ligne en un seul espace."""
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()

def clean(rows):
    """Normalise les champs et SUPPRIME les lignes sans entreprise / sans url / sans titre."""
    out = []
    for r in rows:
        company = _norm(r.get("company"))
        if company.lower() in NA_COMPANY:
            continue
        title = _norm(r.get("title"))
        url = (r.get("url") or "").strip()
        if not title or not url:
            continue
        r["company"] = company
        r["title"] = title
        r["location"] = _norm(r.get("location"))
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
    """yes / no / ? — derive de la localisation, n'exclut rien."""
    if not geo:
        return "?"
    loc = (location or "").lower().strip()
    if not loc:
        return "?"
    for t in geo.get("exclude", []):
        if t.lower() in loc:
            return "no"
    for t in geo.get("include_cities", []) + geo.get("include_regions", []):
        if t.lower() in loc:
            return "yes"
    return "?"

def annotate(rows, geo):
    counts = {"yes": 0, "no": 0, "?": 0}
    for r in rows:
        r["in_europe"] = europe_label(r.get("location", ""), geo)
        counts[r["in_europe"]] += 1
    return counts

def is_internship(title, keywords):
    """True si le titre ressemble a un stage (include_type)."""
    types = keywords.get("include_type") or ["intern", "stage", "summer", "graduate",
                                             "campus", "placement", "apprenti", "alternance"]
    t = (title or "").lower()
    return any(k.lower() in t for k in types)

# ---------- CSV upsert ----------
def load_csv(path):
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {(r["company"], r["title"], r["url"]): r for r in csv.DictReader(f)}

def upsert(existing, scanned, source, bucket, today):
    added = updated = closed = 0
    seen = set()
    for s in scanned:
        key = (s["company"], s["title"], s["url"])
        seen.add(key)
        if key in existing:
            row = existing[key]
            row["last_seen"] = today
            row["status"] = "OPEN"
            row["in_europe"] = s.get("in_europe", row.get("in_europe", "?"))
            if not row.get("location"):
                row["location"] = s.get("location", "")
            updated += 1
        else:
            existing[key] = {
                "company": s["company"], "title": s["title"],
                "role_bucket": s.get("role_bucket", bucket),
                "location": s.get("location", ""), "in_europe": s.get("in_europe", "?"),
                "source": source, "url": s["url"],
                "first_seen": today, "last_seen": today,
                "status": "NEW", "applied": "",
            }
            added += 1
    for key, row in existing.items():
        if row.get("source") == source and key not in seen and row.get("status") != "CLOSED":
            row["status"] = "CLOSED"
            closed += 1
    return added, updated, closed

def write_csv(path, rows):
    ordered = sorted(rows.values(), key=lambda r: (r["company"].lower(), r["title"].lower()))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in ordered:
            w.writerow({k: r.get(k, "") for k in FIELDNAMES})

# ---------- orchestration ----------
def commit(scanned, csv_path, sources_path, source, bucket, today=None):
    """Nettoie + annote in_europe + upsert + ecrit le CSV. Retourne un dict de stats."""
    today = today or date.today().isoformat()
    scanned = clean(scanned)
    counts = annotate(scanned, load_geo(sources_path))
    existing = load_csv(csv_path)
    added, updated, closed = upsert(existing, scanned, source, bucket, today)
    write_csv(csv_path, existing)
    return {"eu": counts, "added": added, "updated": updated,
            "closed": closed, "total": len(existing), "kept": len(scanned)}

def print_stats(source, stats):
    c = stats["eu"]
    print(f"[{source}] gardes {stats['kept']} (in_europe {c['yes']} oui/{c['no']} non/{c['?']} ?) "
          f"| +{stats['added']} NEW, {stats['updated']} maj, {stats['closed']} CLOSED "
          f"| total CSV: {stats['total']}")
