#!/usr/bin/env python3
"""
Side-by-side column split for two-column table pages (variant V).

Chandra reads the bound-in Produce Sales Lists, Market Rates and tea-sales
pages -- printed as two independent tables side by side -- as ONE wide table,
so each row pairs an unrelated left record with a right one (vol021 p1175:
lot 256 next to lot 410). Cutting the leaf at the gutter and reading the left
column before the right gives each table its own rows.

gutter(im) -> (x, y0) or None
  x   centre of the clearest vertical band (2.5% of the width) within +-12% of
      the page centre, measured over the lower 85% of the page; a row counts
      as clear with <= 2 inked pixels (at 600 px width) across the band, which
      admits a thin rule between the tables but not title lettering
  y0  first row from which that band stays clear to the bottom (allowing
      short inked gaps: a stray mark or a folio dot); everything above y0
      -- running head, page title, any full-width heading -- is kept whole
  None unless the band is clear on >= 90% of rows below y0 and y0 sits in the
      top 40% of the page: no gutter, no split. A wrong split would separate
      item names from their prices on single wide tables, so this is strict.

pieces(im) -> [top, L1, L2, R1, R2]  (top omitted if < 2% of the height)
  each column cut once more at its lightest row near the middle, since
  quarter-page pieces are what made dense tables transcribe (T, H variants)

Usage (check):  vsplit.py LEAF.png [OUT_PREFIX]   prints the gutter, saves a
                preview with the cuts drawn if OUT_PREFIX is given
"""
import sys

from PIL import Image, ImageDraw


def _ink(im):
    """Downsampled darkness map: list of rows, each a list of 0-255 ink values."""
    g = im.convert("L")
    w = 600
    h = round(g.height * w / g.width)
    g = g.resize((w, h))
    px = g.load()
    return w, h, [[255 - px[x, y] for x in range(w)] for y in range(h)]


def gutter(im, band_frac=0.025, clear=60, rule_px=2, need=0.90):
    w, h, ink = _ink(im)
    bw = max(4, round(w * band_frac))
    lo = round(h * 0.15)
    x0, x1 = round(w * 0.38), round(w * 0.62) - bw

    def ok(y, x):
        # clear row: at most rule_px inked pixels across the band, so a thin
        # vertical rule between the two tables still counts as a gutter but
        # letters of a title running across it do not
        return sum(v >= clear for v in ink[y][x:x + bw]) <= rule_px

    best = None
    for x in range(x0, x1):
        frac = sum(ok(y, x) for y in range(lo, h)) / (h - lo)
        if best is None or frac > best[0]:
            best = (frac, x)
    frac, x = best
    if frac < need:
        if __name__ == "__main__":
            print(f"  no gutter: best band x={x / w:.2f} clear on {frac:.2f} of rows")
        return None

    def strict(y):
        return not any(v >= clear for v in ink[y][x:x + bw])

    # a rule between the tables makes the strict test fail on most rows; only
    # then fall back to the rule-tolerant test for the walk
    ruled = sum(strict(y) for y in range(lo, h)) / (h - lo) < need
    # walk up from the bottom: y0 = top of the gutter, tolerating short gaps.
    # A centred title can have a word space exactly at the gutter ("CEYLON
    # PRODUCE", vol021 p1175), so a clear band is not enough: the clear span
    # around the band must be about as wide as the gutter is in the body
    cx, lim = x + bw // 2, round(w * 0.15)

    def span(y):
        r = ink[y]
        a = cx
        while a > cx - lim and (r[a - 1] < clear or ruled and abs(a - 1 - cx) <= bw // 2):
            a -= 1
        b = cx
        while b < cx + lim and (r[b + 1] < clear or ruled and abs(b + 1 - cx) <= bw // 2):
            b += 1
        return a, b

    body = sorted(span(y) for y in range(round(h * 0.5), h) if ok(y, x))
    medl = sorted(a for a, _ in body)[len(body) // 2]
    medr = sorted(b for _, b in body)[len(body) // 2]
    tol = max(2, (medr - medl) // 4)

    def wide(y):
        a, b = span(y)
        return ok(y, x) and a <= medl + tol and b >= medr - tol

    y, gap, y0 = h - 1, 0, h - 1
    while y >= 0:
        if wide(y):
            gap, y0 = 0, y
        else:
            gap += 1
            if gap > 3:                 # specks only: a title line is ~8 rows here
                break
        y -= 1
    if y0 > h * 0.40:
        return None
    # y0 can land inside a text line that crosses the gutter (vol021 p924
    # "COLOMBO, JUNE 24, 1901"); cut instead at the lightest full-width row
    # just below, so that line stays whole in the top strip
    y0 = min(range(y0, min(h, y0 + round(h * 0.03))), key=lambda y: sum(ink[y]))
    sx = im.width / w
    return round((x + bw / 2) * sx), round(y0 * sx)


def rule(im, clear=60, need=0.85, slabs=10):
    """Centre rule between two ruled tables (Market Rates pages, where the
    two halves are boxed and abut a vertical line, so there is no blank
    gutter). Traced per horizontal slab to follow a slightly skewed scan.
    Returns ([(x, y_top, y_bottom) per slab] at full resolution, y0) or None."""
    w, h, ink = _ink(im)
    lo = round(h * 0.15)
    x0, x1 = round(w * 0.42), round(w * 0.58)
    edges = [lo + (h - lo) * k // slabs for k in range(slabs + 1)]

    def cover(x, a, b):        # share of rows a..b with ink at x-1..x+1
        return sum(any(ink[y][i] >= clear for i in (x - 1, x, x + 1)) for y in range(a, b)) / (b - a)

    # seed on the slab at mid-page, then follow it up and down within +-3 px
    mid = slabs // 2
    best = max(range(x0, x1), key=lambda x: cover(x, edges[mid], edges[mid + 1]))
    if cover(best, edges[mid], edges[mid + 1]) < need:
        return None
    xs = {mid: best}
    for order in (range(mid + 1, slabs), range(mid - 1, -1, -1)):
        prev = best
        for k in order:
            c = max(range(prev - 3, prev + 4), key=lambda x: cover(x, edges[k], edges[k + 1]))
            if cover(c, edges[k], edges[k + 1]) < need:
                if __name__ == "__main__":
                    print(f"  rule lost in slab {k}")
                return None
            xs[k] = prev = c
    # walk up above the body along the rule to where it starts
    x, y = xs[0], lo
    while y > 0 and any(ink[y - 1][i] >= clear for i in (x - 1, x, x + 1)):
        y -= 1
    s = im.width / w
    segs = [(round(xs[k] * s), round(edges[k] * s), round(edges[k + 1] * s)) for k in range(slabs)]
    segs[0] = (segs[0][0], round(y * s), segs[0][2])
    return segs, round(y * s)


def _hcut(im):
    """Cut at the lightest row within +-15% of the middle."""
    g = im.convert("L").resize((200, max(1, im.height // 4)))
    h = g.height
    rows = [sum(g.crop((0, y, 200, y + 1)).tobytes()) for y in range(h)]
    lo, hi = int(h * .35), int(h * .65)
    y = max(range(lo, hi - 3), key=lambda y: sum(rows[y:y + 3])) + 1
    return [im.crop((0, 0, im.width, y * 4)), im.crop((0, y * 4, im.width, im.height))]


def split(im):
    """('gutter', x, y0) | ('rule', segs, y0) | None"""
    g = gutter(im)
    if g:
        return ("gutter",) + g
    r = rule(im)
    if r:
        return ("rule",) + r
    return None


def _side(im, segs, y0, left):
    """The part of im on one side of the traced rule, the rule itself and the
    other side painted white, cropped to that side."""
    r = max(4, round(im.width * 0.004))
    out = im.copy()
    d = ImageDraw.Draw(out)
    for x, a, b in segs:
        if left:
            d.rectangle((x - r, a, im.width, b), fill="white")
        else:
            d.rectangle((0, a, x + r, b), fill="white")
    xs = [x for x, _, _ in segs]
    box = (0, y0, max(xs) + r, im.height) if left else (min(xs) - r, y0, im.width, im.height)
    return out.crop(box)


def pieces(im):
    s = split(im)
    if s is None:
        return None
    kind, geo, y0 = s
    out = []
    if y0 > im.height * 0.02:
        out.append(im.crop((0, 0, im.width, y0)))
    if kind == "gutter":
        cols = [im.crop((0, y0, geo, im.height)), im.crop((geo, y0, im.width, im.height))]
    else:
        cols = [_side(im, geo, y0, True), _side(im, geo, y0, False)]
    for c in cols:
        out += _hcut(c)
    return out


if __name__ == "__main__":
    im = Image.open(sys.argv[1]).convert("RGB")
    s = split(im)
    print(sys.argv[1], im.size, s and s[0], s and f"y0={s[2] / im.height:.2f}",
          s and (f"x={s[1] / im.width:.2f}" if s[0] == "gutter" else
                 "x=" + ",".join(f"{x / im.width:.3f}" for x, _, _ in s[1])))
    if s and len(sys.argv) > 2:
        kind, geo, y0 = s
        d = ImageDraw.Draw(im)
        d.line((0, y0, im.width, y0), fill=(255, 0, 0), width=8)
        if kind == "gutter":
            d.line((geo, y0, geo, im.height), fill=(255, 0, 0), width=8)
        else:
            for x, a, b in geo:
                d.line((x, max(a, y0), x, b), fill=(255, 0, 0), width=8)
        im.resize((im.width * 1100 // im.height, 1100)).save(sys.argv[2] + ".png")
        for k, pc in enumerate(pieces(Image.open(sys.argv[1]).convert("RGB")), 1):
            pc.resize((max(1, pc.width // 4), max(1, pc.height // 4))).save(f"{sys.argv[2]}_piece{k}.png")
