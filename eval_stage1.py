#!/usr/bin/env python3
"""
Stage 1 evaluation: page-slice test output (output_v4_test) vs the v1 run.

For each TEST_ document:
  * folios   -- per-page folio (number at page edge), coverage, and how often
                consecutive detected folios step by exactly +1
  * runhead  -- pages whose first 3 lines mention TROPICAL AGRICULTURIST
  * capped   -- the pages that hit 12,384 tokens in v1: new token count and
                the last 150 chars of the page
  * body     -- share of v4 word 8-grams also present in v1's whole volume.
                v1 has no page breaks, so this is containment in the volume,
                not page alignment. Header/footer lines are new by design and
                are excluded (first/last 2 lines of each page).
Usage: eval_stage1.py BASE_DIR
"""
import json, pathlib, re, sys

base = pathlib.Path(sys.argv[1])
exec(open(base / "check_doc.py").read().split("def main")[0])   # MARK, LEAD, TRAIL, YEAR

def folio_of(lines):
    for ln in lines:
        for rx in (LEAD, TRAIL):
            m = rx.search(ln)
            if m and int(m.group(1)) not in YEAR:
                return int(m.group(1))
    return None

def words(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.findall(r"[a-z0-9]+", s.lower())

def grams(w, n=8):
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}

chunk = [l.rstrip("\n").split("\t") for l in open(base / "chunks_test/chunk_001.tsv")]
for tag, pdf, pages, rng in chunk:
    vol = tag[len("TEST_"):]
    d = base / "output_v4_test" / tag
    md = next(d.rglob("*.md"), None)
    if md is None:
        print(f"== {tag}: NO OUTPUT"); continue
    meta = json.load(open(next(d.rglob("*_metadata.json"))))
    idx = [i for a, b in (r.split("-") for r in rng.split(",")) for i in range(int(a), int(b) + 1)]
    ptxt = MARK.split(md.read_text(errors="replace"))[::2]
    lines = [[l for l in p.splitlines() if l.strip()] for p in ptxt]

    fol = [folio_of(b[:3] + b[-3:]) if b else None for b in lines]
    have = [f for f in fol if f is not None]
    steps = [(i, j) for i, j in zip(fol, fol[1:]) if i is not None and j is not None]
    step1 = sum(j - i == 1 for i, j in steps)
    rh = sum(bool(b) and any("TROPICAL AGRICULTURIST" in l.upper() for l in b[:3]) for b in lines)

    v1md = next((base / "output" / vol).rglob("*.md"))
    v1meta = json.load(open(next((base / "output" / vol).rglob("*_metadata.json"))))
    v1tok = {int(p["page_num"]): int(p["token_count"]) for p in v1meta["pages"]}
    v1g = grams(words(v1md.read_text(errors="replace")))
    bw = [w for b in lines for w in words("\n".join(b[2:-2]))]
    g = grams(bw)
    contain = len(g & v1g) / max(len(g), 1)

    print(f"== {tag}  range {rng}")
    print(f"   pages {meta['num_pages']} (expected {pages}), markers {len(MARK.findall(md.read_text()))}")
    print(f"   folio on {len(have)}/{len(lines)} pages; consecutive +1 steps {step1}/{len(steps)}")
    print(f"   running head in first 3 lines: {rh}/{len(lines)}")
    print(f"   folios: {fol[:12]} ... {fol[-6:]}")
    print(f"   body 8-gram containment in v1: {contain:.3f}  ({len(g)} grams)")
    for k, pn in enumerate(idx):
        if v1tok.get(pn, 0) >= 12000:
            t = int(meta["pages"][k]["token_count"])
            tail = ptxt[k].strip()[-150:].replace("\n", " | ")
            print(f"   CAPPED-in-v1 page {pn}: v1 {v1tok[pn]} -> v4 {t} tokens; tail: ...{tail}")
