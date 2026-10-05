#!/usr/bin/env python3
"""Build a per-page index (issue date + printed page number) from Document AI.

This is the single most useful thing the Google data gives us, and it fixes a
known weakness in the Chandra output. Chandra emits continuous Markdown with no
page breaks: the `sessional_papers` corpus had to recover page numbers from
image anchors plus token-count interpolation, accurate only to within a few
pages. That makes precise citation impossible.

The Document AI layout solves it exactly. Every page of this journal carries a
running head spanning the top of the page, which Document AI captures as
separate positioned lines:

    468 | THE TROPICAL AGRICULTURIST. | [JAN. 1, 1894.

Taking every line in the top ~7.5% of the page and sorting left-to-right
recovers the printed page number and the issue date together, on every page
rather than the one-in-ten a topmost-line heuristic finds.

The printed page numbers carry OCR noise (a "470" read as "476", a folio
missed entirely). They are repaired by *modal offset* rather than from
immediate neighbours: within a run of continuous pagination the folio is just
the scan page plus a constant, so the offset is computed for every page that
has a folio, and each page then takes the most common offset in a window
around it. A neighbour-based repair cannot fix two adjacent errors -- and in
the sample volume, scan pages 504 and 505 were adjacent errors (a misread 476
and a missing folio), which is precisely the case that defeated it. The offset
method recovers both, and tolerates the offset genuinely changing at front
matter and supplement boundaries.

Output, one row per page:

    identifier, scan_page, printed_page, printed_page_repaired, issue_date,
    date_iso, conf_mean, running_head

Usage:
    python3 11_page_index.py --src docai/ --out page_index.csv
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path

MONTHS = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6, "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12,
}
# "JAN. 1, 1894" / "JANUARY 1894" / "JAN 15, 1902"
DATE = re.compile(r"\b([A-Z]{3,9})\.?\s*(\d{1,2})?\s*,?\s*(18\d\d|19\d\d)\b")
PAGENO = re.compile(r"^\s*[\[\(]?(\d{1,4})[\]\)\.]?\s*$")

TOP_BAND = 0.075   # fraction of page height treated as the running head


def running_head(rec: dict) -> list[dict]:
    """Lines in the top band, ordered left to right."""
    lines = [l for l in (rec.get("lines") or [])
             if l.get("b") and l["b"][1] < TOP_BAND * (rec.get("height") or 2400)]
    return sorted(lines, key=lambda l: l["b"][0])


def parse_date(text: str) -> tuple[str, str]:
    """(raw match, ISO-ish date) from a running head."""
    for m in DATE.finditer(text):
        mon = MONTHS.get(m.group(1).upper())
        if not mon:
            continue
        year, day = int(m.group(3)), m.group(2)
        iso = f"{year:04d}-{mon:02d}" + (f"-{int(day):02d}" if day else "")
        return m.group(0), iso
    return "", ""


def parse_printed_page(band: list[dict]) -> str:
    """The printed folio, which sits at the outer edge of the running head.

    Only the leftmost and rightmost lines are considered: a bare number in the
    middle of the head would be part of the title, and body text that drifts
    into the top band must not be mistaken for a folio.
    """
    for l in ([band[0], band[-1]] if len(band) > 1 else band):
        m = PAGENO.match(l["t"].strip())
        if m:
            return m.group(1)
    return ""


def repair_by_offset(pages: list[dict], window: int = 10) -> tuple[int, int]:
    """Repair folios using the locally modal (folio - scan_page) offset.

    Returns (n_corrected, n_filled): values replaced because they disagreed
    with the local offset, and values supplied where OCR found none.

    A window rather than a single volume-wide offset because pagination is not
    continuous across a whole volume -- front matter, indexes and bound-in
    supplements each restart it.
    """
    offs: list[int | None] = []
    for p in pages:
        folio, scan = p["printed_page"], p["scan_page"]
        offs.append(int(folio) - int(scan)
                    if folio.isdigit() and scan is not None else None)

    corrected = filled = 0
    for i, p in enumerate(pages):
        lo, hi = max(0, i - window), min(len(pages), i + window + 1)
        local = [o for o in offs[lo:hi] if o is not None]
        if len(local) < 3:
            continue
        modal = collections.Counter(local).most_common(1)[0]
        # Require the offset to be genuinely dominant, not a coin toss between
        # two readings, before overruling what the OCR actually saw.
        if modal[1] < 3:
            continue
        k = modal[0]
        if p["scan_page"] is None:
            continue
        expected = int(p["scan_page"]) + k
        if expected < 1:
            continue
        if not p["printed_page"].isdigit():
            p["printed_page_repaired"] = str(expected)
            filled += 1
        elif int(p["printed_page"]) != expected:
            p["printed_page_repaired"] = str(expected)
            corrected += 1
    return corrected, filled


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True,
                    help="directory of *.pages.jsonl from 10_extract_docai.py")
    ap.add_argument("--out", type=Path, default=Path("page_index.csv"))
    args = ap.parse_args()

    files = sorted(args.src.glob("*.pages.jsonl"))
    if not files:
        sys.exit(f"no *.pages.jsonl under {args.src} -- run 10_extract_docai.py first")

    rows, stats = [], []
    for f in files:
        recs = [json.loads(l) for l in f.open()]
        recs.sort(key=lambda r: r.get("page") or 0)
        vol_rows = []
        for r in recs:
            band = running_head(r)
            head = " | ".join(l["t"].strip().replace("\n", " ") for l in band)
            raw, iso = parse_date(head)
            vol_rows.append({
                "identifier": r.get("identifier", f.stem.replace(".pages", "")),
                "scan_page": r.get("page"),
                "printed_page": parse_printed_page(band),
                "printed_page_repaired": "",
                "issue_date": raw,
                "date_iso": iso,
                "conf_mean": r.get("conf_mean", ""),
                "running_head": head[:160],
            })
        corrected, filled = repair_by_offset(vol_rows)
        rows.extend(vol_rows)
        dated = sum(1 for r in vol_rows if r["date_iso"])
        folio = sum(1 for r in vol_rows if r["printed_page"] or r["printed_page_repaired"])
        stats.append((f.stem.replace(".pages", ""), len(vol_rows), dated, folio,
                      corrected, filled))

    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f"{'identifier':44s} {'pages':>6} {'dated':>8} {'folio':>8} {'corr':>6} {'filled':>7}")
    print("-" * 84)
    for ident, n, dated, folio, corrected, filled in stats:
        print(f"{ident:44s} {n:6d} {dated:5d}{100*dated//max(n,1):>3}% "
              f"{folio:5d}{100*folio//max(n,1):>3}% {corrected:6d} {filled:7d}")
    tot = len(rows)
    print("-" * 80)
    print(f"{'TOTAL':44s} {tot:6d} "
          f"{sum(s[2] for s in stats):5d}{100*sum(s[2] for s in stats)//max(tot,1):>3}% "
          f"{sum(s[3] for s in stats):5d}{100*sum(s[3] for s in stats)//max(tot,1):>3}% "
          f"{sum(s[4] for s in stats):6d} {sum(s[5] for s in stats):7d}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
