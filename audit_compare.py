#!/usr/bin/env python3
"""
Stage 4 audit: compare every corpus page with the Tesseract pass (audit_tess.py).

Per page:
  tess   Tesseract content words (alphabetic, >= 4 letters, conf >= 70)
  text   corpus content words, same filter; image links + their descriptions
         and stage4 markers excluded
  recall share of tess words present in text (multiset, order-free)

Flags:
  MISSING  tess >= 15 and recall < 0.50 -- the page has legible print the
           corpus text does not contain (wrong, truncated or hallucinated text)
  EXTRA    tess < 3 and text >= 50 -- substantial text on a page where
           Tesseract sees nothing legible (hallucination, or print too faint
           for Tesseract; checked against stage4 decisions)
Pages carrying a stage4 marker are reported with that action instead.

Usage: audit_compare.py CORPUS_DIR AUDIT_DIR > audit.tsv ; summary on stderr
"""
import collections, json, pathlib, re, sys

MARK = re.compile(r"^\d+-{48}\s*$", re.M)
S4 = re.compile(r"<!-- stage4: (\w+)")


def content(ws):
    return [w for w in ws if len(w) >= 4 and w.isalpha()]


def text_words(t):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)[^\n]*", " ", t)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"\[(Page not transcribed|Faint page)[^\]]*\]", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return content(re.findall(r"[a-z]+", t.lower()))


def recall(tw, xw):
    if not tw:
        return 1.0
    c = collections.Counter(xw)
    return sum(min(n, c.get(w, 0)) for w, n in collections.Counter(tw).items()) / len(tw)


def main(corpus, audit):
    corpus, audit = pathlib.Path(corpus), pathlib.Path(audit)
    summ = collections.Counter()
    print("tag\tpage\tflag\ttess\ttext\trecall\tstage4")
    for d in sorted(corpus.glob("vol*")):
        tag = d.name
        md = next(d.rglob("*.md"))
        pages = MARK.split(md.read_text(errors="replace"))
        for p, txt in enumerate(pages):
            f = audit / tag / f"p{p:04d}.txt"
            if not f.exists():
                summ["no-audit"] += 1
                continue
            tw = content(f.read_text().lower().split())
            xw = text_words(txt)
            r = recall(tw, xw)
            m = S4.search(txt)
            s4 = m.group(1) if m else ""
            flag = ""
            if len(tw) >= 15 and r < 0.50:
                flag = "MISSING"
            elif len(tw) < 3 and len(xw) >= 50:
                flag = "EXTRA"
            summ["pages"] += 1
            if flag:
                summ[f"{flag}{'/' + s4 if s4 else ''}"] += 1
                print(f"{tag}\t{p}\t{flag}\t{len(tw)}\t{len(xw)}\t{r:.2f}\t{s4}")
    for k, v in sorted(summ.items()):
        print(f"{k}\t{v}", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:3])
