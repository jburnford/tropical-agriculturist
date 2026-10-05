#!/usr/bin/env python3
"""
Build output_v5 = output_v4 with the Stage 4 page decisions applied.

output_v4 is never modified. For each page in DECISIONS:

  KEEP_BLANK, KEEP_MINOR,
  KEEP_FIGURE, ACCEPT from "old"  unchanged
  ACCEPT / ACCEPT_CAP / ACCEPT_TABLE from a re-read
                                  page text (md and html) replaced by that
                                  reading; images it references are copied in
  SHOWTHROUGH                     page emptied: it is a blank verso whose only
                                  marks are the reverse side of the sheet
  FAINT                           transcribed text withheld; image links (and
                                  the description Chandra writes after them)
                                  kept from the corpus reading; visible marker
  UNRESOLVED                      text withheld behind a visible marker

Every changed page starts with an HTML comment naming the action and source
(invisible when rendered, greppable: "stage4:"), and its metadata page entry
gains "stage4": {"action", "source"}. Page markers are re-checked afterwards:
the page count and marker sequence of every patched file must be unchanged.

Usage: apply_repairs.py DECISIONS OUTDIR_V4 REPAIR_ROOT OUTDIR_V5
"""
import csv, json, pathlib, re, shutil, sys

MD_SEP = re.compile(r"(\n\n\d+-{48}\n\n)")
HTML_SEP = re.compile(r"(\n\n<!-- Page \d+ -->\n\n)")
IMG = re.compile(r"!\[[^\]]*\]\(([^)]+)\)|<img[^>]*src=\"([^\"]+)\"")
WITHHELD = "[Page not transcribed: OCR unreliable (stage 4 review list)]"
FAINT = "[Faint page: no legible print of its own could be verified; text withheld (stage 4 review list)]"
IMGLINE = re.compile(r"!\[[^\]]*\]\([^)]*\)[^\n]*")
HTMLIMG = re.compile(r"<img[^>]*>[^<\n]*")


def split(text, sep):
    parts = sep.split(text)
    return parts[0::2], parts[1::2]          # pages, separators


def join(pages, seps):
    out = [pages[0]]
    for s, p in zip(seps, pages[1:]):
        out += [s, p]
    return "".join(out)


class Repairs:
    """Page text from repair outputs, keyed by 'round/stem:idx[+idx2]'."""
    def __init__(self, root):
        self.root, self.cache = pathlib.Path(root), {}

    def files(self, rnd, stem):
        d = self.root / rnd / "out" / stem
        if (rnd, stem) not in self.cache:
            md = split((d / f"{stem}.md").read_text(), MD_SEP)[0]
            html = split((d / f"{stem}.html").read_text(), HTML_SEP)[0]
            meta = json.load(open(d / f"{stem}_metadata.json"))
            assert len(md) == len(html) == meta["num_pages"], (rnd, stem)
            self.cache[(rnd, stem)] = (d, md, html, meta)
        return self.cache[(rnd, stem)]

    def page(self, src):
        rnd, rest = src.split("/", 1)
        stem, idx = rest.split(":")[:2]
        d, md, html, meta = self.files(rnd, stem)
        ids = [int(i) for i in idx.split("+")]
        tok = sum(meta["pages"][i]["token_count"] for i in ids)
        return d, "\n\n".join(md[i].strip("\n") for i in ids), "\n".join(html[i] for i in ids), tok


def main(decisions, v4, root, v5):
    v4, v5 = pathlib.Path(v4), pathlib.Path(v5)
    if v5.exists():
        sys.exit(f"{v5} exists -- refusing to overwrite; remove it first")
    shutil.copytree(v4, v5, ignore=shutil.ignore_patterns("_failed"))
    rep = Repairs(root)
    by_tag = {}
    for r in csv.DictReader(open(decisions), delimiter="\t"):
        if r["action"] in ("KEEP_BLANK", "KEEP_MINOR", "KEEP_FIGURE", "TABLE_UNFIXED") or (r["action"] == "ACCEPT" and r["source"] == "old"):
            continue
        by_tag.setdefault(r["tag"], []).append(r)
    counts = {}
    for tag, rows in sorted(by_tag.items()):
        d = v5 / tag / tag
        mdf, htf, mtf = d / f"{tag}.md", d / f"{tag}.html", d / f"{tag}_metadata.json"
        md, mseps = split(mdf.read_text(), MD_SEP)
        html, hseps = split(htf.read_text(), HTML_SEP)
        meta = json.load(open(mtf))
        n = meta["num_pages"]
        assert len(md) == len(html) == n, f"{tag}: md {len(md)} html {len(html)} meta {n}"
        for r in rows:
            p, act, src = int(r["page"]), r["action"], r["source"]
            note = f"<!-- stage4: {act} {src} -->"
            if act in ("ACCEPT", "ACCEPT_CAP", "ACCEPT_TABLE"):
                rd, ptext, phtml, tok = rep.page(src)
                for m in IMG.finditer(ptext + phtml):
                    f = m.group(1) or m.group(2)
                    if (rd / f).exists():
                        shutil.copy2(rd / f, d / f)
                md[p] = f"\n{note}\n\n{ptext.strip(chr(10))}\n"
                html[p] = f"{note}\n{phtml}"
                meta["pages"][p]["token_count"] = tok
            elif act == "SHOWTHROUGH":
                md[p] = f"\n{note}\n"
                html[p] = note
            elif act == "FAINT":
                keep = IMGLINE.findall(md[p])
                md[p] = f"\n{note}\n\n{FAINT}\n" + "".join(f"\n{k}\n" for k in keep)
                html[p] = f"{note}\n<p>{FAINT}</p>" + "".join(HTMLIMG.findall(html[p]))
            elif act == "UNRESOLVED":
                md[p] = f"\n{note}\n\n{WITHHELD}\n"
                html[p] = f"{note}\n<p>{WITHHELD}</p>"
            else:
                sys.exit(f"unknown action {act}")
            meta["pages"][p]["stage4"] = {"action": act, "source": src}
            counts[act] = counts.get(act, 0) + 1
        new_md = join(md, mseps)
        if [int(x) for x in re.findall(r"^(\d+)-{48}$", new_md, re.M)] != list(range(1, n)):
            sys.exit(f"{tag}: page markers broken after patch")
        mdf.write_text(new_md)
        htf.write_text(join(html, hseps))
        json.dump(meta, open(mtf, "w"), indent=2)
    print(f"patched {len(by_tag)} volumes: {counts}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
