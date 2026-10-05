#!/usr/bin/env python3
"""Build the job manifest: page count, bucket and walltime per downloaded PDF.

Walltime matters more here than it looks. Chandra writes a document only once
its last page is finished, so a volume that overruns its walltime produces
*nothing at all* -- there is no checkpointing and no partial output. Budgeting
generously is far cheaper than a re-run.

The planning rate is *measured*, not assumed. The sessional_papers corpus was
run on these same 3g.40gb MIG slices (job 20413297, 132 completed tasks of
858-1,962 pages each), which gives a real distribution:

    gross pages/min, including model load:  p10 9.2   median 14.3   p90 25.2
    slowest single volume observed:          6.5

MIG slices are therefore *faster* than the 9 pages/min once measured on a whole
H100 -- that older figure came from a different run and should not be used.

The default below is the **p10, not the median**: budgeting at the tenth
percentile means nine volumes in ten finish comfortably, and the escalation
ladder in 05_submit.sh handles the rest. At p10 with the safety multiplier, a
1,200-page volume is budgeted 208 minutes, which still covers the slowest rate
ever observed (6.5 pages/min -> 185 min + startup).

This corpus is slightly heavier than the sessional papers: the Cornell scans of
the 1890s run to 1,100-1,200 pages, against ~811 average there.

Usage:
    python3 04_manifest.py --pdfs pdfs/ --out manifest.tsv
    python3 04_manifest.py --pdfs pdfs/ --volumes 1-101   # stop at 1945
    python3 04_manifest.py --pdfs pdfs/ --rate 7.5        # re-budget
"""
from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

# Pages/min on a 3g.40gb MIG slice, including model load: the p10 of 132
# measured tasks. See the module docstring.
DEFAULT_PAGES_PER_MIN = 9.2
STARTUP_MIN = 25.0      # vLLM load + readiness, padded for Lustre contention
DEFAULT_SAFETY = 1.4

# (bucket, walltime limit in minutes). A volume lands in the first bucket it
# fits. Larger than the sessional-papers ladder because the volumes are longer
# and the slices are slower.
BUCKETS = [("b2h", 120), ("b4h", 240), ("b8h", 480), ("b16h", 960)]


def parse_volume_filter(spec: str | None) -> set[int] | None:
    """Parse "1-101" / "1-10,41,44" into a set of volume numbers."""
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


def volume_of_tag(tag: str) -> int | None:
    """Volume number from a tag written by 03_download.py (vol058_iss02_...)."""
    m = re.match(r"vol(\d{3})", tag)
    return int(m.group(1)) if m else None


def page_count(pdf: Path) -> int | None:
    try:
        import pypdfium2
        return len(pypdfium2.PdfDocument(str(pdf)))
    except ImportError:
        pass
    except Exception as exc:
        print(f"  {pdf.name}: pypdfium2 failed ({exc})", file=sys.stderr)
        return None
    try:
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True,
                             text=True, check=True).stdout
        for line in out.splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
    except Exception:
        pass
    return None


def hhmmss(minutes: float) -> str:
    m = int(math.ceil(minutes))
    return f"{m // 60}:{m % 60:02d}:00"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdfs", type=Path, default=Path("pdfs"))
    ap.add_argument("--out", type=Path, default=Path("manifest.tsv"))
    ap.add_argument("--rate", type=float, default=DEFAULT_PAGES_PER_MIN,
                    help="planning rate, pages/min (default: %(default)s)")
    ap.add_argument("--safety", type=float, default=DEFAULT_SAFETY,
                    help="buffer multiplier (default: %(default)s)")
    ap.add_argument("--volumes", help='restrict to these volumes, e.g. "1-101"')
    args = ap.parse_args()

    pdfs = sorted(args.pdfs.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDFs under {args.pdfs} -- run 03_download.py first.")

    keep = parse_volume_filter(args.volumes)
    if keep is not None:
        before = len(pdfs)
        pdfs = [p for p in pdfs if (v := volume_of_tag(p.stem)) and v in keep]
        print(f"volume filter {args.volumes}: {len(pdfs)} of {before} PDFs")
        if not pdfs:
            sys.exit("volume filter excluded everything")

    rows, unreadable, total_pages = [], [], 0
    for pdf in pdfs:
        pages = page_count(pdf)
        if not pages:
            unreadable.append(pdf.name)
            continue
        total_pages += pages
        mins = (pages / args.rate) * args.safety + STARTUP_MIN
        bucket = next((b for b, lim in BUCKETS if mins <= lim), None)
        if bucket is None:
            bucket = BUCKETS[-1][0]
            print(f"  WARNING: {pdf.stem} needs ~{mins:.0f} min, over the "
                  f"largest bucket; capped at {bucket}. Consider splitting it.",
                  file=sys.stderr)
        rows.append((pdf.stem, str(pdf.resolve()), pages, bucket,
                     hhmmss(dict(BUCKETS)[bucket])))

    rows.sort(key=lambda r: r[2])
    with args.out.open("w") as fh:
        fh.write("# tag\tpdf\tpages\tbucket\twalltime\n")
        for r in rows:
            fh.write("\t".join(str(x) for x in r) + "\n")

    print(f"{len(rows)} documents, {total_pages:,} pages -> {args.out}")
    print(f"estimated ~{total_pages / args.rate / 60:.0f} GPU-hours at "
          f"{args.rate} pages/min")
    print(f"walltime budgeted at {args.rate / args.safety:.1f} pages/min "
          f"effective + {STARTUP_MIN:.0f} min startup")
    for b, lim in BUCKETS:
        n = sum(1 for r in rows if r[3] == b)
        if n:
            print(f"  {b:5s} (<= {lim:4d} min): {n:4d} documents")
    if unreadable:
        print(f"\n{len(unreadable)} unreadable PDFs (re-download these):",
              file=sys.stderr)
        for u in unreadable:
            print(f"  {u}", file=sys.stderr)


if __name__ == "__main__":
    main()
