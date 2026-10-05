#!/usr/bin/env python3
"""
Heading skeleton per issue: every line that might start an article, in reading order.

Candidates (outside tables, not the page's running head):
  * markdown headings (# .. ######)
  * short standalone ALL-CAPS lines (1880s titles are often plain caps lines)
  * short bold-only lines (**Capital in Agriculture.**)
Each carries its scan page, folio, part, the markup it came with, and the first
~160 characters of text that follows it, so a reader can tell a title from a
subhead or a table caption. Offsets are into the v6 .md, for exact provenance.

Unit = one issue of one document (doc, volume, issue). Pages in parts sales/advert/
index/front and pages with no issue are left out of the skeleton.

Writes skeleton.jsonl: one line per issue {unit, doc, volume, issue, cands:[...]}.
"""
import csv, json, re, sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
ROOT = pathlib.Path.home() / "tropical/output_v6"

MDH = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
BOLD = re.compile(r"^\*\*([^*]{3,120})\*\*\s*$")
# Run-in title: "INDIAN SOAPSTONE.—Steatite or soapstone is ..." (short notes, 1880s-1900s)
RUNIN = re.compile(r"^\**\s*([A-Z][A-Z0-9'’&,()\-. ]{3,90}?[A-Z)])\s*[.:,]?\s*\**\s*[—–]")
BOLDLEAD = re.compile(r"^\*\*([^*]{8,160})\*\*\s*\S")        # bold title opening a paragraph


def is_short(s):
    """Short standalone mixed-case line that could be a title ("Editorial.", "Kandy Flora")."""
    t = TAG.sub("", s).strip(" *_")
    w = t.split()
    if not 1 <= len(w) <= 12 or t.endswith((",", ";", ":")) or re.search(r"\d{3,}", t):
        return False
    caps = sum(x[0].isupper() for x in w if x[0].isalpha())
    return caps >= max(1, 0.6 * len([x for x in w if x[0].isalpha() and x.lower() not in SMALL]))


SMALL = set("of the and in on for to a an with by from at as or its".split())
IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
TAG = re.compile(r"<[^>]+>")
KEEP_PARTS = {"main", "supplement"}


def is_caps(s):
    t = TAG.sub("", s).strip(" *_#")
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", t)
    if not 1 <= len(words) <= 18 or len(t) > 140:
        return False
    letters = [c for c in t if c.isalpha()]
    return len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) > 0.85


def follow(lines, k, n=160):
    """First n chars of body text after line k (skipping blanks, images, other headings)."""
    buf = []
    for l in lines[k + 1:k + 12]:
        s = TAG.sub(" ", IMG.sub("", l)).strip()
        if not s or MDH.match(l):
            if buf:
                break
            continue
        buf.append(s)
        if sum(map(len, buf)) >= n:
            break
    return re.sub(r"\s+", " ", " ".join(buf))[:n]


def main():
    pages = {(r["doc"], int(r["page"])): r for r in csv.DictReader(open("pages.tsv"), delimiter="\t")}
    units = collections.OrderedDict()
    for r in csv.DictReader(open("page_issue.tsv"), delimiter="\t"):
        if r["issue"] and r["part"] in KEEP_PARTS:
            units.setdefault((r["doc"], r["volume"], r["issue"]), []).append((int(r["page"]), r["part"]))
    out = open("skeleton.jsonl", "w")
    texts = {}
    stats = collections.Counter()
    for (doc, vol, iss), plist in units.items():
        if doc not in texts:
            texts.clear()
            texts[doc] = next((ROOT / doc).glob("*/*.md")).read_text(encoding="utf-8", errors="replace")
        text = texts[doc]
        cands = []
        for pg, part in plist:
            pr = pages[(doc, pg)]
            a, b = int(pr["char_start"]), int(pr["char_end"])
            body = text[a:b]
            lines = body.split("\n")
            offs, o = [], a
            for l in lines:
                offs.append(o); o += len(l) + 1
            in_table = False
            first_content = True
            for k, l in enumerate(lines):
                s = l.strip()
                if "<table" in s:
                    in_table = True
                if in_table:
                    if "</table>" in s:
                        in_table = False
                    continue
                if not s or IMG.fullmatch(s) or s.startswith("<!--"):
                    continue
                if first_content:            # the running head line, if the page has one
                    first_content = False
                    if pr["head"] and s.replace("#", "").strip().startswith(pr["head"][:8]):
                        rest = re.sub(r"^[#*\s]+", "", s)[len(pr["head"]):].strip(" .*#[]")
                        # A title fused onto the head ("190DEPARTMENTAL NOTESCOTTON CULTIVATION").
                        # A running title ("Dyes and Tans.") repeats on nearby pages; a fused title doesn't.
                        near = {pages[(doc, q)]["running_title"][:20].lower() for q in range(pg - 4, pg + 5)
                                if q != pg and (doc, q) in pages}
                        if len(rest) >= 6 and rest[:20].lower() not in near or len(rest) > 60:
                            cands.append({"id": len(cands), "page": pg, "folio": pr["folio"], "part": part,
                                          "kind": "headrest", "text": rest[:200], "next": follow(lines, k),
                                          "offset": offs[k]})
                        continue
                m = MDH.match(s)
                if m:
                    kind, t = "h" + str(len(m.group(1))), m.group(2)
                elif BOLD.match(s):
                    kind, t = "bold", BOLD.match(s).group(1)
                elif is_caps(s):
                    kind, t = "caps", s
                elif RUNIN.match(s) and is_caps(RUNIN.match(s).group(1)):
                    kind, t = "runin", RUNIN.match(s).group(1)
                elif BOLDLEAD.match(s):
                    kind, t = "boldlead", BOLDLEAD.match(s).group(1)
                elif is_short(s) and (k == 0 or not lines[k - 1].strip()) and (k + 1 >= len(lines) or not lines[k + 1].strip()):
                    kind, t = "short", s
                else:
                    continue
                t = re.sub(r"\s+", " ", TAG.sub("", t)).strip()
                if not re.search(r"[A-Za-z]{2}", t):
                    continue
                nxt = follow(lines, k)
                if kind in ("runin", "boldlead"):    # the piece continues on the same line
                    m2 = (RUNIN if kind == "runin" else BOLDLEAD).match(s)
                    rest = re.sub(r"^[\s*.:,—–-]+", "", TAG.sub(" ", s[m2.end(1):]))
                    nxt = re.sub(r"\s+", " ", rest + " " + nxt)[:160]
                cands.append({"id": len(cands), "page": pg, "folio": pr["folio"], "part": part, "kind": kind,
                              "text": t[:200], "next": nxt, "offset": offs[k]})
        stats["units"] += 1; stats["cands"] += len(cands)
        out.write(json.dumps({"unit": f"{doc}|{vol}|{iss}", "doc": doc, "volume": vol, "issue": iss,
                              "pages": [p for p, _ in plist], "cands": cands}, ensure_ascii=False) + "\n")
    print(dict(stats), file=sys.stderr)


if __name__ == "__main__":
    main()
