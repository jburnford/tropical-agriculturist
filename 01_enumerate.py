#!/usr/bin/env python3
"""Enumerate every Internet Archive item for The Tropical Agriculturist.

Two stages, both resumable:

  1. advancedsearch.php  -> inventory/ia_items_raw.json  (identifier list)
  2. /metadata/<id>      -> inventory/ia_meta.jsonl      (full per-item record)

Stage 2 is the expensive one (one request per item) and is where the volume and
issue numbers actually come from: the Tamil Digital Library scans carry no
`volume` metadata at all, but their *filenames* read
`..._Vol_37_no_2_1911.pdf`. Nothing downstream can resolve those without the
file list, so the file list is cached here rather than re-fetched.

Usage:
    python3 01_enumerate.py                # both stages, skipping cached items
    python3 01_enumerate.py --search-only
    python3 01_enumerate.py --refresh      # discard the identifier cache
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

INV = Path(__file__).resolve().parent / "inventory"
RAW = INV / "ia_items_raw.json"
META = INV / "ia_meta.jsonl"

UA = "TropicalAgriculturistResearch/1.0 (USask; jic823@usask.ca)"
# The `scrape` service, not advancedsearch.php. advancedsearch pages a *live*
# result set with no stable sort, so consecutive pages overlap and drift: a
# three-page run over this corpus returned 671 unique items out of a reported
# numFound of 694, silently losing 23. scrape is cursor-based and complete.
SCRAPE = "https://archive.org/services/search/v1/scrape"

# Title matching alone is not enough: several genuine volumes are catalogued
# with only a shelf-mark title (e.g. lbg.630.5.tag.v.45 is titled "The Tropical
# Agriculturist Vol LXV" but others in that family carry no usable title at
# all), so the known identifier families are matched too. This deliberately
# over-collects -- unrelated works that merely share the name are filtered
# later by ta_common.is_the_journal() and the volume/year outlier check.
QUERY = " OR ".join((
    'title:("tropical agriculturist")',
    "identifier:tropicalagricul*",
    "identifier:tropical-agriculturist*",
    "identifier:lbg.630.5.tag*",
    "identifier:lbg.630.05.tag*",
    "identifier:lbg.tropicalagricult*",
    "identifier:tropicalagri*book*issue*",
))
COUNT = 1000

# Fields worth keeping from the metadata record. The rest of an IA metadata
# blob is scanning telemetry we have no use for.
KEEP = ("title", "volume", "year", "date", "language", "collection",
        "imagecount", "sponsor", "contributor", "scanningcenter", "publisher")


def _get(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search() -> list[dict]:
    """Enumerate every matching item via the cursor-based scrape service."""
    docs: dict[str, dict] = {}
    cursor, total = None, None
    while True:
        params = [("q", QUERY), ("count", COUNT),
                  ("fields", "identifier,title,year,volume,date,imagecount,collection")]
        if cursor:
            params.append(("cursor", cursor))
        resp = json.loads(_get(f"{SCRAPE}?{urllib.parse.urlencode(params)}"))
        total = resp.get("total", total)
        for d in resp.get("items", []):
            docs[d["identifier"]] = d
        print(f"  {len(docs)}/{total} items", flush=True)
        cursor = resp.get("cursor")
        if not cursor:
            break
        time.sleep(1)
    if total is not None and len(docs) < total:
        print(f"  WARNING: scrape returned {len(docs)} of {total} reported items",
              file=sys.stderr)
    return list(docs.values())


def fetch_meta(ident: str) -> dict:
    url = "https://archive.org/metadata/" + urllib.parse.quote(ident)
    for attempt in range(4):
        try:
            d = json.loads(_get(url, timeout=60))
            md = d.get("metadata", {}) or {}
            return {
                "identifier": ident,
                **{k: md.get(k) for k in KEEP},
                "files": [
                    {"name": f["name"], "format": f.get("format"),
                     "size": int(f.get("size", 0) or 0)}
                    for f in d.get("files", [])
                ],
            }
        except Exception as exc:
            if attempt == 3:
                return {"identifier": ident, "error": str(exc)}
            time.sleep(2 * (attempt + 1))
    return {"identifier": ident, "error": "unreachable"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--search-only", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="re-run the search even if the identifier cache exists")
    ap.add_argument("--workers", type=int, default=5,
                    help="concurrent metadata requests (default: %(default)s)")
    args = ap.parse_args()

    INV.mkdir(exist_ok=True)

    if args.refresh or not RAW.exists():
        print("searching archive.org ...")
        items = search()
        RAW.write_text(json.dumps(items, indent=1))
        print(f"{len(items)} unique identifiers -> {RAW}")
    else:
        items = json.loads(RAW.read_text())
        print(f"{len(items)} identifiers from cache ({RAW}); --refresh to re-search")

    if args.search_only:
        return

    done: set[str] = set()
    if META.exists():
        for line in META.read_text().splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            # A previously failed fetch is worth retrying.
            if "error" not in rec:
                done.add(rec["identifier"])

    todo = [d["identifier"] for d in items if d["identifier"] not in done]
    print(f"metadata: {len(done)} cached, {len(todo)} to fetch")
    if not todo:
        return

    with META.open("a") as fh, ThreadPoolExecutor(max_workers=args.workers) as ex:
        for n, rec in enumerate(ex.map(fetch_meta, todo), 1):
            fh.write(json.dumps(rec) + "\n")
            if n % 25 == 0:
                fh.flush()
                print(f"  {n}/{len(todo)}", flush=True)

    errs = sum(1 for line in META.read_text().splitlines()
               if '"error"' in line)
    print(f"done -> {META}" + (f" ({errs} items still erroring; re-run to retry)" if errs else ""))


if __name__ == "__main__":
    main()
