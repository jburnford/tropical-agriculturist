#!/usr/bin/env python3
"""
Find the split between two side-by-side tables from Tesseract word boxes.

Pages like the Produce Sales Lists, Market Rates and Ceylon Rainfall returns
print two copies of the same table side by side. Chandra reads them as one
wide table and pairs unrelated left and right records row by row. Whether the
two halves are divided by blank space or by a ruled line (Market Rates, where
the QUOTATIONS column abuts the rule and pixel-based gutter tests fail, see
vsplit.py), no WORD crosses the division. So:

  x   vertical line within 38-62% of the width crossed by the fewest body
      words (ties: nearest the centre)
  y0  bottom of the lowest crossing word in the top 18% of the page: the
      title, running head and any full-width heading sit above it and are
      kept as a full-width strip
  accept iff, below y0, <= 1% of words cross x, AND the two sides are the
      same table: >= 2 header words (alphabetic, >= 3 letters) shared between
      the top 30% of each side. A single wide table with a word-free column
      gap near the middle (vol012 p1228, the control) has different headings
      on each side and is refused -- splitting it would separate item names
      from their prices.

Usage: tsplit.py TESS_TSV [TESS_TSV ...]   prints one line per page
       tsplit.py --batch PAGE_TYPES TESSDIR LEAFDIR OUT_TSV
"""
import csv, re, sys


def words(tsv, with_line=False):
    out = []
    for r in csv.DictReader(open(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if r["level"] == "5" and r["text"].strip() and float(r["conf"]) >= 0:
            l, t, w, h = (int(r[k]) for k in ("left", "top", "width", "height"))
            out.append((l, t, l + w, t + h, r["text"]) +
                       ((r["block_num"], r["par_num"], r["line_num"]),) * with_line)
    return out


def heading_bottom(tsv, x, W, top_lim, gap=0.035):
    """Bottom of the lowest Tesseract line in the top band that runs across x
    with only a word space at x: a centred title whose words merely flank the
    division ("MARKET RATES FOR | TROPICAL PRODUCTS", vol032 p97) has no word
    crossing x, so the word test alone put the cut through it."""
    lines = {}
    for w in words(tsv, with_line=True):
        if w[1] < top_lim:
            lines.setdefault(w[5], []).append(w)
    y0 = 0
    for ws in lines.values():
        # a heading is short and mostly words; Tesseract sometimes joins a left
        # and right TABLE row into one line (vol015 p1043), and taking that as
        # a heading left the first rows of both tables interleaved
        alpha = sum(bool(re.search(r"[A-Za-z]{2}", w[4])) for w in ws)
        if len(ws) > 12 or alpha < 0.7 * len(ws):
            continue
        left = [w for w in ws if w[2] <= x]
        right = [w for w in ws if w[0] >= x]
        if left and right and min(w[0] for w in right) - max(w[2] for w in left) < W * gap:
            y0 = max(y0, max(w[3] for w in ws))
    return y0


def find(tsv, W=None, H=None, require_shared=True):
    ws = words(tsv)
    if not ws:
        return None, "no words"
    W = W or max(w[2] for w in ws)
    H = H or max(w[3] for w in ws)
    # full-width headings (running head, title, "From Lewis & Peat's ...",
    # "IMPORTED FROM ...") all sit in the top ~15%; at 40% a stray long word
    # mid-page left a third of some Market Rates pages unsplit
    top_lim = H * 0.18
    m = W * 0.008
    # a word only counts as crossing if it reaches well past x on both sides
    # and has >= 2 letters/digits: rule pixels read as "|" and short notes at
    # a column's edge ("bid", "10d") that just touch the line are noise and
    # pushed the full-width strip a third of the way down (vol011 p235)
    ws_x = [w for w in ws if len(re.sub(r"[^A-Za-z0-9]", "", w[4])) >= 2]
    best = None
    for x in range(round(W * 0.38), round(W * 0.62), max(1, W // 500)):
        cross = [w for w in ws_x if w[0] < x - m and w[2] > x + m]
        # only words with letters mark a heading: Tesseract merging two numbers
        # across the gutter ("1300 36410") is not one (vol015 p1043)
        y0 = max([w[3] for w in cross if w[1] < top_lim and re.search(r"[A-Za-z]{3}", w[4])], default=0)
        body = [w for w in ws if w[1] >= y0]
        bad = sum(1 for w in cross if w[1] >= y0)
        key = (bad / max(1, len(body)), abs(x - W / 2))
        if best is None or key < best[0]:
            best = (key, x, y0, bad, len(body))
    (frac, _), x, y0, bad, nbody = best
    if frac > 0.01:
        return None, f"no clean division: best x={x / W:.2f} crossed by {bad}/{nbody} words"
    y0 = max(y0, heading_bottom(tsv, x, W, top_lim))
    body_h = H - y0
    def head(side):
        return {re.sub(r"[^a-z]", "", w[4].lower()) for w in ws
                if w[1] >= y0 and w[1] < y0 + body_h * 0.30 and (w[2] <= x if side == "L" else w[0] >= x)
                and len(re.sub(r"[^a-z]", "", w[4].lower())) >= 3}
    common = head("L") & head("R")
    if require_shared and len(common) < 2:
        return None, f"halves differ: x={x / W:.2f} shared header words {sorted(common)}"
    return (x, y0), f"x={x / W:.2f} y0={y0 / H:.2f} crossing={bad} shared={sorted(common)[:8]}"


def batch(types_tsv, tessdir, leafdir, out_tsv):
    """Split geometry for every page typed as a side-by-side feature
    (repair/vsplit/page_types.tsv: tag, page, type; 'other' is skipped).
    The page type is the gate, so shared header words are only reported."""
    from PIL import Image
    n = ok = 0
    with open(out_tsv, "w") as fh:
        for l in open(types_tsv):
            tag, page, kind = l.rstrip("\n").split("\t")
            if kind == "other":
                continue
            n += 1
            tsv = f"{tessdir}/{tag}_p{int(page):04d}.tsv"
            W, H = Image.open(f"{leafdir}/{tag}/p{int(page):04d}.png").size
            g, why = find(tsv, W, H, require_shared=False)
            print(f"{'SPLIT' if g else '-'}\t{tag}\t{page}\t{kind}\t{why}")
            if g:
                ok += 1
                fh.write(f"{tag}\t{page}\t{g[0]}\t{g[1]}\t{kind}\n")
    print(f"# {ok}/{n} pages split", file=sys.stderr)


if __name__ == "__main__":
    if sys.argv[1] == "--batch":
        batch(*sys.argv[2:6])
        sys.exit()
    for f in sys.argv[1:]:
        g, why = find(f)
        print(f"{'SPLIT' if g else '-':5}\t{f.rsplit('/', 1)[-1]}\t{why}")
