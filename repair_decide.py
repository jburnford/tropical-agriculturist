#!/usr/bin/env python3
"""
Decide, page by page, which reading of each repair-list page goes in the corpus.

Readings of a page:
  old  the corpus reading (output_v4), from the original image, 16k cap
  O    original image again, 32k cap            (repair/*/in/O_*.pdf)
  E    autocontrast image, 16k cap              (repair/*/in/E_*.pdf)
  X,H  any later variant: X_*.pdf, H_*.pdf ...  (different images again)

A reading is *usable* if it does not loop: under its token cap and Chandra's
detect_repeat_token does not fire.

Every Chandra reading of a faint page can repeat the same fluent
hallucination, across image variants (J, K and the half-leaf Q all read
"1860 1861 ... 1919" off one show-through verso), and Chandra de-mirrors
show-through into clean text. So agreement between Chandra readings is NOT
used as evidence. The independent witness is Tesseract on the full-resolution
leaf (tess_witness.py, stage4/tess/): it does not invent text, and it reads
mirror-reversed print as junk. tn / tm = confident words read normally /
mirrored. Calibrated on pages checked by eye at full size: show-through
vol012 p15 13/91, vol010 p583 0/28, vol023 p1001 8/53; real print vol005
p444 782/126; very faint real print vol022 p979 2/3, p1235 1/0.

Rules, in order:
  SHOWTHROUGH  tm >= 15, tm >= 3*tn and tn < 15: the only legible print on the
               page is the reverse side of the sheet. Page emptied. Guard: a
               page printed upside down also reads better mirrored than normal,
               so Tesseract is run at 180 degrees too (stage4/tess/rot.tsv);
               rot >= tm means ROTATED print, not show-through -> UNRESOLVED.
               (vol067 iss04 p63: norm 11, mirr 38, rot 235.) Full-size checks
               confirmed mirroring on vol023 p1045 and vol019 p1036, which I had
               wrongly called real from thumbnails.
  ACCEPT       tn >= 15 (the page has its own print) and a usable Chandra
  ACCEPT_CAP   reading contains >= 70% of Tesseract's content words (alphabetic,
               >= 4 letters, order-free: Tesseract's column/table order differs).
               Preference: J (leaf), then old/O, then the rest. ACCEPT_CAP for
               pages that were capped but not faded.
  KEEP_BLANK   tn < 15, old reading empty, and the leaf readings (J, K) empty.
  KEEP_MINOR   tn < 15 and every usable reading holds <= 10 words.
  KEEP_FIGURE  faded page, tn < 15, but the corpus reading contains an image
               (figure/graph) and its transcribed words agree (>= FIG_AGREE,
               0.30) with the leaf reading J -- PDF and leaf families. Chandra
               paraphrases its description of a graph each time, so whole-page
               agreement is low; at 0.30-0.55 every one of 28 pairs checked
               opened with the same figure title ("distribution of oidium in
               ceylon 1929", "relation between yield per hill and spacing"). Graph labels are
               hand-lettered or rotated; Tesseract reads none of them
               (vol099 iss02 p39 "Export of Cinchona Bark From 1882 to 1902").
  FAINT        faded page, tn < 15, readings disagree or have text: no print of
               its own that any engine can verify. Sampled at full size these are
               overwhelmingly show-through too faint for Tesseract to read even
               mirrored (Chandra de-mirrors or invents over them: "THE NEW YORK
               PUBLIC LIBRARY" x8, "OBITUARY PRODUCTION BIRTH"), plus a few
               figures and a few genuinely faint real pages (vol022 p979).
               Transcribed text is withheld; image links and their descriptions
               from the corpus reading are kept; page goes on the review list.
  ACCEPT_CAP   capped, not faded, tn < 15 (figures, numeric tables Tesseract
  (unverified) cannot read): the O or H re-read that finishes.
  UNRESOLVED   everything else: legible to Tesseract but no Chandra reading it
               supports, or Chandra text that Tesseract cannot confirm
               ("unverifiable"). Text withheld, page listed for review.

[Superseded rules -- agreement between Chandra readings across image variants,
and neighbour-duplicate detection -- are in git history of this file's
predecessor notes: they accepted hallucinations and blanked real pages.]

Usage: repair_decide.py OUTDIR_CORPUS REPAIR_ROOT > decisions.tsv
  columns: tag page reason action source words note
  source = old | <round>/<stem>:<idx>
"""
import collections, csv, difflib, json, pathlib, re, sys

sys.path.insert(0, "/scratch/jic823/chandra/venv/lib/python3.11/site-packages")
from chandra.model.util import detect_repeat_token  # noqa: E402

MARK = re.compile(r"^\d+-{48}\s*$", re.M)
AGREE = 0.80
CAP = {"old": 16000}
SAME_IMAGE = {"old": "pdf", "O": "pdf", "E": "pdf",     # source families; agreement
              "J": "leaf", "K": "leaf",                 # only counts across them
              "H": "half", "Q": "half", "M": "mirror"}
SHOW = 0.50          # (b) only, disabled
DUP = 0.90           # (a)/(c): near-exact copy of the brighter neighbour. Checked
                     # against the leaves 2026-10-03: all 8 pages >= 0.90 are
                     # mirrored "To Our Readers" versos; at 0.50-0.89, 13 of 22
                     # sampled pages were REAL print (Produce Sales Lists share
                     # most of their vocabulary page to page).
RANK = {"J": 0, "old": 1, "O": 1, "H": 1, "K": 2, "Q": 2, "E": 3}
NOT_TEXT = {"M"}                                         # mirrored: evidence only, never page text
MAXCMP = 3000                                            # difflib is quadratic
TESS_MIN = 15        # confident Tesseract words that make a page "legible"
RECALL = 0.70        # share of Tesseract's content words a Chandra reading must contain
FIG_AGREE = 0.30     # KEEP_FIGURE: corpus vs leaf reading on a page with an image


def content(ws):
    """Words that discriminate: alphabetic, >= 4 letters."""
    return [w for w in ws if len(w) >= 4 and w.isalpha()]


def recall(tw, rw):
    """Share of Tesseract content words present in the reading (multiset, order-free)."""
    if not tw:
        return 0.0
    c = collections.Counter(content(rw))
    hit = 0
    for w, n in collections.Counter(tw).items():
        hit += min(n, c.get(w, 0))
    return hit / len(tw)


def words(t):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)[^\n]*", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[#*_|`>\[\]]", " ", t)
    return re.findall(r"\w+", t.lower())


def load(d):
    md = next(pathlib.Path(d).rglob("*.md"))
    meta = json.load(open(next(pathlib.Path(d).rglob("*_metadata.json"))))
    return MARK.split(md.read_text(errors="replace")), [int(p["token_count"]) for p in meta["pages"]]


def agree(a, b):
    if not a and not b:
        return 1.0
    if max(len(a), len(b)) > MAXCMP:      # long pages: compare a head and a tail slice
        a, b = a[:1000] + a[-1000:], b[:1000] + b[-1000:]
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


CONTRAST = {}


def dedupe(w, n=6):
    """Drop repeats of any n-gram already seen, so a loop counts once."""
    seen, out = set(), []
    for i in range(len(w)):
        g = tuple(w[i:i + n])
        if g in seen:
            continue
        seen.add(g); out.append(w[i])
    return out


def dup_of_neighbour(w, nbr, tag, p, floor=None):
    """Share of these words found, in order, in a neighbouring page's text --
    only if this page is the fainter of the two. Returns a tag when the share
    is >= floor (default DUP)."""
    floor = DUP if floor is None else floor
    if len(w) < 15:
        return None
    w = w[:MAXCMP]
    for q in (p - 1, p + 1):
        if CONTRAST.get((tag, p), 0) >= CONTRAST.get((tag, q), 0):
            continue
        for nw in nbr(tag, q):
            sm = difflib.SequenceMatcher(None, w, nw[:MAXCMP * 2], autojunk=False)
            hit = sum(b.size for b in sm.get_matching_blocks()) / len(w)
            if hit >= floor:
                return f"~dup-p{q}:{hit:.2f}"
    return None


def showthrough(R, pages, p):
    """Mirrored-leaf words found, in order, in a neighbouring page: share >= SHOW."""
    for r in R:
        if r["v"] != "M" or not r["ok"] or len(r["w"]) < 15:
            continue
        mw = r["w"][:MAXCMP]
        for q in (p - 1, p + 1):
            if 0 <= q < len(pages):
                nw = words(pages[q])[:MAXCMP * 2]
                sm = difflib.SequenceMatcher(None, mw, nw, autojunk=False)
                hit = sum(b.size for b in sm.get_matching_blocks())
                if hit / len(mw) >= SHOW:
                    return r["src"] + f"~p{q}:{hit / len(mw):.2f}"
    return None


def main(corpus, root):
    corpus, root = pathlib.Path(corpus), pathlib.Path(root)
    for row in open(root.parent / "stage4" / "ink.tsv"):
        x = row.split("\t")
        if x[0] != "tag":
            CONTRAST[(x[0], int(x[1]))] = int(x[5])
    reads = collections.defaultdict(list)      # (tag,page) -> [(variant, source, text, tok, cap)]
    reason = {}
    for idx in sorted(root.glob("*/in/*.index.tsv")):
        stem = idx.name[:-len(".index.tsv")]
        rnd = idx.parent.parent.name
        out = idx.parent.parent / "out" / stem
        if not (out / f"{stem}.md").exists():
            continue
        cap = int((idx.parent.parent / "MAX_OUT").read_text())
        pages, toks = load(out)
        rows = [l.rstrip("\n").split("\t") for l in open(idx)]
        assert len(rows) == len(pages), stem
        v = stem.split("_")[0]
        for i, row in enumerate(rows):
            tag, page, why = row[:3]
            reason[(tag, page)] = why
            if len(row) > 3:                               # H: one part of a split page
                prev = reads[(tag, page)][-1] if reads[(tag, page)] else None
                if row[3] != "1" and prev and prev[0] == v and prev[1].endswith(":part"):
                    src = prev[1][:-5] + f"+{i}"
                    nparts = 3 if v == "T" else 2
                    if int(row[3]) < nparts:
                        src += ":part"
                    reads[(tag, page)][-1] = (v, src, prev[2] + "\n\n" + pages[i], max(prev[3], toks[i]), cap)
                else:
                    reads[(tag, page)].append((v, f"{rnd}/{stem}:{i}:part", pages[i], toks[i], cap))
                continue
            reads[(tag, page)].append((v, f"{rnd}/{stem}:{i}", pages[i], toks[i], cap))
    cache = {}

    def nbr(tag, q):
        """Word lists for page q: corpus text plus every re-read of it."""
        if tag not in cache:
            cache[tag] = load(corpus / tag)
        out = []
        if 0 <= q < len(cache[tag][0]):
            out.append(words(cache[tag][0][q]))
        for v, src, txt, tok, cap in reads.get((tag, str(q)), []):
            if v not in NOT_TEXT:
                out.append(words(txt))
        return out

    tess = {}
    for row in csv.DictReader(open(root.parent / "stage4" / "tess" / "tess.tsv"), delimiter="\t"):
        f = root.parent / "stage4" / "tess" / "text" / row["tag"] / f"p{int(row['page']):04d}.txt"
        tess[(row["tag"], row["page"])] = (int(row["norm_words"]), int(row["mirr_words"]),
                                           content(f.read_text().lower().split()) if f.exists() else [])

    rot = {}
    rf = root.parent / "stage4" / "tess" / "rot.tsv"
    if rf.exists():
        for row in csv.DictReader(open(rf), delimiter="\t"):
            rot[(row["tag"], row["page"])] = int(row["rot_words"])

    print("tag\tpage\treason\taction\tsource\twords\tnote")
    for (tag, page), rr in sorted(reads.items()):
        if tag not in cache:
            cache[tag] = load(corpus / tag)
        why = reason[(tag, page)]
        allr = [("old", "old", cache[tag][0][int(page)], cache[tag][1][int(page)], 16000)] + rr
        R = []
        for v, src, txt, tok, cap in allr:
            ok = tok < cap and not detect_repeat_token(txt.rstrip()) and not src.endswith(":part")
            R.append(dict(v=v, src=src, w=words(txt), ok=ok, img=SAME_IMAGE.get(v, v)))
        T = [r for r in R if r["v"] not in NOT_TEXT]
        old = R[0]
        note = " ".join(f"{r['v']}:{'ok' if r['ok'] else 'LOOP'}:{len(r['w'])}w" for r in R)
        act, src = "UNRESOLVED", ""
        tn, tm, tw = tess.get((tag, page), (None, None, []))
        note += f" tess:{tn}/{tm}"
        usable = [r for r in T if r["ok"]]
        leaf = [r for r in R if r["v"] in ("J", "K")]

        if tn is None:
            note += " no-leaf"
        elif tm >= TESS_MIN and tm >= 3 * max(tn, 1) and tn < TESS_MIN:
            if (tag, page) not in rot:
                note += " rot-unchecked"                       # rerun stage4/tess_rot.py
            elif rot[(tag, page)] >= tm:
                note += f" ROTATED:{rot[(tag, page)]}"
            else:
                act, src = "SHOWTHROUGH", f"tess-mirror:{tm}/{tn}/rot{rot[(tag, page)]}"
        elif tn >= TESS_MIN:
            # the page has its own print: accept the best Chandra reading that
            # Tesseract's confident words back up
            scored = sorted(((recall(tw, r["w"]), r) for r in usable),
                            key=lambda x: (x[0] < RECALL, RANK.get(x[1]["v"], 9), -x[0]))
            if scored and scored[0][0] >= RECALL:
                rec, r = scored[0]
                act = "ACCEPT_CAP" if "faded" not in why else "ACCEPT"
                src = r["src"] if r["v"] != "old" else "old"
                note += f" recall={rec:.2f}"
            else:
                note += f" best-recall={max((x[0] for x in scored), default=0):.2f}"
        elif old["ok"] and not old["w"] and all(r["ok"] and not r["w"] for r in leaf):
            act, src = "KEEP_BLANK", "old"
        elif usable and all(len(r["w"]) <= 10 for r in usable) and old["ok"]:
            act, src = "KEEP_MINOR", "old"
        elif "faded" not in why:
            # capped at normal contrast, little text Tesseract can read (figures,
            # numeric tables): a re-read that finishes is the fix
            o = [r for r in R if r["v"] == "O" and r["ok"]] + [r for r in R if r["v"] == "H" and r["ok"]]
            if o:
                act, src = "ACCEPT_CAP", o[0]["src"]
                note += " unverified"
        else:
            J = next((r for r in R if r["v"] == "J" and r["ok"]), None)
            raw_old = cache[tag][0][int(page)]
            if old["ok"] and J and "![" in raw_old and len(old["w"]) >= 5 and agree(old["w"], J["w"]) >= FIG_AGREE:
                act, src = "KEEP_FIGURE", "old"
                note += f" agree-J={agree(old['w'], J['w']):.2f}"
            else:
                act, src = "FAINT", "old-images-only"
        n = next((len(r["w"]) for r in R if r["src"] == src), 0)
        print(f"{tag}\t{page}\t{why}\t{act}\t{src}\t{n}\t{note}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
