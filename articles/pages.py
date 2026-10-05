#!/usr/bin/env python3
"""
Page layer for the Tropical Agriculturist corpus (output_v6).

One row per scan page of every document: where its text sits in the .md, what
the running head says (printed folio, issue date, running title), and the
Internet Archive URLs of the page image. Articles are built on top of this, so
every article can cite exact pages and link to their images.

Scan page i of a document = Chandra page i = PDF page i = IA BookReader leaf
"n<i>" (checked by eye on tropicalagricul321909ceyl n30: head "JANUARY, 1909.]
15 Dyes and Tans." in both). Other identifier families are checked separately.

Folios. A folio read from the head is trusted ("read") only when a nearby page
(within NEAR scan pages) gives the same offset folio - scan_page; a lone
reading is not enough, since body lines also start with numbers. A page with
no trusted folio gets one by interpolation ("inferred") only if the trusted
pages either side share one offset -- i.e. the folios between them run on with
no gap. Plates are unnumbered leaves that shift the offset, so where the
offset changes across a gap we cannot tell which leaf is the plate and leave
the folio blank rather than guess. A head reading that disagrees with the
trusted folios either side is kept in folio_raw and overruled ("corrected").

Usage: pages.py [OUTPUT_V6] > pages.tsv   (summary per document on stderr)
"""
import csv, json, pathlib, re, sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path.home() / "tropical/output_v6")
TAG_IDENT = pathlib.Path.home() / "tropical/inventory/tag_ident.tsv"
NEAR = 4

MARK = re.compile(r"\n\n(\d+)-{40,}\n\n")
MONTHS = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6, "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12,
}
MON = r"(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")"
DATE = re.compile(rf"\b({MON})\.?\s*(\d{{1,2}})?(?:st|nd|rd|th)?\s*[,.]?\s*(1[89]\d\d)\b", re.I)
JOURNAL = r"(?:THE\s+)?TROPICAL\s+AGRICULTURIST[.,]?"
# Heads, after stripping markdown. Date and journal title are optional parts.
#   recto: "NOVEMBER 1, 1883.]THE TROPICAL AGRICULTURIST.303"  "JANUARY, 1909.]15Dyes and Tans."
#   verso: "30.THE TROPICAL AGRICULTURIST.[NOVEMBER 1, 1883.]"  "140[AUGUST, 1915."
#   titled verso: "Dyes and Tans.16[JANUARY, 1909."    bare: "150"  "139RED LATERITIC EARTH"
RECTO = re.compile(rf"^(?P<date>{DATE.pattern})\s*\.?\s*\]\s*\.?\s*(?P<mid>[^\d\[\]]{{0,70}}?)\s*(?P<folio>\d{{1,4}})(?![\d,.]\d)(?P<rest>.*)$", re.I)
VERSO = re.compile(rf"^(?P<pre>[^\d\[\]]{{0,60}}?)(?P<folio>\d{{1,4}})\.?\s*(?P<mid>[^\d\[\]]{{0,70}}?)\s*\[\s*(?P<date>{DATE.pattern})\.?\]?(?P<rest>.*)$", re.I)
DATEONLY = re.compile(rf"^\[?(?P<date>{DATE.pattern})\.?\]?(?P<rest>.*)$", re.I)
BARE = re.compile(r"^\(?\s*(?P<folio>\d{1,4})(?![\d,.:/]|\s*\d)\s*\)?(?P<rest>.{0,60})$")
# running title then folio: "Plant Sanitation.178"
# running title with its own date, then folio: "and Magazine of the Ceylon Agricultural Society.—August, 1910.171"
TITLED_DATE = re.compile(rf"^(?P<pre>[^\d\[\]]{{2,90}}?)[—–-]\s*(?P<date>{DATE.pattern})\s*[.,]?\s*(?P<folio>\d{{1,4}})?$", re.I)
TITLED = re.compile(r"^(?P<pre>[A-Za-z][^\d\[\]]{2,60}?)[.,]?\s*(?P<folio>\d{1,4})$")
CLEAN = re.compile(r"^[#*_>\s|]+|[*_\s|]+$")
COMMENT = re.compile(r"<!--.*?-->", re.S)
IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def split_pages(text):
    """Page texts and their (start, end) character offsets in the .md."""
    ms = list(MARK.finditer(text))
    if [int(m.group(1)) for m in ms] != list(range(1, len(ms) + 1)):
        raise ValueError("page markers out of sequence")
    bounds = [0] + [x for m in ms for x in (m.start(), m.end())] + [len(text)]
    offs = list(zip(bounds[::2], bounds[1::2]))
    return [text[a:b] for a, b in offs], offs


def iso(m):
    mon = MONTHS[m.group(1).upper().rstrip(".")]
    day = m.group(2)
    return f"{int(m.group(3)):04d}-{mon:02d}" + (f"-{int(day):02d}" if day else "")


def parse_head(line):
    """(folio, date_iso, running_title, head_len) from the first line of a page."""
    s = CLEAN.sub("", line)
    for rx in (RECTO, VERSO):
        m = rx.match(s)
        if m:
            d = DATE.search(m.group("date"))
            mid = re.sub(r"(?:THE\s+)?TROPICAL\s+AGRICULTURIST[.,]?", "", m.group("mid"), flags=re.I).strip(" .,")
            title = ((m.groupdict().get("pre") or "").strip() or (m.group("mid").strip(" .,") if mid else "")
                     or m.group("rest").strip(" .[]"))
            return int(m.group("folio")), iso(d), title[:60], m.end("folio") if rx is RECTO else m.end("date")
    m = DATEONLY.match(s)
    if m and len(m.group("rest")) < 60:
        return None, iso(DATE.search(m.group("date"))), m.group("rest").strip(" .[]")[:60], m.end("date")
    m = TITLED_DATE.match(s)
    if m:
        f = int(m.group("folio")) if m.group("folio") else None
        return f, iso(DATE.search(m.group("date"))), m.group("pre").strip(" .[]")[:60], m.end()
    m = BARE.match(s)
    if m:
        return int(m.group("folio")), "", m.group("rest").strip(" .[]")[:60], m.end("folio")
    m = TITLED.match(s)
    if m:
        return int(m.group("folio")), "", m.group("pre").strip(" .[]")[:60], m.end("folio")
    return None, "", "", 0


def kind_of(p):
    body = COMMENT.sub("", p)
    if "stage4: FAINT" in p:
        return "faint"
    if "stage4: UNRESOLVED" in p or "[Page not transcribed" in p:
        return "untranscribed"
    words = re.findall(r"[A-Za-z]{2,}", IMG.sub("", body))
    if not words:
        return "image" if IMG.search(body) else "blank"
    if len(words) < 25 and IMG.search(body) and re.search(r"blank|no visible (text|content)", body, re.I):
        return "blank"
    return "text"


def repair(rows):
    """Fill folio/folio_status from folio_raw by offset agreement (see module doc)."""
    n = len(rows)
    off = [r["folio_raw"] - i if isinstance(r["folio_raw"], int) else None for i, r in enumerate(rows)]
    trusted = [False] * n
    for i in range(n):
        if off[i] is None:
            continue
        for j in range(max(0, i - NEAR), min(n, i + NEAR + 1)):
            if j != i and off[j] == off[i]:
                trusted[i] = True
                break
    anchors = [i for i in range(n) if trusted[i]]
    prev = [None] * n; nxt = [None] * n
    last = None
    for i in range(n):
        prev[i] = last
        if trusted[i]:
            last = i
    last = None
    for i in reversed(range(n)):
        nxt[i] = last
        if trusted[i]:
            last = i
    for i, r in enumerate(rows):
        if trusted[i]:
            r["folio"], r["folio_status"] = r["folio_raw"], "read"
            continue
        a, b = prev[i], nxt[i]
        if a is not None and b is not None and off[a] == off[b]:
            r["folio"] = i + off[a]
            r["folio_status"] = "corrected" if r["folio_raw"] != "" else "inferred"
        else:
            r["folio"], r["folio_status"] = "", ("unplaced" if r["folio_raw"] != "" else "none")
    return anchors


def main():
    ident = dict(l.rstrip("\n").split("\t") for l in open(TAG_IDENT))
    w = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    cols = ["doc", "page", "ia_id", "kind", "char_start", "char_end", "folio", "folio_status",
            "folio_raw", "date", "running_title", "head", "line1", "image_url", "viewer_url"]
    w.writerow(cols)
    for d in sorted(ROOT.glob("vol*")):
        md = next(d.glob("*/*.md"))
        meta = json.load(open(next(d.glob("*/*_metadata.json"))))
        text = md.read_text(encoding="utf-8", errors="replace")
        pages, offs = split_pages(text)
        assert len(pages) == meta["num_pages"], d.name
        ia = ident.get(d.name) or ident[d.name[:60]]
        rows = []
        for i, p in enumerate(pages):
            lines = [l for l in COMMENT.sub("", p).split("\n") if l.strip() and not IMG.fullmatch(l.strip())]
            folio, date, title, hl = parse_head(lines[0]) if lines else (None, "", "", 0)
            rows.append({
                "doc": d.name, "page": i, "ia_id": ia, "kind": kind_of(p),
                "char_start": offs[i][0], "char_end": offs[i][1],
                "folio": "", "folio_status": "", "folio_raw": folio if folio is not None else "",
                "date": date, "running_title": title,
                "head": CLEAN.sub("", lines[0])[:hl] if hl else "",
                "line1": re.sub(r"\s+", " ", lines[0])[:120] if lines else "",
                "image_url": f"https://archive.org/download/{ia}/page/n{i}.jpg",
                "viewer_url": f"https://archive.org/details/{ia}/page/n{i}/mode/1up",
            })
        repair(rows)
        for r in rows:
            w.writerow([r[c] for c in cols])
        txt = [r for r in rows if r["kind"] == "text"]
        st = lambda s: sum(r["folio_status"] == s for r in txt)
        print(f"{d.name[:44]:44} {len(rows):5} text {len(txt):5}  read {st('read')/max(1,len(txt)):4.0%}"
              f" inf {st('inferred'):3} corr {st('corrected'):3} unpl {st('unplaced'):3} none {st('none'):4}"
              f"  dated {sum(bool(r['date']) for r in txt)/max(1,len(txt)):4.0%}", file=sys.stderr)


if __name__ == "__main__":
    main()
