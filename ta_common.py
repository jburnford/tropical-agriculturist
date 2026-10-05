#!/usr/bin/env python3
"""Shared helpers for the Tropical Agriculturist pipeline."""
from __future__ import annotations

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
INV = BASE / "inventory"

ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}

# Families of digitisation, best first. A volume-level scan is preferred over
# per-issue scans because it is one OCR job with continuous pagination; issue
# scans have to be stitched back together and often drop wrappers and adverts.
VOLUME_LEVEL = ("cornell", "lbg", "dli", "unse")
FAMILY_RANK = {"cornell": 0, "lbg": 1, "dli": 2, "unse": 3,
               "per-issue": 4, "tdl": 5, "other": 6}


def roman_to_int(s: str) -> int | None:
    s = s.lower()
    if not s or any(ch not in ROMAN for ch in s):
        return None
    total = prev = 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total or None


def family(ident: str) -> str:
    """Which digitisation project produced this item."""
    if ident.startswith("tdl."):
        return "tdl"
    if ident.startswith("tropical-agriculturist_"):
        return "per-issue"
    if ident.startswith("lbg."):
        return "lbg"
    if ident.startswith(("dli.ernet", "in.ernet.dli")):
        return "dli"
    if re.match(r"tropicalagricult\d{4}unse", ident):
        return "unse"
    if ident.startswith("tropicalagricul"):
        return "cornell"
    return "other"


def resolve_vol_issue(rec: dict) -> tuple[int | None, int | None]:
    """Best-effort (volume, issue) for an IA item. Either may be None.

    Every branch below exists because some slice of this corpus needs it; the
    order matters, most-authoritative first.
    """
    ident = rec["identifier"]
    title = str(rec.get("title") or "")
    vol = issue = None

    # 1. explicit `volume` metadata: either "44" or "v.15(1895-1896)"
    raw = rec.get("volume")
    if raw is not None:
        raw = str(raw).strip()
        if raw.isdigit():
            vol = int(raw)
        else:
            m = re.search(r"v\.?\s*(\d+)", raw, re.I)
            if m:
                vol = int(m.group(1))
            else:
                # The Colombo imprints carry a year range and no volume number
                # at all ("1884-1885"). Through the single-volume-a-year era
                # the series is exactly regular -- volume N spans
                # (1880+N)-(1881+N) -- which is corroborated by every Cornell
                # item, whose metadata gives both (e.g. "v.15(1895-1896)").
                # From 1913 the journal went to two volumes a year and the
                # arithmetic stops holding, so it is capped at 1912.
                m = re.match(r"(18\d\d)\s*-\s*(18\d\d|\d\d)$", raw)
                if m and int(m.group(1)) <= 1912:
                    vol = int(m.group(1)) - 1880

    # 2. per-issue identifiers: tropical-agriculturist_1915-06_44_6
    m = re.match(r"tropical-agriculturist_[a-z0-9-]+?_(\d{2,3})(?:_(\d+))?$", ident)
    if m:
        vol = vol or int(m.group(1))
        if m.group(2):
            issue = int(m.group(2))

    # 3. Numbers embedded in the identifier. These outrank the title: the
    #    scanning libraries number their own shelves reliably, whereas
    #    `lbg.630.5.tag.v.71` carries the title "Vol-VI" -- plainly wrong, and
    #    the identifier and its 1928 date both say 71.
    #
    #    Cornell/BHL use two colliding shapes:
    #      tropicalagricul{vv}{yyyy}ceyl -> vol vv  (...33 1909... = v.33)
    #      tropicalagricult{v}{yy}ceyl   -> vol v   (...21 19...   = v.21)
    if vol is None:
        m = re.match(r"tropicalagricul(\d{2})(\d{4})ceyl", ident)
        if m:
            vol = int(m.group(1))
    if vol is None:
        m = re.match(r"tropicalagricult(\d{1,2})(\d{2})ceyl$", ident)
        if m:
            vol = int(m.group(1))
    if vol is None:
        m = re.search(r"tag\.v\.(\d+)", ident)
        if m:
            vol = int(m.group(1))
    if vol is None:
        # The `unse` bucket mixes genuine volume scans ("Tropical Agriculturist
        # 1920: Vol 54") with CABI offprints that merely share the identifier
        # shape ("Bacterial wilt of bananas", tropicalagricult0038unse). Only
        # trust the number when the title agrees that this is the journal.
        m = re.search(r"tropicalagricult(\d{4})unse", ident)
        if m and re.search(r"tropical\s+agricultur", title, re.I):
            vol = int(m.group(1))
    if vol is None:
        m = re.search(r"tropicalagricultvol-([ivxlcdm]+)\.", ident, re.I)
        if m:
            vol = roman_to_int(m.group(1))
    if vol is None or issue is None:
        m = re.match(r"tropicalagri(\d{4})book(\d+)issue(\d+)", ident)
        if m:
            vol = vol or int(m.group(2))
            issue = issue or int(m.group(3))

    # 4. roman numeral in the title: "Vol-xli", "Vol LXIII". Last resort for
    #    the dli.ernet items, whose identifiers are opaque accession numbers.
    if vol is None:
        m = re.search(r"vol[\s.\-_]*([ivxlcdm]+)\b", title, re.I)
        if m:
            vol = roman_to_int(m.group(1))

    # 5. Tamil Digital Library: vol/issue live in the FILENAME only.
    if vol is None or issue is None:
        for f in rec.get("files", []):
            m = re.search(r"_Vol[_\s]*(\d+)(?:[_\s]*no[_\s]*(\d+))?", f["name"], re.I)
            if m:
                vol = vol or int(m.group(1))
                if issue is None and m.group(2):
                    issue = int(m.group(2))
                break

    # The journal ran to about volume 120. Anything outside that is a parsing
    # artefact, not a volume: `tropicalagricult0000unse_d3r6` would otherwise
    # resolve to volume 0 via the "unse" rule.
    if vol is not None and not (1 <= vol <= 130):
        vol = None
    return vol, issue


def best_pdf(rec: dict) -> dict | None:
    """The PDF best suited to VLM OCR.

    Prefer the colour/greyscale "Text PDF" over the bitonal `_bw` variant:
    bitonal thresholding destroys the halftone plates and the faint 1880s
    type that Chandra otherwise reads. Largest wins a tie.
    """
    pdfs = [f for f in rec.get("files", [])
            if f["name"].lower().endswith(".pdf") and f["size"] > 1_000_000]
    if not pdfs:
        return None
    return sorted(pdfs, key=lambda f: (f["name"].lower().endswith("_bw.pdf"),
                                       -f["size"]))[0]


def is_index_only(rec: dict) -> bool:
    """Index/contents items carry no article text worth OCR'ing in bulk."""
    ident = rec["identifier"].lower()
    title = str(rec.get("title") or "")
    return ident.endswith("_index") or bool(re.search(r"\bindex\b", title, re.I))


def load_meta(path: Path | None = None) -> list[dict]:
    """Read ia_meta.jsonl, dropping error records and the Nature review."""
    path = path or (INV / "ia_meta.jsonl")
    out, errors = [], []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if "error" in rec:
            errors.append(rec["identifier"])
            continue
        # A 2-page Nature review *about* the journal, not an issue of it.
        if rec["identifier"].startswith("paper-doi"):
            continue
        if not is_the_journal(rec):
            continue
        out.append(rec)
    return out, errors

# Works that share the title but are not the Ceylon journal. The journal began
# in June 1881; anything substantially earlier is a different book. The 1833
# "portgoog" item is G. R. Porter's practical treatise on sugar cane.
NOT_THE_JOURNAL = (
    # G. R. Porter, "The Tropical Agriculturist: a practical treatise on the
    # cultivation of the sugar cane" (1833). A book, not the journal.
    "tropicalagricul01portgoog",
    # A CABI offprint filed under a journal-shaped identifier. Its title gives
    # it away, but nothing else does: it carries no volume metadata, so the
    # identifier rule alone would read it as volume 38.
    "tropicalagricult0038unse",
)


def is_the_journal(rec: dict) -> bool:
    """False for works that share the name but are not the Ceylon journal.

    Three distinct kinds of impostor turn up in an identifier-prefix search:

      * Pre-1881 books. The journal began in June 1881; `tropicalagricul01portgoog`
        (1833) is G. R. Porter's treatise on sugar cane.
      * *Tropical Agriculture*, the journal of the Imperial College of Tropical
        Agriculture in Trinidad. Different journal, confusingly similar title,
        and its own volume numbering -- its vol 37 is 1960, whereas this
        journal's vol 37 is 1911. Left in, it would contend for volumes it has
        no claim to.
      * `tropicalagricult0000*`, a catch-all bucket into which IA filed
        assorted CABI offprints ("Bacterial wilt of bananas history and known
        distribution") and later textbooks.

    Note that collection membership is *not* a usable filter here: CABI
    digitised the genuine per-issue run, so `cabi` contains both 237 real
    issues and the offprints above.
    """
    ident = rec["identifier"]
    if ident in NOT_THE_JOURNAL:
        return False
    if re.match(r"tropicalagricult0000", ident):
        return False

    title = str(rec.get("title") or "").strip().lower()
    # "tropical agriculture ..." but not "tropical agriculturist ..."
    if re.match(r"tropical agriculture\b", title):
        return False

    m = re.search(r"\b(1[78]\d\d)\b", str(rec.get("year") or rec.get("date") or ""))
    if m and int(m.group(1)) < 1881:
        return False
    return True
