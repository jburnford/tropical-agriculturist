#!/usr/bin/env python3
"""
Merge label files made against different skeleton versions into one set for the current
skeleton.jsonl. A unit's labels are taken only from a run whose skeleton had exactly the
same candidates for that unit (page, offset, text) -- labels are keyed by candidate id,
so a changed candidate list would silently mislabel. Later pairs win.

Usage: merge_labels.py OUT.jsonl LABELS_A.jsonl SKELETON_A.jsonl [LABELS_B SKELETON_B ...]
Exits non-zero if any current unit is left without labels.
"""
import json, sys

sig = lambda U: [(c["page"], c["offset"], c["text"]) for c in U["cands"]]
cur = {json.loads(l)["unit"]: json.loads(l) for l in open("skeleton.jsonl")}
out_path, pairs = sys.argv[1], sys.argv[2:]
got, src = {}, {}
for k in range(0, len(pairs), 2):
    labs = {json.loads(l)["unit"]: l for l in open(pairs[k])}
    skel = {json.loads(l)["unit"]: json.loads(l) for l in open(pairs[k + 1])}
    n = 0
    for u, U in cur.items():
        if u in labs and u in skel and sig(skel[u]) == sig(U):
            got[u], src[u] = labs[u], pairs[k]; n += 1
    print(f"{pairs[k]}: {n} units usable", file=sys.stderr)
missing = [u for u in cur if u not in got]
with open(out_path, "w") as f:
    for u in cur:
        if u in got:
            f.write(got[u] if got[u].endswith("\n") else got[u] + "\n")
print(f"{len(got)}/{len(cur)} units labelled -> {out_path}; missing {len(missing)}", file=sys.stderr)
for u in missing[:10]:
    print("  MISSING", u, file=sys.stderr)
sys.exit(1 if missing else 0)
