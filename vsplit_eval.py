#!/usr/bin/env python3
"""
Score side-by-side table pages: the corpus reading vs the V (column-split)
reading, for content AND reading order.

Content  recall of the page's Tesseract content words (stage4/audit), as in
         table_eval.py; summary/loop flags likewise.
Order    the two tables of a side-by-side page should be read one after the
         other. Anchors = tokens (lower-case letters/digits, >= 3 chars, e.g.
         lot numbers, estate names) that occur exactly once among the page's
         Tesseract words (repair/vsplit/tess) and exactly once in the reading.
         Each anchor is placed on the left or right of the split (tsplit.py
         geometry; words in the full-width top strip are ignored). Walking
         the reading in order, `switch` = column changes / anchors. Read
         column by column it is ~1/anchors; interleaved row by row (lot 256,
         lot 410, lot 257, lot 412 ...) it approaches 1.

Intab    share of content words inside <table> markup (see intab()).

Usage: vsplit_eval.py CORPUS AUDIT TESSDIR SPLITS ROUND_DIR > eval.tsv
"""
import collections, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import table_eval as te  # noqa: E402
import tsplit  # noqa: E402

TOK = re.compile(r"[a-z0-9]{3,}")


def toks(s):
    return TOK.findall(s.lower())


def reading_tokens(txt):
    t = re.sub(r"<[^>]+>", " ", te.body(txt))
    return toks(t)


def intab(txt):
    """Share of content words inside <table> markup: on these all-table pages
    a piece read as loose text (item names listed apart from their prices,
    vol019 p309 right half) drops it."""
    t = te.body(txt)
    a = len(te.twords(" ".join(re.findall(r"<table.*?</table>", t, re.S))))
    b = len(te.twords(re.sub(r"<table.*?</table>", " ", t, flags=re.S)))
    return a / (a + b) if a + b else 1.0


def order(tess, x, y0, rtoks):
    side, count = {}, collections.Counter()
    for l, t, r, b, w in tsplit.words(tess):
        for k in toks(w):
            count[k] += 1
            if t >= y0 and (r <= x or l >= x):
                side[k] = "L" if r <= x else "R"
    rc = collections.Counter(rtoks)
    seq = [side[k] for k in rtoks if count[k] == 1 and rc[k] == 1 and k in side]
    if len(seq) < 10:
        return len(seq), float("nan")
    sw = sum(a != b for a, b in zip(seq, seq[1:]))
    return len(seq), sw / len(seq)


def main(corpus, audit, tessdir, splits, rd):
    corpus, audit, rd = pathlib.Path(corpus), pathlib.Path(audit), pathlib.Path(rd)
    geo = {}
    for l in open(splits):
        t, p, x, y0 = l.split("\t")[:4]
        geo[(t, p)] = (int(x), int(y0))
    cap = int((rd / "MAX_OUT").read_text())
    reads = collections.defaultdict(list)
    for idx in sorted((rd / "in").glob("*.index.tsv")):
        stem = idx.name[:-len(".index.tsv")]
        out = rd / "out" / stem
        if not (out / f"{stem}.md").exists():
            continue
        pages, toks_ = te.load(out)
        parts = collections.OrderedDict()
        for i, l in enumerate(open(idx)):
            f = l.rstrip("\n").split("\t")
            parts.setdefault((f[0], f[1]), []).append(i)
        for (t, p), ii in parts.items():
            txt = "\n\n".join(pages[i] for i in ii)
            reads[(t, p)].append((f"{rd.name}/{stem}", txt, max(toks_[i] for i in ii),
                                  any(toks_[i] >= cap for i in ii), f"{rd.name}/{stem}:" + "+".join(map(str, ii))))
    cache = {}
    print("tag\tpage\tvariant\ttok\tloop\tsummary\trecall\twords\tanchors\tswitch\tintab\tsrc")
    for (t, p), rr in sorted(reads.items()):
        if t not in cache:
            cache[t] = te.load(corpus / t)
        tw = te.content((audit / t / f"p{int(p):04d}.txt").read_text().lower().split())
        tess = f"{tessdir}/{t}_p{int(p):04d}.tsv"
        x, y0 = geo[(t, p)]
        old = cache[t][0][int(p)]
        allr = [("v5", old, cache[t][1][int(p)], False, "v5")] + rr
        for v, txt, tok, capped, src in allr:
            loop = int(capped or te.detect_repeat_token(txt.rstrip()))
            xw = te.twords(txt)
            n, sw = order(tess, x, y0, reading_tokens(txt))
            print(f"{t}\t{p}\t{v}\t{tok}\t{loop}\t{int(bool(te.SUMM.search(te.body(txt))))}\t"
                  f"{te.recall(tw, xw):.2f}\t{len(xw)}\t{n}\t{sw:.2f}\t{intab(txt):.2f}\t{src}")


if __name__ == "__main__":
    main(*sys.argv[1:])
