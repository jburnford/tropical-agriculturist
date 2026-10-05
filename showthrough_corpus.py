#!/usr/bin/env python3
"""
Corpus-wide show-through detection from the two Tesseract passes.

stage4/audit         every page as scanned   (audit_tess.py)
stage4/audit_mirror  every page flipped L-R  (MIRROR=1 audit_tess.py)

A page whose only legible print is the reverse side of the sheet reads well
mirrored and badly as scanned. Chandra de-mirrors such print into clean text
(and sometimes invents an opening line: vol022 p893, "Appendix to the Journal
of the Horticultural Society of London 1863"), so the corpus carries a copy
of the neighbouring page -- or worse -- on a blank verso.

Only REAL words are counted: Tesseract reads mirrored print as reversed
fragments that are often alphabetic ("ton yom tot uot haw bus" on vol022
p893, 27 "confident words" as scanned against 211 mirrored). A word counts if
it occurs >= 5 times in the corpus's own text (Chandra never writes "uot").

Candidate: mirrored >= 15 real words and >= 3x the as-scanned real words.
(No absolute cap on as-scanned: a page with print of its own reads strongly
as scanned and cannot reach the 3:1 ratio.)
Pages already carrying a stage4 decision are skipped. For candidates, Tesseract
is run once more at 180 degrees: upside-down print also reads better mirrored
than as scanned (vol067 iss04 p63), so rot >= mirrored rules the page out.

Emits repair_decide.py-format rows: SHOWTHROUGH when the corpus page holds
>= 15 transcribed words (apply_repairs.py empties the page: it is a blank
verso). Candidates with fewer words are already effectively blank and are
left alone.

Usage: showthrough_corpus.py CORPUS DECISIONS_ALL NPROC > decisions_showthrough.tsv
"""
import csv, glob, pathlib, re, sys
from multiprocessing import Pool

sys.path.insert(0, "/scratch/jic823/tropical")
from audit_compare import text_words  # noqa: E402
from tess_witness import tess  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402

MARK = re.compile(r"^\d+-{48}\s*$", re.M)
MIN = 15


def vocabulary(corpus, minfreq=5):
    import collections
    c = collections.Counter()
    for d in pathlib.Path(corpus).glob("vol*"):
        c.update(re.findall(r"[a-z]{3,}", next(d.rglob("*.md")).read_text(errors="replace").lower()))
    return {w for w, n in c.items() if n >= minfreq}


def counts(root, vocab):
    c = {}
    for f in pathlib.Path(root).glob("vol*/p*.txt"):
        c[(f.parent.name, int(f.stem[1:]))] = sum(w.lower() in vocab for w in f.read_text().split())
    return c


PDFS = {}
for f in glob.glob("chunks/chunk_*.tsv"):
    for l in open(f):
        t, p = l.split("\t")[:2]; PDFS[t] = p


def rot180(job):
    t, p = job
    doc = pdfium.PdfDocument(PDFS[t])
    im = doc[p].render(scale=300 / 72, grayscale=True).to_pil().rotate(180)
    doc.close()
    return t, p, len(tess(im)[0])


def main(corpus, decisions, nproc):
    vocab = vocabulary(corpus)
    norm, mirr = counts("stage4/audit", vocab), counts("stage4/audit_mirror", vocab)
    decided = {(r["tag"], int(r["page"])) for r in csv.DictReader(open(decisions), delimiter="\t")
               if r["action"] not in ("KEEP_BLANK", "KEEP_MINOR", "KEEP_FIGURE", "TABLE_UNFIXED")}
    cand = [k for k, m in mirr.items() if k not in decided and m >= MIN
            and m >= 3 * max(norm.get(k, 0), 1)]
    with Pool(int(nproc)) as pool:
        rot = {(t, p): r for t, p, r in pool.map(rot180, cand)}
    pages = {}
    print("tag\tpage\treason\taction\tsource\twords\tnote")
    n_rot = n_blank = n_show = 0
    for t, p in sorted(cand):
        if rot[(t, p)] >= mirr[(t, p)]:
            n_rot += 1
            continue
        if t not in pages:
            pages[t] = MARK.split(next(pathlib.Path(corpus, t).rglob("*.md")).read_text(errors="replace"))
        w = len(text_words(pages[t][p]))
        if w < MIN:
            n_blank += 1
            continue
        n_show += 1
        print(f"{t}\t{p}\tcorpus-mirror\tSHOWTHROUGH\ttess-mirror:{mirr[(t, p)]}/{norm.get((t, p), 0)}"
              f"/rot{rot[(t, p)]}\t0\tcorpus {w} words removed (real words: mirrored {mirr[(t, p)]}, "
              f"as scanned {norm.get((t, p), 0)})")
    print(f"candidates {len(cand)}: rotated {n_rot}, already blank {n_blank}, emptied {n_show}",
          file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
