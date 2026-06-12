#!/usr/bin/env python3
"""
verify_links.py — controle QUALITE du CSV (skill verify-links).

Audit DETERMINISTE, sans reseau :
  - DOUBLONS ELARGIS (pas seulement le lien exact) : meme entreprise + meme URL
    NORMALISEE (http/https, www, slash final, parametres de tracking ignores), OU
    meme entreprise + meme TITRE normalise (casse/ponctuation/annee ignorees),
  - URLs malformees ou suspectes (agregateurs, reseaux sociaux),
  - in_europe invalide ou "?" restants, bucket manquant,
  - offres PERIMEES : last_seen trop ancien (probablement fermees),
  - integrite des colonnes.

Test de LIENS MORTS (HTTP) : le reseau est fait par Claude. Ce script EMET la liste
des urls a tester (--emit-check urls.json), Claude les fetch en lots, ecrit les urls
mortes dans dead.json, puis on applique --apply-dead dead.json.

IMPORTANT : a lancer sur un CSV qui EXISTE dans un dossier accessible a Cowork. Si le
fichier est absent, le script s'arrete avec une erreur claire (pas de CSV cree a vide).

Modes :
  python verify_links.py <csv> [--sources s.json] [--stale-days 45]   # rapport seul
  python verify_links.py <csv> --emit-check urls.json                  # liste a tester (HTTP)
  python verify_links.py <csv> --fix                                   # dedup ELARGI + normalise + reecrit
  python verify_links.py <csv> --apply-dead dead.json [--drop]         # marque/retire les liens morts
  python verify_links.py <csv> --report report.md                      # ecrit un rapport markdown
"""
import json, argparse, os, sys
from urllib.parse import urlparse
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import internship_common as ic

SUSPECT = ic.SUSPECT_DOMAINS


def die(msg):
    print(f"[verify] ERREUR: {msg}", file=sys.stderr)
    sys.exit(2)


def url_ok(u):
    try:
        p = urlparse(u)
        return bool(p.scheme in ("http", "https") and p.netloc)
    except Exception:
        return False


def days_since(iso):
    try:
        return (date.today() - datetime.strptime(iso, "%Y-%m-%d").date()).days
    except Exception:
        return None


def audit(rows, stale_days):
    issues = {"bad_url": [], "suspect": [], "dup_url": [], "dup_title": [],
              "bad_europe": [], "unknown_europe": [], "stale": [], "no_bucket": []}
    by_url, by_title = {}, {}
    for r in rows:
        url = r.get("url", ""); comp = (r.get("company") or "").lower()
        by_url.setdefault((comp, ic.normalize_url(url)), []).append(r)
        by_title.setdefault((comp, ic.normalize_title(r.get("title", ""))), []).append(r)
        if not url_ok(url):
            issues["bad_url"].append(r)
        elif any(s in url.lower() for s in SUSPECT):
            issues["suspect"].append(r)
        if r.get("in_europe") not in ("yes", "no", "?"):
            issues["bad_europe"].append(r)
        elif r.get("in_europe") == "?":
            issues["unknown_europe"].append(r)
        if not r.get("bucket") or r.get("bucket") == "?":
            issues["no_bucket"].append(r)
        d = days_since(r.get("last_seen", ""))
        if d is not None and d > stale_days:
            issues["stale"].append((r, d))
    for k, lst in by_url.items():
        if len(lst) > 1:
            issues["dup_url"].append((k, lst))
    for k, lst in by_title.items():
        if len(lst) > 1 and len({x.get("url") for x in lst}) > 1:
            issues["dup_title"].append((k, lst))
    return issues


def print_report(issues, total, stale_days, fh=None):
    def w(s=""):
        print(s, file=fh) if fh else print(s)
    w(f"# Rapport de verification — {total} offres\n")
    w(f"- Liens malformes : **{len(issues['bad_url'])}**")
    w(f"- Domaines suspects (non-candidature) : **{len(issues['suspect'])}**")
    w(f"- Doublons d'URL normalisee (meme lien a tracking pres) : **{len(issues['dup_url'])}**")
    w(f"- Quasi-doublons (meme entreprise + titre, URLs differentes) : **{len(issues['dup_title'])}**")
    w(f"- in_europe invalide : **{len(issues['bad_europe'])}**")
    w(f"- in_europe == '?' (a resoudre) : **{len(issues['unknown_europe'])}**")
    w(f"- bucket manquant : **{len(issues['no_bucket'])}**")
    w(f"- Offres perimees (last_seen > {stale_days} j, probablement fermees) : **{len(issues['stale'])}**")
    if issues["bad_url"] or issues["suspect"]:
        w("\n## Liens a corriger")
        for r in (issues["bad_url"] + issues["suspect"])[:30]:
            w(f"- {r.get('company')} — {r.get('title')} → `{r.get('url')}`")
    if issues["dup_url"]:
        w("\n## Doublons d'URL normalisee (fusionnes par --fix)")
        for (comp, nurl), lst in issues["dup_url"][:30]:
            w(f"- **{lst[0].get('company')} — {lst[0].get('title')}** ({len(lst)} lignes) `{nurl}`")
    if issues["dup_title"]:
        w("\n## Quasi-doublons meme poste, URLs differentes (fusionnes par --fix)")
        for (comp, nt), lst in issues["dup_title"][:30]:
            w(f"- **{lst[0].get('company')} — {lst[0].get('title')}**")
            for x in lst:
                w(f"    - `{x.get('url')}` (source: {x.get('source','')})")
    if issues["stale"]:
        w("\n## Offres perimees (a verifier / archiver)")
        for r, d in sorted(issues["stale"], key=lambda t: -t[1])[:40]:
            w(f"- {r.get('company')} — {r.get('title')} (vue il y a {d} j) → `{r.get('url')}`")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--sources", default=os.path.join(here, "..", "skills", "scan-internships", "sources.json"))
    ap.add_argument("--stale-days", type=int, default=45)
    ap.add_argument("--emit-check", default=None)
    ap.add_argument("--fix", action="store_true", help="dedup ELARGI + normalise + reecrit le CSV")
    ap.add_argument("--apply-dead", default=None)
    ap.add_argument("--drop", action="store_true")
    ap.add_argument("--report", default=None)
    a = ap.parse_args()

    if not os.path.exists(a.csv):
        die(f"CSV introuvable: {a.csv}\n"
            "  -> lance d'abord un scan, et travaille dans un dossier connecte a Cowork "
            "ou le CSV existe (ex. <dossier_user>/stages_quant_ds.csv).")

    existing = ic.load_csv(a.csv)
    rows = list(existing.values())

    if a.emit_check:
        urls = sorted({r.get("url") for r in rows if url_ok(r.get("url", ""))})
        json.dump(urls, open(a.emit_check, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[verify] {len(urls)} urls a tester -> {a.emit_check}")
        return

    if a.apply_dead:
        dead = set(json.load(open(a.apply_dead, encoding="utf-8")))
        hit = [k for k, r in existing.items() if r.get("url") in dead]
        if a.drop:
            for k in hit:
                del existing[k]
            ic.write_csv(a.csv, existing)
            print(f"[verify] {len(hit)} liens morts SUPPRIMES du CSV")
        else:
            print(f"[verify] {len(hit)} liens morts detectes (relance avec --drop pour supprimer) :")
            for k in hit:
                print("   -", existing[k].get("company"), "—", existing[k].get("url"))
        return

    if a.fix:
        kw = ic.load_keywords(a.sources)
        cleaned = ic.clean([dict(r) for r in rows])
        ic.annotate(cleaned, kw.get("geo"))
        ic.annotate_bucket(cleaned, kw)
        # preserve first_seen/last_seen/source d'origine via la cle exacte
        for r in cleaned:
            old = existing.get((r["company"], r["title"], r["url"]), {})
            r["first_seen"] = old.get("first_seen") or r.get("first_seen") or date.today().isoformat()
            r["last_seen"] = old.get("last_seen") or r.get("last_seen") or r["first_seen"]
            r["source"] = old.get("source") or r.get("source", "")
        merged_list, fusions = ic.dedup_rows(cleaned)
        merged = {(r["company"], r["title"], r["url"]): r for r in merged_list}
        ic.write_csv(a.csv, merged)
        print(f"[verify] dedup ELARGI + normalise : {len(rows)} -> {len(merged)} lignes "
              f"({fusions} fusion(s) de doublons)")
        rows = list(merged.values())

    issues = audit(rows, a.stale_days)
    if a.report:
        print_report(issues, len(rows), a.stale_days, fh=open(a.report, "w", encoding="utf-8"))
        print(f"[verify] rapport ecrit -> {a.report}")
    print_report(issues, len(rows), a.stale_days)


if __name__ == "__main__":
    main()
