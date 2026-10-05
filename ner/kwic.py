#!/usr/bin/env python3
"""KWIC + collocation summary over canonical article text.
Usage: kwic.py TERM [TERM...]  (TERM is a regex, matched case-insensitively on whole words)
Prints: hits, articles, decade spread, top left/right collocates (1-2 words), and sample lines."""
import gzip, json, re, sys, collections, random, pathlib
random.seed(1)
BY = pathlib.Path(__file__).resolve().parent.parent / "articles/by_year"
TAG = re.compile(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)|[*#_]+|\d+-{20,}")
def texts():
    for f in sorted(BY.glob("articles_*.jsonl.gz")):
        for l in gzip.open(f, "rt", encoding="utf-8"):
            r = json.loads(l)
            if r["canonical"] and r["kind"] == "article":
                yield r, re.sub(r"\s+", " ", TAG.sub(" ", r["text"]))
terms = sys.argv[1:]
pats = {t: re.compile(rf"\b({t})\b", re.I) for t in terms}
hits = {t: 0 for t in terms}; arts = {t: set() for t in terms}; dec = {t: collections.Counter() for t in terms}
L1 = {t: collections.Counter() for t in terms}; R1 = {t: collections.Counter() for t in terms}
L2 = {t: collections.Counter() for t in terms}; R2 = {t: collections.Counter() for t in terms}
samples = {t: [] for t in terms}; n_art = 0
for r, txt in texts():
    n_art += 1
    for t, p in pats.items():
        for m in p.finditer(txt):
            hits[t] += 1; arts[t].add(r["id"]); dec[t][r["issue"][:3] + "0s"] += 1
            left = txt[max(0, m.start() - 60):m.start()]; right = txt[m.end():m.end() + 60]
            lw = re.findall(r"[A-Za-z][A-Za-z'&.-]*", left); rw = re.findall(r"[A-Za-z][A-Za-z'&.-]*", right)
            if lw: L1[t][lw[-1]] += 1
            if len(lw) > 1: L2[t][" ".join(lw[-2:])] += 1
            if rw: R1[t][rw[0]] += 1
            if len(rw) > 1: R2[t][" ".join(rw[:2])] += 1
            if len(samples[t]) < 4000: samples[t].append((r["issue"], left[-45:], m.group(0), right[:45]))
print(f"{n_art} canonical articles scanned")
for t in terms:
    print(f"\n=== {t!r}: {hits[t]:,} hits in {len(arts[t]):,} articles; by decade {dict(sorted(dec[t].items()))}")
    print("  left word :", ", ".join(f"{w} {c}" for w, c in L1[t].most_common(14)))
    print("  right word:", ", ".join(f"{w} {c}" for w, c in R1[t].most_common(14)))
    print("  left 2    :", " | ".join(f"{w} {c}" for w, c in L2[t].most_common(10)))
    print("  right 2   :", " | ".join(f"{w} {c}" for w, c in R2[t].most_common(10)))
    for s in random.sample(samples[t], min(10, len(samples[t]))):
        print(f"  {s[0]}  {s[1]:>45} [{s[2]}] {s[3]}")
