#!/usr/bin/env python3
"""Extract text + layout from Google Document AI shards, discarding the images.

The 2025 pass over this journal left ~3,670 Document AI response shards on the
external SSD, 82 GB in total. Between 68% and 83% of every file is a base64
JPEG of the page, which we do not need -- the source PDFs are better copies at
higher resolution. What *is* unique and worth keeping is the layout: a bounding
box and a confidence score for every token, line, paragraph and block, which
Chandra does not produce at all.

This reduces each volume to one JSONL file, one record per page:

    {"identifier": ..., "page": 503, "width": 1681, "height": 2378,
     "text": "...", "conf_mean": 0.94, "conf_low_frac": 0.035,
     "lines": [{"t": "...", "b": [x0,y0,x1,y1], "c": 0.97}, ...]}

Boxes are reduced to an axis-aligned [x0,y0,x1,y1] in page pixels. Document AI
emits a four-vertex polygon to allow for skew, but these scans are deskewed and
the polygons are effectively rectangles; keeping four vertices triples the size
for no gain. `--keep-poly` preserves them if you need the skew.

Granularity is the size/detail dial:
    --granularity line   (default)  ~24 KB/page  -> ~1 GB for the whole set
    --granularity token             ~220 KB/page -> ~8 GB
    --granularity none              text only    -> ~250 MB

Usage:
    python3 10_extract_docai.py --src /mnt/e/data --out docai/
    python3 10_extract_docai.py --src /mnt/e/data --out docai/ --granularity token
    python3 10_extract_docai.py --src /mnt/e --out docai/ --only tropicalagricult1318ceyl
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

# Stray project files that sit alongside the real shards on the SSD.
NOT_A_SHARD = re.compile(
    r"^(meta|strings|accuracy|api_test_results|direct_url|factory_registrations"
    r"|registry_contents|spacy_training.*|overnight_processing_data.*"
    r"|\d+-reproducer)\.json$", re.I)

SHARD = re.compile(r"^(?P<ident>.+?)-(?P<idx>\d+)\.json$")


def anchor_span(layout: dict, text_len: int) -> tuple[int, int] | None:
    """Character range covered by a layout's textAnchor.

    Document AI omits `startIndex` when it is zero and sends both indices as
    strings, so neither can be read straight out of the JSON.
    """
    segs = (layout.get("textAnchor") or {}).get("textSegments") or []
    if not segs:
        return None
    start = min(int(s.get("startIndex", 0)) for s in segs)
    end = max(int(s.get("endIndex", 0)) for s in segs)
    if end <= start:
        return None
    return max(0, start), min(text_len, end)


def bbox(layout: dict, keep_poly: bool):
    """Axis-aligned [x0,y0,x1,y1] in page pixels, or the raw polygon."""
    poly = (layout.get("boundingPoly") or {})
    verts = poly.get("vertices") or []
    if not verts:
        # Some pages carry only normalized vertices.
        verts = poly.get("normalizedVertices") or []
        if not verts:
            return None
    if keep_poly:
        return [[v.get("x", 0), v.get("y", 0)] for v in verts]
    xs = [v.get("x", 0) for v in verts]
    ys = [v.get("y", 0) for v in verts]
    return [min(xs), min(ys), max(xs), max(ys)]


def page_records(shard: dict, granularity: str, keep_poly: bool):
    text = shard.get("text") or ""
    for page in shard.get("pages", []):
        span = anchor_span(page.get("layout") or {}, len(text))
        ptext = text[span[0]:span[1]] if span else ""
        dim = page.get("dimension") or {}

        units = []
        if granularity != "none":
            for u in page.get(granularity + "s", []):
                lay = u.get("layout") or {}
                s = anchor_span(lay, len(text))
                if not s:
                    continue
                rec = {"t": text[s[0]:s[1]]}
                b = bbox(lay, keep_poly)
                if b:
                    rec["b"] = b
                c = lay.get("confidence")
                if c is not None:
                    rec["c"] = round(float(c), 4)
                if u.get("detectedBreak", {}).get("type"):
                    rec["brk"] = u["detectedBreak"]["type"]
                units.append(rec)

        confs = [u["c"] for u in units if "c" in u]
        out = {
            "page": page.get("pageNumber"),
            "width": dim.get("width"),
            "height": dim.get("height"),
            "text": ptext,
            "n_blocks": len(page.get("blocks", [])),
            "n_lines": len(page.get("lines", [])),
            "n_tokens": len(page.get("tokens", [])),
        }
        langs = page.get("detectedLanguages") or []
        if langs:
            out["lang"] = langs[0].get("languageCode")
        if confs:
            out["conf_mean"] = round(sum(confs) / len(confs), 4)
            out["conf_low_frac"] = round(sum(1 for c in confs if c < 0.70) / len(confs), 4)
        if granularity != "none":
            out[granularity + "s"] = units
        yield out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True,
                    help="directory tree of Document AI shard JSONs")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--granularity", choices=("none", "line", "token", "paragraph", "block"),
                    default="line")
    ap.add_argument("--keep-poly", action="store_true",
                    help="keep four-vertex polygons instead of axis-aligned boxes")
    ap.add_argument("--only", action="append", default=[],
                    help="restrict to these identifiers (repeatable)")
    ap.add_argument("--limit-shards", type=int,
                    help="process at most N shards per identifier (for testing)")
    args = ap.parse_args()

    shards: dict[str, list[tuple[int, Path]]] = collections.defaultdict(list)
    for p in args.src.rglob("*.json"):
        if NOT_A_SHARD.match(p.name):
            continue
        m = SHARD.match(p.name)
        if not m:
            continue
        ident = m.group("ident")
        if args.only and ident not in args.only:
            continue
        shards[ident].append((int(m.group("idx")), p))

    if not shards:
        sys.exit(f"no Document AI shards found under {args.src}")

    args.out.mkdir(parents=True, exist_ok=True)
    print(f"{len(shards)} identifiers, {sum(len(v) for v in shards.values())} shards")

    grand_pages = grand_bytes = 0
    for ident in sorted(shards):
        files = sorted(shards[ident])
        if args.limit_shards:
            files = files[:args.limit_shards]
        dest = args.out / f"{ident}.pages.jsonl"
        npages = 0
        seen: set[int] = set()
        with dest.open("w") as fh:
            for idx, path in files:
                try:
                    shard = json.loads(path.read_text(errors="replace"))
                except Exception as exc:
                    print(f"  ! {path.name}: {exc}", file=sys.stderr)
                    continue
                for rec in page_records(shard, args.granularity, args.keep_poly):
                    # pageNumber is global across shards, so duplicates mean
                    # overlapping shards rather than genuine extra pages.
                    if rec["page"] in seen:
                        continue
                    seen.add(rec["page"])
                    rec["identifier"] = ident
                    rec["shard"] = idx
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    npages += 1
        size = dest.stat().st_size
        grand_pages += npages
        grand_bytes += size
        print(f"  {ident:48s} {len(files):4d} shards -> {npages:5d} pages, "
              f"{size/1048576:7.1f} MB")

    print(f"\n{grand_pages:,} pages, {grand_bytes/1073741824:.2f} GB -> {args.out}")


if __name__ == "__main__":
    main()
