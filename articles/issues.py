#!/usr/bin/env python3
"""
Issue layer: assign every scan page a volume, an issue (year-month) and a part.

Parts: main (the journal proper), supplement ("Supplement to the Tropical
Agriculturist", which carries the Agricultural Magazine and Literary Register in
the 1890s-1900s), sales (Produce Sales Lists, tea sales reports, "Supplement to
CEYLON OBSERVER"), advert, index, front (title leaves, library stamps, blanks
before the first issue).

Evidence, strongest first:
  * per-issue documents: volume and issue come from the identifier/tag;
  * running-head dates (most bound volumes 1881-1925): the page's own month;
  * issue mastheads ("Vol. IX.] COLOMBO, MAY 1st, 1890. No. 11."): for heads
    without a date (1906-07; DLI 1928+), an issue runs from its masthead to
    the next one;
  * second-volume mastheads inside a DLI PDF switch the volume number.
Part cues come from the page's first line; pages without a cue take the label
of the folio run they sit in (constant folio - scan offset), else of the
nearest cued neighbours when both sides agree.

Usage: issues.py  (reads pages.tsv, writes page_issue.tsv and issues.tsv)
"""
import csv, collections, re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mastheads import scan as scan_mastheads, VOL, rom
from issue_tables import tables as issue_tables
from pages import split_pages

ROOT = pathlib.Path.home() / "tropical/output_v6"
MON3 = "jan feb mar apr may jun jul aug sep oct nov dec".split()
TITLE = re.compile(r"Vol(?:ume)?\.?\s*([LXVIC]{2,8})\b.{0,160}?(?:Containing\s+Num|(?:January|July)\s*(?:—|-|–|to))", re.I | re.S)


def vol_month(v, no):
    """From vol 26 (1906): vol V = year 1893 + V//2, Jan-Jun if V even else Jul-Dec; No. k = k-th month.
    Returns (year, month) -- the volume's first month when no is None. Checked against head dates in check_rule()."""
    if v < 26 or v > 101 or (no is not None and not 1 <= no <= 6):
        return None
    return 1893 + v // 2, (1 if v % 2 == 0 else 7) + ((no or 1) - 1)


def vol_span(v):
    """(first, last) 'YYYY-MM' of volume v, or None. To vol 23 one volume a year, July-June
    (vol 1 began June 1881); from vol 26 the half-year rule in vol_month()."""
    if 1 <= v <= 23:
        return f"{1880 + v}-{6 if v == 1 else 7:02d}", f"{1881 + v}-06"
    s = vol_month(v, None)
    return (f"{s[0]}-{s[1]:02d}", f"{s[0]}-{s[1] + 5:02d}") if s else None


def fix_year(d, v):
    """A head date outside its volume's span is an OCR misread of the year (1906 for 1900,
    1837 for 1887): keep the month and take the year that puts it inside the span, else drop."""
    sp = vol_span(v)
    if not d or not sp or sp[0] <= d <= sp[1]:
        return d, False
    for y in range(int(sp[0][:4]), int(sp[1][:4]) + 1):
        c = f"{y}-{d[5:7]}"
        if sp[0] <= c <= sp[1]:
            return c, True
    return None, True


def title_pages(doc):
    md = next((ROOT / doc).glob("*/*.md"))
    ps, _ = split_pages(md.read_text(encoding="utf-8", errors="replace"))
    out = []
    for i, p in enumerate(ps):
        m = TITLE.search(p[:900])
        if m:
            out.append((i, rom(m.group(1))))
    return out

CUES = [  # (part, regex on line1); first match wins
    ("sales", re.compile(r"SALES?\s+LIST|PRODUCE\s+SALES|TEA.{0,40}SALES|Supplement\s+to\s+.?CEYLON\s+OBSERVER|AVERAGES?\s+(FOR|OF)\s+(TEA|COFFEE)"
                         # bound-in tea brokers' reports (Gow, Wilson & Stanton) and their continuation tables
                         r"|WILSON\s*&\s*\w*TON|TEA\s+REPORT"
                         r"|^\W*(INDIAN|CEYLON|JAVA)\W*(?:[-—–]+\s*Continued\b|\s+Average\b|\s+\d+\s+chests)|^\W*(INDIAN|CEYLON|JAVA)\.?\W*$", re.I)),
    # 1908-13 the Supplement's head spans the spread: "The Supplement to the Tropical Agriculturist"
    # (verso) | "and Magazine of the Ceylon Agricultural Society." (recto) -- both halves are Supplement.
    ("supplement", re.compile(r"Supplement\s+to\s+the|AGRICULTURAL\s+MAGAZINE|LITERARY\s+REGISTER|^\W*and\s+Magazine\s+of\s+the\s+Ceylon\s+Agri", re.I)),
    ("advert", re.compile(r"^\W*ADVERTISE", re.I)),
    ("index", re.compile(r"^\W*(GENERAL\s+)?INDEX\b|^\W*CONTENTS\b", re.I)),
    ("main", re.compile(r"TROPICAL\s+AGRICULTURIST", re.I)),
]
MONTHNAMES = "january february march april may june july august september october november december".split()


def tag_info(doc):
    """(volume, issue_key, issue_no) for per-issue documents, else (volume, None, None)."""
    vol = int(doc[3:6])
    q = re.search(r"tropical-agriculturist-([a-z]+)-([a-z]+)-(\d{4})", doc)   # quarterly / combined
    if q and q.group(1) in MONTHNAMES and q.group(2) in MONTHNAMES:
        a, b = MONTHNAMES.index(q.group(1)) + 1, MONTHNAMES.index(q.group(2)) + 1
        n = re.search(r"_iss(\d\d)_", doc)
        return vol, f"{q.group(3)}-{a:02d}/{b:02d}", int(n.group(1)) if n else None
    m = re.search(r"_iss(\d\d)_.*?(\d{4})-(\d\d)", doc) or re.search(r"tropical-agriculturist-(\d{4})-(\d\d)", doc)
    if m and "_iss" in doc:
        return vol, f"{m.group(2)}-{m.group(3)}", int(m.group(1))
    if m:
        return vol, f"{m.group(1)}-{m.group(2)}", None
    m = re.search(r"tropical-agriculturist-([a-z]+)-([a-z]+)-(\d{4})", doc)   # quarterly / combined
    if m and m.group(1) in MONTHNAMES:
        a, b = MONTHNAMES.index(m.group(1)) + 1, MONTHNAMES.index(m.group(2)) + 1
        n = re.search(r"_iss(\d\d)_", doc)
        return vol, f"{m.group(3)}-{a:02d}/{b:02d}", int(n.group(1)) if n else None
    return vol, None, None


def runs(rows):
    """Folio-run id per page: consecutive text pages sharing folio - page offset."""
    rid, cur, last_off = [None] * len(rows), -1, None
    for i, r in enumerate(rows):
        if r["folio"] == "":
            continue
        off = int(r["folio"]) - i
        if off != last_off:
            cur += 1; last_off = off
        rid[i] = cur
    return rid


def label_parts(rows):
    cue = []
    for r in rows:
        lab = None
        if r["kind"] != "text":
            lab = None
        else:
            for part, rx in CUES:
                if rx.search(r["line1"]):
                    lab = part; break
            if lab is None and r["date"] and r["head"]:
                lab = "main"            # a dated running head without "Supplement" is the journal proper
        cue.append(lab)
    # A bare "INDIAN." / "CEYLON." line is a tea-report table only near a definite tea-report cue
    # (a 1938 map page is headed "# CEYLON").
    BARE_SALES = re.compile(r"^\W*(INDIAN|CEYLON|JAVA)\.?\W*$", re.I)
    firm = [i for i, r in enumerate(rows) if cue[i] == "sales" and not BARE_SALES.search(r["line1"])]
    for i, r in enumerate(rows):
        if cue[i] == "sales" and BARE_SALES.search(r["line1"]) and not any(abs(i - j) <= 15 for j in firm):
            cue[i] = None
    rid = runs(rows)
    vote = collections.defaultdict(collections.Counter)
    for i, c in enumerate(cue):
        if c and rid[i] is not None:
            vote[rid[i]][c] += 1
    part = []
    for i, r in enumerate(rows):
        if cue[i]:
            part.append((cue[i], "cue")); continue
        # Nearest cues first: the Supplement is sometimes paginated continuously with the
        # journal (1909), so a folio run can span both parts.
        a = next((cue[j] for j in range(i - 1, max(-1, i - 11), -1) if cue[j]), None)
        b = next((cue[j] for j in range(i + 1, min(len(rows), i + 11)) if cue[j]), None)
        if a and a == b:
            part.append((a, "neighbours")); continue
        if rid[i] is not None and vote[rid[i]]:
            part.append((vote[rid[i]].most_common(1)[0][0], "run"))
        else:
            part.append(("main", "default") if r["kind"] == "text" else (r["kind"], "kind"))
    return part


def main():
    allrows = list(csv.DictReader(open("pages.tsv"), delimiter="\t"))
    bydoc = collections.defaultdict(list)
    for r in allrows:
        bydoc[r["doc"]].append(r)
    out = csv.writer(open("page_issue.tsv", "w"), delimiter="\t", lineterminator="\n")
    out.writerow(["doc", "page", "volume", "issue", "issue_no", "part", "part_src", "issue_src"])
    summary = collections.OrderedDict()
    for doc, rows in bydoc.items():
        vol, key, no = tag_info(doc)
        parts = label_parts(rows)
        n = len(rows)
        vols, issues, nos, src = [vol] * n, [key] * n, [no] * n, ["tag" if key else ""] * n
        if key is None:
            # Mastheads: keep volume numbers that recur (>=3) -- citations of other journals don't.
            mh = scan_mastheads(doc)
            vc = collections.Counter(v for _, v, _, _ in mh)
            good = {v for v, c in vc.items() if c >= 3}
            # Trust the identifier's volume unless the mastheads name a HIGHER one (vol046 lbg is
            # really vol 56). Lower numbers are the bound-in Agricultural Magazine's own volumes.
            higher = [v for v in good if v > vol + 1]
            base = vol if vol in good or not higher else max(higher, key=lambda v: vc[v])
            # Only this volume and the next count; other serials bound in (the Supplement,
            # Agricultural Magazine) carry their own volume numbers.
            mh = [h for h in mh if h[1] in (base, base + 1) and 1 <= h[2] <= 12]
            # A DLI/tdl PDF may hold two half-year volumes: split at the second one's
            # first masthead, issue table or title page.
            tabs = issue_tables(doc)
            titles = title_pages(doc)
            nxt = [(i, no_) for i, v, no_, _ in mh if v == base + 1]
            starts = [i for i, no_ in nxt if no_ == 1 and any(j > i and k == 2 for j, k in nxt)]
            starts += [i for i, v in titles if v == base + 1 and i > 0]
            # From vol 26 a head date fixes the volume: 5 dated pages in a row of base+1 start it.
            if vol_month(base, None):
                run = 0
                for i, r in enumerate(rows):
                    d = r["date"][:7]
                    if not d:
                        continue
                    y, mo = int(d[:4]), int(d[5:7])
                    run = run + 1 if (y - 1893) * 2 + (mo >= 7) == base + 1 else 0
                    if run == 5:
                        starts.append(next(j for j in range(i, -1, -1) if j == 0 or
                                           not rows[j - 1]["date"] or (int(rows[j - 1]["date"][:4]) - 1893) * 2 + (int(rows[j - 1]["date"][5:7]) >= 7) != base + 1 and rows[j]["date"]))
                        break
            if len(tabs) == 2:
                starts.append(tabs[1][0])
            elif len(tabs) == 1 and tabs[0][1][0][0] == "jul" and base % 2 == 0:
                starts.append(tabs[0][0])
            split = min(starts) if starts else n
            vol_at = lambda i: base if i < split else base + 1
            table_for = {}
            for ti, trows in tabs:
                jan = trows[0][0] in ("jan", "feb", "mar")
                table_for[base if (base % 2 == 0) == jan else base + 1] = trows
            # Head dates: month of each page, smoothed by the modal month of +-3 dated pages.
            # From vol 26 a page's own head date fixes its volume (DLI copies bind some June pages
            # after the next volume's index); then misread years are repaired against that volume.
            def page_vol(i, r):
                d = r["date"][:7]
                if d and vol_month(base, None):
                    v = (int(d[:4]) - 1893) * 2 + (int(d[5:7]) >= 7)
                    if v in (base, base + 1):
                        return v
                return vol_at(i)
            pvol = [page_vol(i, r) for i, r in enumerate(rows)]
            months = [fix_year(r["date"][:7], pvol[i])[0] if r["date"] else None for i, r in enumerate(rows)]
            sm = [None] * n
            for i in range(n):
                win = [m for m in months[max(0, i - 3):i + 4] if m]
                if months[i] and win:
                    mc = collections.Counter(win).most_common(1)[0]
                    sm[i] = months[i] if months[i] == mc[0] or mc[1] < 3 else mc[0]
            # Covers bound together in a cluster (vol096 p487-497: six issues' covers in 10 pages)
            # say nothing about where each issue's pages are: drop them from propagation.
            pos = [h[0] for h in mh]
            clustered = {pos[k] for k in range(len(pos)) for j in range(len(pos))
                         if j != k and abs(pos[j] - pos[k]) < 12}
            mh = [h for h in mh if h[0] not in clustered]
            cur = None; mh_at = {i: (v, no_, d) for i, v, no_, d in mh}
            for i in range(n):
                if i in mh_at and mh_at[i][0] == vol_at(i):
                    cur = mh_at[i]
                v = vols[i] = pvol[i]
                nos[i] = cur[1] if cur else None
                f = rows[i]["folio"]
                tmon = None
                if f and v in table_for and rows[i]["folio_status"] != "unplaced":
                    hit = [m for m, a, b in table_for[v] if a <= int(f) <= b]
                    tmon = hit[0] if len(hit) == 1 else None
                if sm[i]:
                    issues[i], src[i] = sm[i], "head"
                elif tmon and vol_month(v, None):
                    issues[i], src[i] = f"{vol_month(v, None)[0]}-{MON3.index(tmon) + 1:02d}", "table"
                elif cur and cur[2] and fix_year(cur[2][:7], v)[0]:
                    issues[i], src[i] = fix_year(cur[2][:7], v)[0], "masthead"
                elif cur and vol_month(v, cur[1]):
                    y, m = vol_month(v, cur[1]); issues[i], src[i] = f"{y}-{m:02d}", "masthead+rule"
            # Fill remaining gaps inside an issue: same masthead number before and after -> same issue.
            last = None
            for i in range(n):
                if issues[i]:
                    last = (issues[i], nos[i])
                elif last and nos[i] == last[1] and nos[i] is not None:
                    issues[i], src[i] = last[0], "fill"
            # A masthead page opens an issue: it takes the issue of the strong evidence after it.
            mh_pages = {h[0] for h in mh}
            for i in mh_pages:
                if src[i] not in ("head", "table"):
                    j = next((j for j in range(i + 1, min(n, i + 9)) if src[j] in ("head", "table")), None)
                    if j is not None:
                        issues[i], vols[i], src[i] = issues[j], vols[j], "masthead-next"
            # Weak labels (masthead/rule/fill) yield to strong neighbours (head/table) that agree.
            strong = [issues[i] if src[i] in ("head", "table") else None for i in range(n)]
            for i in range(n):
                if src[i] in ("masthead", "masthead+rule", "fill", ""):
                    a = next((strong[j] for j in range(i - 1, max(-1, i - 9), -1) if strong[j]), None)
                    b = next((strong[j] for j in range(i + 1, min(n, i + 9)) if strong[j]), None)
                    if a and a == b and a != issues[i]:
                        issues[i], src[i] = a, "between"
            # Still unplaced: at least the half-year volume (from vol 26 on, the numbering rule).
            for i in range(n):
                if not issues[i] and vol_month(vols[i], None):
                    y, m = vol_month(vols[i], None)
                    issues[i], src[i] = f"{y}-{m:02d}/{m + 5:02d}", "volume"
        for i, r in enumerate(rows):
            p, ps = parts[i]
            out.writerow([doc, i, vols[i], issues[i] or "", nos[i] or "", p, ps, src[i]])
            if issues[i] and p in ("main", "supplement", "sales"):
                s = summary.setdefault((vols[i], issues[i]), {"docs": collections.Counter(), "pages": 0, "parts": collections.Counter()})
                s["docs"][doc] += 1; s["pages"] += 1; s["parts"][p] += 1
    w = csv.writer(open("issues.tsv", "w"), delimiter="\t", lineterminator="\n")
    w.writerow(["volume", "issue", "pages", "main", "supplement", "sales", "docs"])
    for (v, k), s in sorted(summary.items()):
        w.writerow([v, k, s["pages"], s["parts"]["main"], s["parts"]["supplement"], s["parts"]["sales"],
                    ";".join(f"{d}:{c}" for d, c in s["docs"].most_common())])


if __name__ == "__main__":
    main()
