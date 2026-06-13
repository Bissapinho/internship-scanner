#!/usr/bin/env python3
"""
internship_common.py — logique partagee par tous les parseurs du plugin (v0.2).

Chaque parseur (NUFT, Ashby, WebSearch, Crawl...) produit une liste de dicts
{company, title, location, url} puis appelle commit() qui :
  - NETTOIE (espaces, supprime lignes sans entreprise / sans url, postes SWE,
    APPRENTISSAGE/ALTERNANCE et postes GRADUATE non-stage),
  - annote in_europe (yes/no/?) via keywords.geo de sources.json (n'exclut rien),
  - classe le role dans un bucket (bank_quant / hedge_fund_quant / data_scientist / ...),
  - upsert (dedup) dans un CSV unique persistant, en mettant a jour last_seen.

Schema de sortie FIXE (9 colonnes) :
  company, title, location, in_europe, bucket, source, url, first_seen, last_seen

Filtre TITRE (point utilisateur) : on ne garde que des STAGES / INTERNSHIPS.
  - on garde : intern, internship, stage, summer (un "summer analyst" est un stage).
  - on rejette : apprenticeship / apprenti / alternance / work-study (apprentissage),
    et les postes GRADUATE / new grad qui ne sont pas aussi des stages.

Retro-compatible : un CSV 6 colonnes de la v0.1 est relu sans erreur (colonnes manquantes -> "").
Aucun acces reseau ici : les parseurs lisent des fichiers locaux deja recuperes par Claude.
"""
import os, re, csv, json
from urllib.parse import urlparse
from datetime import date

FIELDNAMES = ["company", "title", "location", "in_europe", "bucket",
              "source", "url", "first_seen", "last_seen"]

NA_COMPANY = {"", "(nom manquant)", "nom manquant", "unknown", "n/a", "na", "-", "tbd"}

# postes a exclure (SWE / software engineering)
SWE_RE = re.compile(r"\bswe\b|software\s+eng|software\s+dev|software\s+engineer", re.I)
# apprentissage / alternance -> exclu
APPRENTICE_RE = re.compile(r"apprentice|apprenti|alternance|alternant|work[\s-]?study|contrat\s+pro", re.I)
# indices "stage / internship" (on exige au moins un de ceux-la dans le titre)
INTERN_RE = re.compile(r"\bintern\b|internship|\bstage\b|\bstagiaire\b|\bsummer\b", re.I)
# graduate / poste diplome (rejete SAUF s'il s'agit aussi d'un stage)
GRADUATE_RE = re.compile(r"\bgraduate\b|\bnew\s?grad\b|\bgrad\s+program", re.I)

# ---------- nettoyage ----------
def _norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()

def is_swe(title):
    return bool(SWE_RE.search(title or ""))

def is_apprenticeship(title):
    return bool(APPRENTICE_RE.search(title or ""))

def is_internship_title(title):
    """True si le titre ressemble a un STAGE/INTERNSHIP (intern/internship/stage/summer)."""
    return bool(INTERN_RE.search(title or ""))

def is_pure_graduate(title):
    """True si poste 'graduate/new grad' qui n'est PAS aussi un stage -> a rejeter."""
    t = title or ""
    return bool(GRADUATE_RE.search(t)) and not is_internship_title(t)

def reject_title(title):
    """Centralise le rejet de titre : SWE, apprentissage, graduate non-stage,
    et tout ce qui n'est pas un stage/internship."""
    if not title:
        return True
    if is_swe(title) or is_apprenticeship(title) or is_pure_graduate(title):
        return True
    if not is_internship_title(title):
        return True
    return False

def clean(rows):
    """Normalise + supprime: entreprise/titre/url manquant, SWE, apprentissage,
    graduate non-stage, et tout titre qui n'est pas un stage/internship."""
    out = []
    for r in rows:
        company = _norm(r.get("company"))
        if company.lower() in NA_COMPANY:
            continue
        title = _norm(r.get("title"))
        url = (r.get("url") or "").strip()
        if not title or not url:
            continue
        if reject_title(title):
            continue
        r["company"] = company
        r["title"] = title
        r["location"] = re.sub(r"\s*,\s*", " / ", _norm(r.get("location")))
        r["url"] = url
        out.append(r)
    return out

# ---------- normalisation pour DEDUP ----------
def normalize_url(u):
    """URL canonique pour comparer : sans scheme, sans www, sans query/fragment, sans slash final."""
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("#")[0].split("?")[0]
    return u.rstrip("/")

def normalize_title(t):
    """Titre canonique : minuscules, annees retirees, ponctuation -> espace."""
    t = (t or "").lower()
    t = re.sub(r"\b20\d\d\b", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()

# ---------- config geo / keywords ----------
def load_keywords(sources_path):
    if not sources_path or not os.path.exists(sources_path):
        return {}
    return json.load(open(sources_path, encoding="utf-8")).get("keywords", {})

def load_geo(sources_path):
    return load_keywords(sources_path).get("geo")

def europe_label(location, geo):
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

# ---------- classification de bucket (deterministe) ----------
_BUCKET_ORDER = ["bank_quant", "hedge_fund_quant", "data_scientist",
                 "data_science_ai", "data_analyst", "consulting_data"]

def classify_bucket(title, keywords, default="?"):
    t = (title or "").lower()
    buckets = (keywords or {}).get("role_buckets", {})
    for name in _BUCKET_ORDER:
        cfg = buckets.get(name)
        if not cfg:
            continue
        kws = cfg.get("keywords") or cfg.get("include") or []
        exc = cfg.get("exclude_titles") or []
        if any(k.lower() in t for k in kws) and not any(e.lower() in t for e in exc):
            return name
    return default

def annotate_bucket(rows, keywords):
    for r in rows:
        if not r.get("bucket"):
            r["bucket"] = classify_bucket(r.get("title", ""), keywords)
    return rows

def is_internship(title, keywords):
    types = keywords.get("include_type") or ["intern", "internship", "stage", "summer"]
    t = (title or "").lower()
    return any(k.lower() in t for k in types)

def is_data_scientist(title, keywords):
    cfg = (keywords.get("role_buckets") or {}).get("data_scientist", {})
    inc = cfg.get("include") or ["data scientist", "data science"]
    exc = cfg.get("exclude_titles") or []
    t = (title or "").lower()
    if not any(k.lower() in t for k in inc):
        return False
    if any(k.lower() in t for k in exc):
        return False
    return True

# ---------- CSV upsert (dedup, conserve first_seen, met a jour last_seen) ----------
def load_csv(path):
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {(r.get("company", ""), r.get("title", ""), r.get("url", "")): r
                for r in csv.DictReader(f)}

def upsert(existing, scanned, today, source=None):
    added = kept = 0
    for s in scanned:
        key = (s["company"], s["title"], s["url"])
        if key in existing:
            row = existing[key]
            if not row.get("first_seen"):
                row["first_seen"] = today
            row["last_seen"] = today
            if not row.get("location"):
                row["location"] = s.get("location", "")
            row["in_europe"] = s.get("in_europe", row.get("in_europe", "?"))
            if s.get("bucket") and s["bucket"] != "?":
                row["bucket"] = s["bucket"]
            if source and source not in (row.get("source") or ""):
                row["source"] = ", ".join(x for x in [row.get("source"), source] if x)
            kept += 1
        else:
            existing[key] = {
                "company": s["company"], "title": s["title"],
                "location": s.get("location", ""), "in_europe": s.get("in_europe", "?"),
                "bucket": s.get("bucket", "?"), "source": source or s.get("source", ""),
                "url": s["url"], "first_seen": today, "last_seen": today,
            }
            added += 1
    return added, kept

def write_csv(path, rows):
    order = {b: i for i, b in enumerate(_BUCKET_ORDER)}
    def sort_key(r):
        return (order.get(r.get("bucket", ""), 99), r.get("company", "").lower(),
                r.get("title", "").lower())
    ordered = sorted(rows.values(), key=sort_key)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        for r in ordered:
            w.writerow({k: r.get(k, "") for k in FIELDNAMES})

# ---------- DEDUP elargi (utilise par verify --fix) ----------
SUSPECT_DOMAINS = ["linkedin.com", "indeed.", "glassdoor.", "google.com/search",
                   "twitter.com", "x.com", "facebook.com", "medium.com", "wikipedia.org"]

def _is_suspect(url):
    return any(s in (url or "").lower() for s in SUSPECT_DOMAINS)

def _better_url(a, b):
    """Choisit la meilleure URL entre deux candidates (non-suspecte > https > plus courte)."""
    if _is_suspect(a) != _is_suspect(b):
        return b if _is_suspect(a) else a
    ha = a.lower().startswith("https"); hb = b.lower().startswith("https")
    if ha != hb:
        return a if ha else b
    return a if len(a) <= len(b) else b

def _norm_loc(loc):
    return re.sub(r"\s+", " ", (loc or "").lower()).strip()

def _richer(a, b):
    """Choisit la variante la plus 'riche' d'un texte (plus de majuscules, puis plus longue)."""
    a = a or ""; b = b or ""
    ua = sum(c.isupper() for c in a); ub = sum(c.isupper() for c in b)
    if ua != ub:
        return a if ua > ub else b
    if len(a) != len(b):
        return a if len(a) > len(b) else b
    return a

def dedup_rows(rows):
    """Fusionne les doublons ELARGIS. Deux lignes fusionnent si (meme entreprise) ET :
      - meme URL normalisee (http/https, www, slash, tracking ignores)  -> vrai doublon de lien ; OU
      - meme TITRE normalise ET localisation COMPATIBLE (meme ville, ou l'une vide).
    Une meme offre postee dans deux villes differentes (URLs differentes) n'est PAS fusionnee.
    La ligne fusionnee garde la variante la plus riche (casse/annee), le plus ancien first_seen,
    le dernier last_seen, l'union des sources. Renvoie (rows_fusionnees, n_fusions)."""
    n = len(rows)
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    sig_url, sig_title = {}, {}
    for i, r in enumerate(rows):
        comp = (r.get("company") or "").lower()
        ku = (comp, normalize_url(r.get("url", "")))
        if ku in sig_url:
            union(i, sig_url[ku])
        else:
            sig_url[ku] = i
        # titre : on inclut la localisation pour ne pas fusionner deux villes differentes
        kt = (comp, normalize_title(r.get("title", "")), _norm_loc(r.get("location", "")))
        if kt in sig_title:
            union(i, sig_title[kt])
        else:
            sig_title[kt] = i
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(rows[i])
    merged, fusions = [], 0
    for g in groups.values():
        if len(g) == 1:
            merged.append(g[0]); continue
        fusions += len(g) - 1
        base = dict(g[0])
        url = base.get("url", "")
        company = base.get("company", ""); title = base.get("title", "")
        first = base.get("first_seen", "") or ""
        last = base.get("last_seen", "") or ""
        srcs, loc = set(), base.get("location", "")
        bucket, eu = base.get("bucket", "?"), base.get("in_europe", "?")
        for r in g:
            url = _better_url(url, r.get("url", "")) if url else r.get("url", "")
            company = _richer(company, r.get("company", ""))
            title = _richer(title, r.get("title", ""))
            fs = r.get("first_seen", "") or ""
            ls = r.get("last_seen", "") or ""
            if fs and (not first or fs < first):
                first = fs
            if ls and ls > last:
                last = ls
            for sname in (r.get("source", "") or "").split(","):
                sname = sname.strip()
                if sname:
                    srcs.add(sname)
            if len(r.get("location", "") or "") > len(loc or ""):
                loc = r.get("location", "")
            if (not bucket or bucket == "?") and r.get("bucket") not in (None, "", "?"):
                bucket = r.get("bucket")
            if eu == "?" and r.get("in_europe") in ("yes", "no"):
                eu = r.get("in_europe")
        base.update({"url": url, "company": company, "title": title,
                     "first_seen": first, "last_seen": last,
                     "source": ", ".join(sorted(srcs)), "location": loc,
                     "bucket": bucket, "in_europe": eu})
        merged.append(base)
    return merged, fusions

# ---------- orchestration ----------
def commit(scanned, csv_path, sources_path, today=None, source=None):
    today = today or date.today().isoformat()
    kw = load_keywords(sources_path)
    scanned = clean(scanned)
    counts = annotate(scanned, kw.get("geo"))
    annotate_bucket(scanned, kw)
    existing = load_csv(csv_path)
    added, kept = upsert(existing, scanned, today, source=source)
    write_csv(csv_path, existing)
    return {"eu": counts, "added": added, "kept": kept, "total": len(existing)}

def print_stats(source, stats):
    c = stats["eu"]
    print(f"[{source}] retenus {c['yes']+c['no']+c['?']} (in_europe {c['yes']} oui/{c['no']} non/{c['?']} ?) "
          f"| +{stats['added']} nouveaux, {stats['kept']} deja vus | total CSV: {stats['total']}")
