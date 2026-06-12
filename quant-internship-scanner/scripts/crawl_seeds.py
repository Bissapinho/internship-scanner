#!/usr/bin/env python3
"""
crawl_seeds.py — moteur de DECOUVERTE "de reference en reference" (crawler borne).

Le plugin ne se contente plus d'une liste de sources figee : a partir d'une page deja
recuperee par Claude (HTML ou Markdown), ce script EXTRAIT les liens candidats vers de
NOUVELLES sources d'offres (job boards ATS, pages carrieres de firmes quant/HF/fintech),
les FILTRE par allowlist, ENLEVE ce qui est deja connu, et emet une FILE DE DECOUVERTE JSON.

Boucle agentique (pilotee par le skill, profondeur bornee a 2 sauts) :
  1. Claude fetch une page seed (repo agregateur, board, page carriere).        [hop 0]
  2. crawl_seeds.py page.html -> queue.json  (liens candidats filtres + dedupliques)
  3. Claude fetch chaque url de queue.json (allowlist ATS) et en extrait les offres. [hop 1]
  4. (option) re-crawl ces pages pour 1 saut de plus.                              [hop 2]
  5. Les offres collectees sont injectees via scan_addjobs.py (--source "Crawl:<domaine>").

AUCUN ACCES RESEAU ici : on lit un fichier local, on ecrit un JSON local. Le reseau est
fait par Claude (web_fetch / Chrome), conformement a l'archi du plugin.

Allowlist d'ATS (domaines de confiance) et mots-cles "carriere" : voir sources.json
(champ `crawl`). Defauts raisonnables si absent.

Usage:
  python crawl_seeds.py <page.html|page.md> [<page2> ...] \
      --out queue.json [--csv <stages.csv>] [--sources <sources.json>] \
      [--found-on <url_de_la_page>] [--max 60] [--include-careers]

Sortie (queue.json) : liste d'objets
  {"url": "...", "kind": "ats_board|job_posting|careers", "domain": "...",
   "company_guess": "...", "found_on": "<page seed>"}
"""
import re, json, argparse, os, sys
from urllib.parse import urlparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import internship_common as ic

# ATS / job-board connus -> pages structurees, surs a suivre
DEFAULT_ATS = [
    "boards.greenhouse.io", "job-boards.greenhouse.io", "boards-api.greenhouse.io",
    "jobs.lever.co", "api.lever.co", "jobs.ashbyhq.com", "api.ashbyhq.com",
    "myworkdayjobs.com", "smartrecruiters.com", "workable.com",
    "eightfold.ai", "icims.com", "teamtailor.com", "personio.com",
    "ats.rippling.com", "jobs.workable.com",
]
# indices "page carriere / early careers" (suivis seulement avec --include-careers)
DEFAULT_CAREER_HINTS = [
    "career", "careers", "early-careers", "students", "graduate", "graduates",
    "join-us", "join", "internship", "internships", "jobs", "open-roles",
    "opportunities", "recruitment", "campus", "stage", "stages", "emplois",
]
# bruit a ignorer (reseaux sociaux, agregateurs grand public, etc.)
DEFAULT_DENY = [
    "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "youtube.com", "github.com/sponsors", "glassdoor.", "indeed.", "google.com",
    "wikipedia.org", "medium.com", "discord.", "t.me", "mailto:", "tel:",
]

URL_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
MD_RE = re.compile(r'\]\((https?://[^)\s]+)\)')
ANCHOR_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)


def load_crawl_cfg(sources_path):
    cfg = {}
    if sources_path and os.path.exists(sources_path):
        cfg = json.load(open(sources_path, encoding="utf-8")).get("crawl", {}) or {}
    return {
        "ats": cfg.get("ats_domains", DEFAULT_ATS),
        "careers": cfg.get("career_hints", DEFAULT_CAREER_HINTS),
        "deny": cfg.get("deny_domains", DEFAULT_DENY),
    }


def known_domains(csv_path):
    """Domaines deja presents dans le CSV : on evite de re-decouvrir ce qu'on a deja."""
    doms = set()
    for row in ic.load_csv(csv_path).values():
        try:
            doms.add(urlparse(row.get("url", "")).netloc.lower())
        except Exception:
            pass
    return doms


def extract_links(text):
    """Renvoie une liste de (url, anchor_text). Gere HTML et Markdown."""
    out = []
    for m in ANCHOR_RE.finditer(text):
        anchor = re.sub(r"<[^>]+>", " ", m.group(2))
        out.append((m.group(1).strip(), ic._norm(anchor)))
    for m in URL_RE.finditer(text):
        out.append((m.group(1).strip(), ""))
    for m in MD_RE.finditer(text):
        out.append((m.group(1).strip(), ""))
    return out


def domain_of(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def company_from_url(url, anchor):
    if anchor and 2 <= len(anchor) <= 60:
        return anchor
    d = domain_of(url)
    path = urlparse(url).path.strip("/").split("/")
    # greenhouse/lever/ashby : slug entreprise dans le path
    for host in ("greenhouse.io", "lever.co", "ashbyhq.com"):
        if host in d and path and path[0]:
            return path[0].replace("-", " ").title()
    # workday : sous-domaine = entreprise
    if "myworkdayjobs.com" in d:
        return d.split(".")[0].title()
    base = d.replace("www.", "").split(".")
    return base[0].title() if base and base[0] else ""


def classify(url, anchor, cfg):
    d = domain_of(url)
    low = url.lower()
    if not d or any(x in low for x in cfg["deny"]):
        return None
    if any(a in d for a in cfg["ats"]):
        # une URL ATS avec un id de poste = posting, sinon board
        kind = "job_posting" if re.search(r"/(jobs?|postings?)/\w", low) else "ats_board"
        return kind
    blob = (low + " " + anchor.lower())
    if any(h in blob for h in cfg["careers"]):
        return "careers"
    return None


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--sources", default=os.path.join(here, "..", "skills", "scan-internships", "sources.json"))
    ap.add_argument("--found-on", default="")
    ap.add_argument("--max", type=int, default=60)
    ap.add_argument("--include-careers", action="store_true",
                    help="suivre aussi les pages 'careers' de domaines inconnus (plus large, plus de bruit)")
    a = ap.parse_args()

    cfg = load_crawl_cfg(a.sources)
    known = known_domains(a.csv) if a.csv else set()
    seen, queue = set(), []
    n_ats = n_post = n_career = 0

    for page in a.pages:
        text = open(page, encoding="utf-8", errors="ignore").read()
        for url, anchor in extract_links(text):
            if not url.startswith("http"):
                continue
            url = url.split("#")[0].rstrip("/")
            if url in seen:
                continue
            kind = classify(url, anchor, cfg)
            if not kind:
                continue
            if kind == "careers" and not a.include_careers:
                continue
            d = domain_of(url)
            # on saute un board ATS deja entierement couvert (domaine connu),
            # mais on garde les postings individuels meme si le domaine est connu
            if kind == "ats_board" and d in known:
                continue
            seen.add(url)
            queue.append({
                "url": url, "kind": kind, "domain": d,
                "company_guess": company_from_url(url, anchor),
                "found_on": a.found_on or page,
            })
            n_ats += kind == "ats_board"; n_post += kind == "job_posting"; n_career += kind == "careers"
            if len(queue) >= a.max:
                break
        if len(queue) >= a.max:
            break

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(queue, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[crawl] {len(queue)} candidats -> {a.out} "
          f"(ats_board {n_ats} / job_posting {n_post} / careers {n_career}) "
          f"| {len(a.pages)} page(s), {len(known)} domaines deja connus ignores")

if __name__ == "__main__":
    main()
