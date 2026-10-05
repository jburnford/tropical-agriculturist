#!/usr/bin/env python3
"""
Score readings of table pages against the corpus-wide Tesseract audit text.

For each page in REPAIR_ROOT/<round>/in/*.index.tsv (strip variants H/T are
joined in part order), and for the corpus reading, prints:
  tag page variant tok loop summary recall words
  summary  1 if the transcribed body uses Chandra's table-summary phrasing
           ("Table with 4 columns ...", "Includes categories like ...")
  recall   share of the page's Tesseract content words (stage4/audit) present

Usage: table_eval.py CORPUS AUDIT ROUND_DIR... > eval.tsv
"""
import collections, json, pathlib, re, sys

sys.path.insert(0, "/scratch/jic823/chandra/venv/lib/python3.11/site-packages")
from chandra.model.util import detect_repeat_token  # noqa: E402

MARK = re.compile(r"^\d+-{48}\s*$", re.M)
SUMM = re.compile(r"Table with \d+ (main )?columns|Includes (categories|items|sections|entries|data|rows)|"
                  r"The table (lists|contains|shows|includes)|Contains multiple rows|Various entries for|"
                  r"It lists (various|the)", re.I)


def content(ws):
    return [w for w in ws if len(w) >= 4 and w.isalpha()]


def body(t):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)[^\n]*", " ", t)
    return re.sub(r"<!--.*?-->", " ", t, flags=re.S)


def twords(t):
    return content(re.findall(r"[a-z]+", re.sub(r"<[^>]+>", " ", body(t)).lower()))


def recall(tw, xw):
    if not tw:
        return 1.0
    c = collections.Counter(xw)
    return sum(min(n, c.get(w, 0)) for w, n in collections.Counter(tw).items()) / len(tw)


def load(d):
    md = next(pathlib.Path(d).rglob("*.md"))
    meta = json.load(open(next(pathlib.Path(d).rglob("*_metadata.json"))))
    return MARK.split(md.read_text(errors="replace")), [int(p["token_count"]) for p in meta["pages"]]


def main(corpus, audit, *rounds):
    corpus, audit = pathlib.Path(corpus), pathlib.Path(audit)
    reads = collections.defaultdict(list)
    for rd in map(pathlib.Path, rounds):
        cap = int((rd / "MAX_OUT").read_text())
        for idx in sorted((rd / "in").glob("*.index.tsv")):
            stem = idx.name[:-len(".index.tsv")]
            out = rd / "out" / stem
            if not (out / f"{stem}.md").exists():
                continue
            pages, toks = load(out)
            parts = collections.OrderedDict()
            for i, l in enumerate(open(idx)):
                x = l.rstrip("\n").split("\t")
                parts.setdefault((x[0], x[1]), []).append(i)
            for (t, p), ii in parts.items():
                txt = "\n\n".join(pages[i] for i in ii)
                reads[(t, p)].append((f"{rd.name}/{stem}", txt, max(toks[i] for i in ii),
                                      any(toks[i] >= cap for i in ii),
                                      f"{rd.name}/{stem}:" + "+".join(map(str, ii))))
    cache = {}
    print("tag\tpage\tvariant\ttok\tloop\tsummary\trecall\twords\tsrc")
    for (t, p), rr in sorted(reads.items()):
        if t not in cache:
            cache[t] = load(corpus / t)
        tw = content((audit / t / f"p{int(p):04d}.txt").read_text().lower().split())
        allr = [("old", cache[t][0][int(p)], cache[t][1][int(p)], cache[t][1][int(p)] >= 16000, "old")] + rr
        for v, txt, tok, capped, src in allr:
            loop = int(capped or detect_repeat_token(txt.rstrip()))
            xw = twords(txt)
            print(f"{t}\t{p}\t{v}\t{tok}\t{loop}\t{int(bool(SUMM.search(body(txt))))}\t"
                  f"{recall(tw, xw):.2f}\t{len(xw)}\t{src}")


if __name__ == "__main__":
    main(*sys.argv[1:])
