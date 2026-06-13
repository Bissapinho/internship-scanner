#!/usr/bin/env python3
"""
locate_csv.py — RETROUVE le CSV canonique des stages entre deux scans.

Probleme resolu : garantir la CONTINUITE de l'historique. Le CSV ne doit jamais
repartir de zero parce que l'agent a pointe un autre dossier. Ce script cherche un
`stages_quant_ds.csv` existant dans les dossiers connectes (roots), et :
  - s'il en trouve un -> imprime son chemin (on REUTILISE l'historique) ;
  - s'il en trouve plusieurs -> garde le plus "fourni" (plus de lignes, puis plus recent) ;
  - s'il n'en trouve aucun -> imprime le chemin par defaut (a creer au prochain ecrit).

Emplacement canonique recommande : <repo>/data/stages_quant_ds.csv (dossier `data/`
gitignore -> donnees locales, non versionnees).

Aucun reseau. Lecture seule (n'ecrit rien).

Usage:
  python locate_csv.py --roots <dir1> [<dir2> ...] [--name stages_quant_ds.csv] \
                       --default <chemin_par_defaut>
Sortie : une seule ligne = le chemin a utiliser pour OUT.
"""
import argparse, os, csv, sys

def count_rows(path):
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return sum(1 for _ in csv.reader(f)) - 1  # -1 entete
    except Exception:
        return -1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="*", default=[])
    ap.add_argument("--name", default="stages_quant_ds.csv")
    ap.add_argument("--default", required=True)
    ap.add_argument("--max-depth", type=int, default=6)
    a = ap.parse_args()

    found = []
    for root in a.roots:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            # bornage profondeur + on saute .git et caches
            if dirpath.count(os.sep) - base_depth > a.max_depth:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules")]
            if a.name in filenames:
                p = os.path.join(dirpath, a.name)
                found.append((count_rows(p), os.path.getmtime(p), p))

    if found:
        # plus de lignes d'abord, puis plus recent
        found.sort(key=lambda t: (t[0], t[1]), reverse=True)
        print(found[0][2])
        print(f"[locate] {len(found)} CSV trouve(s), choisi: {found[0][2]} "
              f"({found[0][0]} lignes)", file=sys.stderr)
    else:
        print(os.path.abspath(a.default))
        print(f"[locate] aucun CSV existant -> defaut: {os.path.abspath(a.default)}",
              file=sys.stderr)

if __name__ == "__main__":
    main()
