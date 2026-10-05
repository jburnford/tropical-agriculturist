#!/usr/bin/env python3
"""
Per-page health scan of an OCR tree (Stage 4 groundwork).

For every page of every document listed in the chunk files, write one row:
  tag page tok chars zratio top_line_rep end_repeat
to STDOUT (TSV). Signals:

  tok           token_count from Chandra's metadata. 0 = vLLM error (Chandra
                returns raw="" on a failed request and the metadata keeps no
                error flag) or a genuinely empty page; >= cap = loop/truncation.
  chars         non-whitespace characters of the page markdown, image links removed.
  zratio        zlib-compressed size / raw size. Loops compress far better than prose.
  top_line_rep  count of the most frequent line (len >= 12) on the page.
  end_repeat    Chandra's own detect_repeat_token on the page text (the same
                test it uses to trigger a retry) -- 1 if it still fires.

Usage: scan_pages.py OUTDIR CHUNKDIR > pages.tsv
"""
import collections, json, pathlib, re, sys, zlib

sys.path.insert(0, "/scratch/jic823/chandra/venv/lib/python3.11/site-packages")
from chandra.model.util import detect_repeat_token  # noqa: E402

MARK = re.compile(r"^\d+-{48}\s*$", re.M)
IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")

out_root, chunk_dir = map(pathlib.Path, sys.argv[1:3])
print("tag\tpage\ttok\tchars\tzratio\ttop_line_rep\tend_repeat")
for chunk in sorted(chunk_dir.glob("chunk_*.tsv")):
    for row in chunk.read_text().splitlines():
        tag = row.split("\t")[0]
        d = out_root / tag
        md = next(d.rglob("*.md"))
        meta = json.load(open(next(d.rglob("*_metadata.json"))))
        pages = MARK.split(md.read_text(errors="replace"))
        toks = {p["page_num"]: int(p["token_count"]) for p in meta["pages"]}
        if len(pages) != len(toks):
            sys.exit(f"{tag}: {len(pages)} md pages vs {len(toks)} metadata pages")
        for i, txt in enumerate(pages):
            body = IMG.sub("", txt)
            raw = body.encode()
            chars = len(re.sub(r"\s", "", body))
            z = len(zlib.compress(raw)) / len(raw) if len(raw) > 200 else 1.0
            lines = [l.strip() for l in body.splitlines() if len(l.strip()) >= 12]
            rep = max(collections.Counter(lines).values()) if lines else 0
            er = int(detect_repeat_token(txt.rstrip()))
            print(f"{tag}\t{i}\t{toks[i]}\t{chars}\t{z:.3f}\t{rep}\t{er}")
