#!/usr/bin/env python3
"""Download the chosen Tropical Agriculturist PDFs from the Internet Archive.

Reads inventory/ta_manifest.csv (written by 02_inventory.py) and fetches one
PDF per row into --out. Intended to run on a Nibi login node, which has both
outbound internet and the bandwidth; compute nodes have neither.

Resumable and idempotent: a file already present at roughly its expected size
is left alone, so re-running after an interruption fetches only what is
missing.

Usage:
    python3 03_download.py --out /project/def-jic823/tropical/pdfs
    python3 03_download.py --out pdfs --volumes 1-55     # a subset
    python3 03_download.py --out pdfs --dry-run
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import ta_common as T

UA = "TropicalAgriculturistResearch/1.0 (USask; jic823@usask.ca)"
DOWNLOAD = "https://archive.org/download/{ident}/{fname}"
MIN_BYTES = 512_000
# IA's reported size and the delivered file agree closely, but derivative PDFs
# are occasionally regenerated. Accept anything within 2%.
SIZE_TOL = 0.02


def tag_for(row: dict) -> str:
    """Stable, sortable, filesystem-safe name for one downloaded volume/issue.

    Volume-prefixed so that a directory listing reads in series order, with
    the IA identifier retained so every output traces back to its source.
    """
    vol = row["volume"]
    parts = [f"vol{int(vol):03d}" if vol else "volXXX"]
    if row.get("issue"):
        parts.append(f"iss{int(row['issue']):02d}")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", row["identifier"]).strip("-")
    parts.append(slug[:60])
    return "_".join(parts)


def parse_volume_filter(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    keep: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            keep.update(range(int(a), int(b) + 1))
        elif part:
            keep.add(int(part))
    return keep


def download_one(row: dict, dest: Path, retries: int) -> tuple[bool, str]:
    expected = float(row["pdf_mb"]) * 1048576
    if dest.exists():
        got = dest.stat().st_size
        if got > MIN_BYTES and (not expected or abs(got - expected) / expected <= SIZE_TOL):
            return True, f"present ({got/1048576:.0f} MB)"
        print(f"    size mismatch (have {got/1048576:.1f} MB, "
              f"expect {expected/1048576:.1f} MB) - refetching", file=sys.stderr)

    url = DOWNLOAD.format(ident=urllib.parse.quote(row["identifier"]),
                          fname=urllib.parse.quote(row["pdf_name"]))
    tmp = dest.with_suffix(".pdf.part")
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=1800) as r, tmp.open("wb") as fh:
                while chunk := r.read(1 << 20):
                    fh.write(chunk)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(5 * attempt)
                continue
            return False, f"download failed: {exc}"

        size = tmp.stat().st_size
        if size <= MIN_BYTES:
            tmp.unlink()
            if attempt < retries:
                time.sleep(5 * attempt)
                continue
            return False, f"truncated ({size} bytes)"
        with tmp.open("rb") as fh:
            if fh.read(5) != b"%PDF-":
                tmp.unlink()
                return False, "served content is not a PDF"
        tmp.rename(dest)
        return True, f"{size/1048576:.0f} MB"
    return False, "exhausted retries"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=T.INV / "ta_manifest.csv")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--volumes", help='e.g. "1-55" or "1-10,41,44"')
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(args.manifest.open()) if r["pdf_name"]]
    keep = parse_volume_filter(args.volumes)
    if keep is not None:
        rows = [r for r in rows if r["volume"] and int(r["volume"]) in keep]
    if not rows:
        sys.exit("nothing to download (check --volumes / run 02_inventory.py)")

    total_mb = sum(float(r["pdf_mb"]) for r in rows)
    print(f"{len(rows)} files, {total_mb/1024:.1f} GB -> {args.out}")
    if args.dry_run:
        for r in rows[:15]:
            print(f"  vol {r['volume'] or '?':>3}  {float(r['pdf_mb']):6.1f} MB  {tag_for(r)}")
        if len(rows) > 15:
            print(f"  ... and {len(rows)-15} more")
        return

    args.out.mkdir(parents=True, exist_ok=True)
    log = args.out.parent / "download_log.tsv"
    ok, failed = 0, []
    with log.open("a") as lg:
        for i, row in enumerate(rows, 1):
            dest = args.out / f"{tag_for(row)}.pdf"
            print(f"[{i}/{len(rows)}] vol {row['volume'] or '?'} {row['identifier'][:48]}",
                  flush=True)
            good, msg = download_one(row, dest, args.retries)
            print(f"    {msg}", flush=True)
            lg.write(f"{time.strftime('%FT%T')}\t{row['identifier']}\t"
                     f"{dest.name}\t{'ok' if good else 'FAIL'}\t{msg}\n")
            lg.flush()
            if good:
                ok += 1
            else:
                failed.append(row["identifier"])
            if i < len(rows) and not msg.startswith("present"):
                time.sleep(args.delay)

    print(f"\ndownloaded/verified {ok}, failed {len(failed)}")
    if failed:
        out = args.out.parent / "still_missing.txt"
        out.write_text("\n".join(failed) + "\n")
        print(f"failures -> {out}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
