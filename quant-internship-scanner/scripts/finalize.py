#!/usr/bin/env python3
"""
finalize.py — ORCHESTRATEUR de fin de chaine (verrouille les etapes apres un scan).

But : qu'aucune etape ne soit oubliee (surtout en run planifie non surveille). En UNE commande :
  1. DEDUP + nettoyage   -> verify_links.py --fix   (fusionne doublons elargis, re-normalise)
  2. RAPPORT qualite     -> verify_links.py --report (liens suspects, offres perimees)
  3. EXCEL               -> format_xlsx.py           (classeur mis en forme, a cote du CSV)
  4. JOURNAL             -> append d'une ligne dans data/scan_log.csv (date, total, +N, perimees...)
  5. RECAP imprime (repartition par bucket / Europe / sources).

Le +N (nouveaux) et les sources OK/echec sont connus de l'agent (phase de scan) : il peut les
passer via --added / --sources-ok / --sources-fail pour les tracer dans le journal. Optionnels.

Aucun reseau. Reutilise les scripts deja testes (sous-processus). Le journal vit dans data/
(gitignore) -> non versionne.

Usage:
  python finalize.py <OUT.csv> --sources <sources.json>
        [--xlsx <out.xlsx>] [--report <verif.md>] [--log <scan_log.csv>]
        [--stale-days 45] [--added N] [--sources-ok "NUFT,Ashby"] [--sources-fail "Greenhouse"]
"""
import argparse, os, sys, subprocess, csv
from datetime import date, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import internship_common as ic
PY = sys.executable or "python3"


def run(script, *args):
    r = subprocess.run([PY, os.path.join(HERE, script), *args],
                       capture_output=True, text=True)
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode != 0:
        print(f"[finalize] !! {script} a echoue (code {r.returncode})", file=sys.stderr)
        if r.stderr.strip():
            print(r.stderr.strip(), file=sys.stderr)
    return r.returncode == 0


def days_since(iso):
    try:
        return (date.today() - datetime.strptime(iso, "%Y-%m-%d").date()).days
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--sources", default=os.path.join(HERE, "..", "skills", "scan-internships", "sources.json"))
    ap.add_argument("--xlsx", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--stale-days", type=int, default=45)
    ap.add_argument("--added", type=int, default=None)
    ap.add_argument("--sources-ok", default="")
    ap.add_argument("--sources-fail", default="")
    a = ap.parse_args()

    if not os.path.exists(a.csv):
        print(f"[finalize] ERREUR: CSV introuvable: {a.csv}\n"
              "  -> lance d'abord un scan (locate_csv.py pour le bon chemin).", file=sys.stderr)
        sys.exit(2)

    datadir = os.path.dirname(os.path.abspath(a.csv))
    xlsx = a.xlsx or (a.csv[:-4] + ".xlsx" if a.csv.endswith(".csv") else a.csv + ".xlsx")
    report = a.report or os.path.join(datadir, "verif_stages.md")
    log = a.log or os.path.join(datadir, "scan_log.csv")

    print("== finalize : 1/2 dedup + nettoyage + rapport ==")
    run("verify_links.py", a.csv, "--sources", a.sources,
        "--stale-days", str(a.stale_days), "--fix", "--report", report)
    print("== finalize : 2/2 export Excel ==")
    run("format_xlsx.py", a.csv, xlsx)

    # ---- stats sur le CSV final ----
    rows = list(ic.load_csv(a.csv).values())
    total = len(rows)
    by_bucket, eu = {}, {"yes": 0, "no": 0, "?": 0}
    stale = 0
    for r in rows:
        by_bucket[r.get("bucket", "?")] = by_bucket.get(r.get("bucket", "?"), 0) + 1
        eu[r.get("in_europe", "?")] = eu.get(r.get("in_europe", "?"), 0) + 1
        d = days_since(r.get("last_seen", ""))
        if d is not None and d > a.stale_days:
            stale += 1

    # ---- JOURNAL (append) ----
    log_fields = ["date", "total", "added", "eu_yes", "eu_unknown", "stale",
                  "sources_ok", "sources_fail"]
    newfile = not os.path.exists(log)
    try:
        with open(log, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=log_fields)
            if newfile:
                w.writeheader()
            w.writerow({
                "date": date.today().isoformat(), "total": total,
                "added": "" if a.added is None else a.added,
                "eu_yes": eu["yes"], "eu_unknown": eu["?"], "stale": stale,
                "sources_ok": a.sources_ok, "sources_fail": a.sources_fail,
            })
    except Exception as e:
        print(f"[finalize] journal non ecrit ({e})", file=sys.stderr)

    # ---- RECAP ----
    order = ["bank_quant", "hedge_fund_quant", "data_scientist",
             "data_science_ai", "data_analyst", "consulting_data", "?"]
    buckets_str = ", ".join(f"{b}:{by_bucket[b]}" for b in order if by_bucket.get(b))
    print("\n================ RECAP SCAN ================")
    print(f"  Total offres   : {total}" + ("" if a.added is None else f"  (+{a.added} nouveaux)"))
    print(f"  Europe         : {eu['yes']} oui / {eu['?']} a confirmer / {eu['no']} non")
    print(f"  Perimees (>{a.stale_days}j): {stale}")
    print(f"  Par categorie  : {buckets_str}")
    if a.sources_ok or a.sources_fail:
        print(f"  Sources OK     : {a.sources_ok or '-'}")
        print(f"  Sources echec  : {a.sources_fail or '-'}")
    print(f"  Excel          : {xlsx}")
    print(f"  Rapport        : {report}")
    print(f"  Journal        : {log}")
    print("===========================================")


if __name__ == "__main__":
    main()
