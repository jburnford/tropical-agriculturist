#!/usr/bin/env python3
"""Reconcile IA holdings of The Tropical Agriculturist into a download set.

The journal was digitised several times over by unrelated projects (Cornell /
BHL, the Indian "lbg" and "dli" libraries, the Tamil Digital Library, and a
per-issue scan of the whole run). The same volume therefore appears up to five
times under wholly different identifier schemes. This script picks one copy per
volume and says why.

Outputs (all under inventory/):
    ta_items.csv     every item, with volume/issue resolved
    ta_manifest.csv  the de-duplicated download set
    coverage.txt     coverage and gap report

Usage:
    python3 02_inventory.py [--local-holdings e_drive_files.txt]
"""
from __future__ import annotations

import argparse
import collections
import csv
import re
import sys
from pathlib import Path

import ta_common as T


def _year_of(rec: dict) -> str:
    """First plausible 4-digit year from `year` or `date`.

    Guard against the free-text dates in this corpus: "April-May 1926" would
    otherwise yield a year of "Apri".
    """
    for key in ("year", "date"):
        m = re.search(r"\b(1[89]\d\d)\b", str(rec.get(key) or ""))
        if m:
            return m.group(1)
    return ""


MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"), start=1)}


def _year_month(rec_id: str, year: str) -> tuple[int, int] | None:
    """(year, month) from a per-issue identifier, e.g. ..._1934-07 or
    ..._april-may-1926_66_4-5."""
    if not year:
        return None
    m = re.search(r"_(\d{4})-(\d{2})(?:_|$)", rec_id)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"_([a-z]+)(?:-[a-z]+)?-(\d{4})", rec_id)
    if m and m.group(1) in MONTHS:
        return int(m.group(2)), MONTHS[m.group(1)]
    return None


def infer_missing_volumes(rows: list[dict]) -> int:
    """Fill in volumes for date-only per-issue items.

    From 1913 the journal published two volumes a year, January-June and
    July-December. Items identified only by date (`..._1934-07`) carry no
    volume, but their siblings in the same half-year do. Rather than hardcode
    a volume-to-year table, learn the (year, half) -> volume map from every
    item that resolved, then apply it. This is what recovers volumes 83, 86
    and 88, which have no volume-numbered items at all.
    """
    learned: dict[tuple[int, int], set[int]] = collections.defaultdict(set)
    for r in rows:
        ym = _year_month(r["identifier"], r["year"])
        if ym and r["volume"]:
            learned[(ym[0], 0 if ym[1] <= 6 else 1)].add(int(r["volume"]))

    filled = 0
    for r in rows:
        if r["volume"]:
            continue
        ym = _year_month(r["identifier"], r["year"])
        if not ym:
            continue
        year, half = ym[0], 0 if ym[1] <= 6 else 1
        cands = learned.get((year, half))
        # Only trust an unambiguous map: one volume for that half-year.
        if cands and len(cands) == 1:
            r["volume"] = next(iter(cands))
            r["volume_inferred"] = 1
            filled += 1
            continue
        # Nothing known for this half-year, so step to its neighbour: in the
        # two-volumes-a-year era the January-June volume is exactly one below
        # the July-December volume of the same year. This is what recovers
        # volumes 86 (Jan-Jun 1936) and 88 (Jan-Jun 1937), for which no
        # volume-numbered item survives at all -- only their second-half
        # siblings, 87 and 89.
        sibling = learned.get((year, 1 - half))
        if sibling and len(sibling) == 1:
            v = next(iter(sibling))
            r["volume"] = v - 1 if half == 0 else v + 1
            r["volume_inferred"] = 1
            filled += 1
    return filled


def volume_year_outliers(rows: list[dict], tol: int = 3) -> list[dict]:
    """Flag items whose volume disagrees with their year.

    The series runs ~2 volumes/year for most of its life, so volume and year
    are near-linearly related. Fitting that line across the whole corpus and
    measuring each item against it catches the bad title metadata that the
    identifier-first precedence in ta_common cannot -- e.g. a "Vol-VI" title
    on an item dated 1928. Purely diagnostic; nothing is dropped on this
    basis, because the fit is only ever approximate.
    """
    pts = [(int(r["volume"]), int(r["year"]))
           for r in rows if r["volume"] and r["year"]]
    if len(pts) < 20:
        return []
    n = len(pts)
    mx = sum(v for v, _ in pts) / n
    my = sum(y for _, y in pts) / n
    var = sum((v - mx) ** 2 for v, _ in pts)
    if not var:
        return []
    slope = sum((v - mx) * (y - my) for v, y in pts) / var
    intercept = my - slope * mx
    out = []
    for r in rows:
        if not (r["volume"] and r["year"]):
            continue
        pred = slope * int(r["volume"]) + intercept
        err = int(r["year"]) - pred
        if abs(err) > tol * 4:          # ~12 years off the trend line
            out.append({**r, "predicted_year": round(pred), "error_years": round(err)})
    return out


def build_rows(recs: list[dict]) -> list[dict]:
    rows = []
    for r in recs:
        vol, issue = T.resolve_vol_issue(r)
        pdf = T.best_pdf(r)
        rows.append({
            "identifier": r["identifier"],
            "family":     T.family(r["identifier"]),
            "volume":     vol,
            "issue":      issue,
            "year":       _year_of(r),
            "is_index":   int(T.is_index_only(r)),
            "pages":      r.get("imagecount") or "",
            "pdf_name":   pdf["name"] if pdf else "",
            "pdf_mb":     round(pdf["size"] / 1048576, 1) if pdf else 0.0,
            "title":      str(r.get("title") or "")[:140],
            "volume_inferred": 0,
        })
    rows.sort(key=lambda x: (x["volume"] or 9999, x["issue"] or 0, x["identifier"]))
    return rows


def choose(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Pick one source per volume; fall back to issue scans where needed."""
    content = [r for r in rows if not r["is_index"] and r["pdf_name"]]
    by_vol: dict[int | None, list[dict]] = collections.defaultdict(list)
    for r in content:
        by_vol[r["volume"]].append(r)

    manifest, notes = [], []
    for vol in sorted(v for v in by_vol if v is not None):
        cands = by_vol[vol]
        # A volume-level scan is one whose item covers the whole volume, i.e.
        # a volume-level family with no issue number attached.
        vol_level = [c for c in cands
                     if c["family"] in T.VOLUME_LEVEL and c["issue"] is None]
        if vol_level:
            vol_level.sort(key=lambda c: (T.FAMILY_RANK[c["family"]],
                                          -int(c["pages"] or 0)))
            best_fam = vol_level[0]["family"]
            # Some volumes were bound and scanned as two half-year parts. Keep
            # every part from the chosen family, not just the first.
            chosen = [c for c in vol_level if c["family"] == best_fam]
            for c in chosen:
                manifest.append({**c, "reason": f"volume scan ({best_fam})"})
            spare = len(cands) - len(chosen)
            if spare:
                fams = sorted({c["family"] for c in cands} - {best_fam})
                notes.append(f"vol {vol}: took {len(chosen)} {best_fam} scan(s); "
                             f"{spare} other cop{'y' if spare == 1 else 'ies'} "
                             f"available ({', '.join(fams)})")
        else:
            # No volume-level scan: assemble the volume from issue scans,
            # preferring the English per-issue run over the Tamil library.
            issues = [c for c in cands if c["family"] == "per-issue"]
            pool = issues or cands
            fam = pool[0]["family"] if not issues else "per-issue"
            for c in sorted(pool, key=lambda c: (c["issue"] or 0, c["identifier"])):
                manifest.append({**c, "reason": f"no volume scan; {fam} issue"})
            notes.append(f"vol {vol}: assembled from {len(pool)} {fam} item(s)")

    for r in by_vol.get(None, []):
        manifest.append({**r, "reason": "volume unresolved - needs manual check"})
        notes.append(f"UNRESOLVED {r['identifier']}: {r['title'][:70]}")

    return manifest, notes


def local_holdings(path: Path | None) -> set[str]:
    """Identifiers we already hold locally, from a file listing of the E: drive."""
    if not path or not path.exists():
        return set()
    found = set()
    for line in path.read_text(errors="replace").splitlines():
        for m in re.finditer(r"(tropicalagricul\w+|lbg\.[\w.]+|"
                             r"tropical-agriculturist_[\w-]+|"
                             r"\d{4,6}-The[\w\s\-()]+)", line):
            found.add(m.group(1).rstrip("._-"))
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local-holdings", type=Path,
                    default=T.INV / "e_all_tropical.txt",
                    help="file listing of already-downloaded copies (E: drive)")
    ap.add_argument("--blocked", type=Path, default=T.INV / "blocked.txt",
                    help="identifiers that cannot be fetched, one per line")
    args = ap.parse_args()

    # Some IA items are lending-only and answer 401 to a plain download: three
    # lbg volume scans did (volumes 58, 65, 71). Dropping them here rather
    # than in the downloader means selection falls through to the next-best
    # copy of the same volume -- a dli scan, or the per-issue run -- instead of
    # the volume silently going missing. Re-run this script then 03_download.py
    # and only the substitutes are fetched.
    blocked = set()
    if args.blocked.exists():
        blocked = {l.strip() for l in args.blocked.read_text().splitlines()
                   if l.strip() and not l.startswith("#")}

    recs, errors = T.load_meta()
    if errors:
        print(f"WARNING: {len(errors)} items have metadata errors and were "
              f"skipped; re-run 01_enumerate.py to retry them", file=sys.stderr)

    if blocked:
        before = len(recs)
        recs = [r for r in recs if r["identifier"] not in blocked]
        print(f"excluded {before - len(recs)} blocked item(s) "
              f"listed in {args.blocked.name}")

    rows = build_rows(recs)
    inferred = infer_missing_volumes(rows)
    rows.sort(key=lambda x: (x["volume"] or 9999, x["issue"] or 0, x["identifier"]))
    manifest, notes = choose(rows)
    have = local_holdings(args.local_holdings)

    for m in manifest:
        m["held_locally"] = int(any(m["identifier"] in h or h in m["identifier"]
                                    for h in have))

    with (T.INV / "ta_items.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    with (T.INV / "ta_manifest.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0]))
        w.writeheader(); w.writerows(manifest)

    # ---------------- report ----------------
    suspect = volume_year_outliers(rows)
    vols = sorted({m["volume"] for m in manifest if m["volume"]})
    gaps = [v for v in range(min(vols), max(vols) + 1) if v not in set(vols)]
    total_mb = sum(m["pdf_mb"] for m in manifest)
    total_pages = sum(int(m["pages"] or 0) for m in manifest)
    held = sum(m["held_locally"] for m in manifest)
    fam_counts = collections.Counter(m["family"] for m in manifest)

    out = [
        "The Tropical Agriculturist - Internet Archive coverage",
        "=" * 62,
        f"IA items examined        : {len(rows)}",
        f"  index-only (skipped)   : {sum(r['is_index'] for r in rows)}",
        f"  no usable PDF          : {sum(1 for r in rows if not r['pdf_name'])}",
        f"  volume inferred by date: {inferred}",
        "",
        f"Download set             : {len(manifest)} files, {total_mb/1024:.1f} GB",
        f"  already held on E:     : {held}",
        f"  to fetch               : {len(manifest) - held}",
        f"Pages (IA imagecount)    : {total_pages:,}",
        f"By digitisation family   : {dict(fam_counts)}",
        "",
        f"Volumes covered          : {len(vols)}  (vol {min(vols)} - vol {max(vols)})",
        f"Gaps in that range       : {len(gaps)}" + (f"  -> {gaps}" if gaps else ""),
        "",
        "Per-volume detail",
        "-" * 62,
    ]
    for v in vols:
        picked = [m for m in manifest if m["volume"] == v]
        pages = sum(int(p["pages"] or 0) for p in picked)
        yr = next((p["year"] for p in picked if p["year"]), "?")
        out.append(f"  vol {v:>3} ({yr})  {len(picked):>2} file(s)  {pages:>5} pp  "
                   f"[{picked[0]['family']}]"
                   + ("  (held)" if all(p["held_locally"] for p in picked) else ""))
    if suspect:
        out += ["", "Volume/year outliers (check these by hand)", "-" * 62]
        for s_ in suspect:
            out.append(f"  {s_['identifier'][:52]:52s} vol {s_['volume']:>3} "
                       f"year {s_['year']} (trend says ~{s_['predicted_year']})")
    out += ["", "Notes", "-" * 62] + ["  " + n for n in notes]

    (T.INV / "coverage.txt").write_text("\n".join(out) + "\n")
    print("\n".join(out[:22]))
    print(f"\n-> inventory/ta_items.csv, ta_manifest.csv, coverage.txt")


if __name__ == "__main__":
    main()
