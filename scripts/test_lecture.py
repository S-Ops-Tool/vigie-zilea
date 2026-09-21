#!/usr/bin/env python3
"""Verifie que la lecture des articles fonctionne, sur un echantillon.

Aucun appel au modele : on mesure seulement ce qu'on arrive a lire, et
combien de texte on obtient par rapport au chapeau du flux.
"""
import sys
import pathlib
import collections

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from core import store, editorial, article    # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8

corpus = store.read_corpus()
mq, _, _ = editorial.eligible(corpus)
mq = editorial.dedupe(mq)[:N]
print(f"echantillon : {len(mq)} article(s)\n")

motifs = collections.Counter()
gains = []
for i, it in enumerate(mq, 1):
    avant = len(it.get("body_text") or "")
    t, d = article.corps(it.get("url", ""))
    src = (it.get("source") or "")[:22]
    if d.get("ok"):
        gains.append(len(t))
        print(f"  [{i}] {src:<22} {avant:>4} -> {len(t):>6} caracteres")
    else:
        motifs[d.get("motif", "?")] += 1
        print(f"  [{i}] {src:<22} {avant:>4} -> ECHEC : {d.get('motif')}")

print(f"\nlus : {len(gains)}/{len(mq)}")
if gains:
    gains.sort()
    print(f"texte obtenu : median {gains[len(gains)//2]} caracteres, max {gains[-1]}")
if motifs:
    print("echecs :", ", ".join(f"{m} x{n}" for m, n in motifs.most_common()))
