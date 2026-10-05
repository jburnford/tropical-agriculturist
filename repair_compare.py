#!/usr/bin/env python3
"""
Compare each re-read page (repair_ocr.slurm output) with the corpus reading.

For every page in REPAIRDIR/in/<stem>.index.tsv, prints:
  stem idx tag page reason  old_tok new_tok  old_rep new_rep  agree  old_words new_words

  *_rep   Chandra's detect_repeat_token on the page text, or the token cap hit
          (16,000 corpus / 32,000 repair) -- the page is a loop either way.
  *_words transcribed words only: image links and the description Chandra
          writes after them on the same line are dropped.
  agree   word-sequence similarity (difflib ratio, 0..1) of the two readings
          after stripping HTML/markdown/image links and case. Faded-page
          re-reads use a different input image (autocontrast), so two
          readings that agree are evidence the text is on the page; a
          hallucination is not reproduced from a different image.

Usage: repair_compare.py OUTDIR_CORPUS REPAIRDIR > compare.tsv
"""
import difflib, json, pathlib, re, sys

sys.path.insert(0, "/scratch/jic823/chandra/venv/lib/python3.11/site-packages")
from chandra.model.util import detect_repeat_token  # noqa: E402

MARK = re.compile(r"^\d+-{48}\s*$", re.M)
CORPUS_CAP, REPAIR_CAP = 16000, 32000


def words(t):
    # An image link and the rest of its line: Chandra writes its description of
    # a figure (or of a blank page: "This image is a scan of a blank page...")
    # straight after the link. That is not transcription, so it is not compared.
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)[^\n]*", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[#*_|`>\[\]]", " ", t)
    return re.findall(r"\w+", t.lower())


def load(d):
    md = next(pathlib.Path(d).rglob("*.md"))
    meta = json.load(open(next(pathlib.Path(d).rglob("*_metadata.json"))))
    pages = MARK.split(md.read_text(errors="replace"))
    return pages, [int(p["token_count"]) for p in meta["pages"]]


def looped(text, tok, cap):
    return int(tok >= cap or detect_repeat_token(text.rstrip()))


def main(corpus, rdir):
    corpus, rdir = pathlib.Path(corpus), pathlib.Path(rdir)
    cache = {}
    print("stem\tidx\ttag\tpage\treason\told_tok\tnew_tok\told_rep\tnew_rep\tagree\told_words\tnew_words")
    for idx_file in sorted((rdir / "in").glob("*.index.tsv")):
        stem = idx_file.name[:-len(".index.tsv")]
        out = rdir / "out" / stem
        if not (out / f"{stem}.md").exists():
            continue
        new_pages, new_toks = load(out)
        rows = [l.rstrip("\n").split("\t") for l in open(idx_file)]
        assert len(rows) == len(new_pages) == len(new_toks), stem
        for i, (tag, page, why) in enumerate(rows):
            if tag not in cache:
                cache[tag] = load(corpus / tag)
            op, ot = cache[tag][0][int(page)], cache[tag][1][int(page)]
            np_, nt = new_pages[i], new_toks[i]
            ow, nw = words(op), words(np_)
            # difflib is quadratic; capped pages are judged on loop/cap, not agreement
            if max(len(ow), len(nw)) > 3000:
                agree = -1.0
            elif ow or nw:
                agree = difflib.SequenceMatcher(None, ow, nw, autojunk=False).ratio()
            else:
                agree = 1.0
            print(f"{stem}\t{i}\t{tag}\t{page}\t{why}\t{ot}\t{nt}\t"
                  f"{looped(op, ot, CORPUS_CAP)}\t{looped(np_, nt, REPAIR_CAP)}\t"
                  f"{agree:.2f}\t{len(ow)}\t{len(nw)}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
