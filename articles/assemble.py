#!/usr/bin/env python3
"""
Assemble articles from skeleton.jsonl + labels: one record per article, linked to pages.

An article runs from an ARTICLE line to the next ARTICLE or SECTION line in the same
issue unit, or to the end of the unit's pages, and never across a change of part
(main -> supplement). Text before the first ARTICLE of a unit becomes an untitled
article only if it has >= 40 words (cover leaves and contents pages fall below that
or are kept, labelled "untitled", so no text is silently dropped).

Provenance: `segments` are (scan page, char_start, char_end) into the document's
output_v6 .md, so every word of `text` can be traced to a page; `pages` carries the
printed folio and the IA image/viewer URLs. The running head line of each page is
left out of `text` (it is page furniture, and repeated in pages[].head).

Usage: assemble.py LABELS.jsonl OUT.jsonl
"""
import csv, json, re, sys, pathlib, collections
ROOT = pathlib.Path.home() / "tropical/output_v6"
COMMENT = re.compile(r"<!--.*?-->", re.S)
ROW = re.compile(r"<tr>.*?</tr>", re.S)
PAGE_CELL = re.compile(r"<td[^>]*>\s*\d{1,3}\s*</td>\s*</tr>$")
LEADER_LINE = re.compile(r"^.{8,}(\.\s*){2,}\s*\d{1,3}\s*$", re.M)


def is_contents(text, words):
    """A printed contents table: rows (or dotted-leader lines) ending in a 1-3 digit page number, the
    numbers non-decreasing, and most rows carrying dotted leaders (".. ..") or a "By <author>".
    1928-45 issues open with one; its department headings must not become sections of the body."""
    if words > 600:
        return False
    rows = ROW.findall(text)
    paged = [r for r in rows if PAGE_CELL.search(r)]
    if paged:
        nums = [int(re.search(r"(\d{1,3})\s*</td>\s*</tr>$", r).group(1)) for r in paged]
        mono = sum(b < a for a, b in zip(nums, nums[1:])) <= 1
        leader = sum(bool(re.search(r"\.\s?\.|\bBy [A-Z]|, by [A-Z]", r)) for r in paged)
        if len(paged) >= 2 and len(paged) >= 0.6 * len(rows) and mono and leader >= 0.5 * len(paged):
            return True
    lines = LEADER_LINE.findall(text)
    return len(lines) >= 3 and len(lines) >= 0.5 * max(1, text.count("\n"))


def main(labels_path, out_path):
    pages = {(r["doc"], int(r["page"])): r for r in csv.DictReader(open("pages.tsv"), delimiter="\t")}
    units = {json.loads(l)["unit"]: json.loads(l) for l in open("skeleton.jsonl")}
    labs = {json.loads(l)["unit"]: {int(k): v for k, v in json.loads(l)["labels"].items()} for l in open(labels_path)}
    parts = {}
    for r in csv.DictReader(open("page_issue.tsv"), delimiter="\t"):
        parts[(r["doc"], int(r["page"]))] = r["part"]
    # Canonical copy per issue (canonical.py). A volume-level unit (issue unresolved, e.g. vol096's
    # Vol. 97 section) is canonical only if no other document holds issues of that volume.
    canon, vol_docs = {}, collections.defaultdict(set)
    for r in csv.DictReader(open("canonical.tsv"), delimiter="\t"):
        canon[(r["volume"], r["issue"], r["doc"])] = r["canonical"] == "1"
        vol_docs[r["volume"]].add(r["doc"])
    def is_canon(U):
        k = (U["volume"], U["issue"], U["doc"])
        return canon[k] if k in canon else not (vol_docs[U["volume"]] - {U["doc"]})
    out = open(out_path, "w"); texts = {}; stats = collections.Counter()
    for u, lab in labs.items():
        U = units[u]; doc = U["doc"]
        if doc not in texts:
            texts.clear(); texts[doc] = next((ROOT / doc).glob("*/*.md")).read_text(encoding="utf-8", errors="replace")
        md = texts[doc]
        cands = U["cands"]
        upages = U["pages"]
        # Boundaries: (offset, page, kind, cand index)
        starts = []
        section = ""; section_off = -1
        for c in cands:
            L = lab.get(c["id"], "OTHER")
            if L in ("ARTICLE", "SECTION"):
                starts.append((c["offset"], c["page"], L, c["id"]))
        first = int(pages[(doc, upages[0])]["char_start"])
        end_all = int(pages[(doc, upages[-1])]["char_end"])
        bounds = [(first, upages[0], "LEAD", None)] + starts + [(end_all, upages[-1], "END", None)]
        n = 0; unit_recs = []
        for (a, pa, kind, cid), (b, pb, _, _) in zip(bounds, bounds[1:]):
            if kind == "SECTION":
                section = cands[cid]["text"]; section_off = a
                # Its own text (until the next title) is kept below as an article titled by the
                # section ("Editorial", "Correspondence") when it has >= 40 words; never dropped silently.
            title = byline = ""
            if kind == "ARTICLE":
                title = cands[cid]["text"]
                for c in cands[cid + 1:cid + 4]:
                    L = lab.get(c["id"], "OTHER")
                    if L == "CONT" and not byline:
                        title += " " + c["text"]
                    elif L == "BYLINE" and not byline:
                        byline = c["text"]
                    elif L in ("ARTICLE", "SECTION"):
                        break
            # Segments: walk unit pages overlapping [a, b); a change of part (main -> supplement)
            # starts a new record rather than running one article across both -- text is never dropped.
            groups = []                              # [part, [segs], [pieces]]
            for pg in upages:
                pr = pages[(doc, pg)]
                s, e = int(pr["char_start"]), int(pr["char_end"])
                if e <= a or s >= b:
                    continue
                s2, e2 = max(s, a), min(e, b)
                body = md[s2:e2]
                if s2 == s and pr["head"]:          # drop the running head line
                    lines = body.split("\n", 1)
                    if lines[0].replace("#", "").strip().startswith(pr["head"][:8]) or not lines[0].strip():
                        k = body.find(pr["line1"][:20]) if pr["line1"] else -1
                        if k >= 0:
                            nl = body.find("\n", k)
                            s2 = s2 + (nl + 1 if nl >= 0 else len(body))
                if not COMMENT.sub("", md[s2:e2]).strip():
                    continue                         # nothing of this article on the page (only its head)
                p = parts[(doc, pg)]
                if not groups or groups[-1][0] != p:
                    groups.append([p, [], []])
                groups[-1][1].append([pg, s2, e2])
                groups[-1][2].append(COMMENT.sub("", md[s2:e2]).strip())
            first_id = None
            for gi, (gpart, segs, pieces) in enumerate(groups):
                text = "\n\n".join(x for x in pieces if x)
                words = len(re.findall(r"[A-Za-z]{2,}", re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)))
                if gi == 0 and kind in ("LEAD", "SECTION") and words < 40:
                    stats[f"{kind.lower()}_short_words"] += words      # cover leaves / bare section headings
                    continue
                n += 1
                rid = f"{doc}#{U['issue']}#{n:03d}"
                if gi == 0:
                    t, by = (section if kind == "SECTION" else title) or "(untitled)", byline
                    first_id = rid
                else:
                    t, by = "(untitled)", ""
                    stats["part_split_records"] += 1
                rec = {
                    "_a": a, "_b": b, "_sec_off": section_off,
                    "id": rid, "doc": doc, "ia_id": pages[(doc, upages[0])]["ia_id"],
                    "volume": int(U["volume"]), "issue": U["issue"], "part": gpart, "section": section,
                    "title": t, "byline": by, "words": words,
                    "split_from": first_id if gi else None, "canonical": is_canon(U),
                    "pages": [{"page": pg, "folio": pages[(doc, pg)]["folio"], "image_url": pages[(doc, pg)]["image_url"],
                               "viewer_url": pages[(doc, pg)]["viewer_url"]} for pg, _, _ in segs],
                    "segments": segs, "text": text,
                }
                unit_recs.append(rec)
        # Contents tables: merge consecutive fragments into one record; blank the section of any record
        # whose section heading was printed inside a contents table (it names a department of the
        # contents, not of the body that follows).
        merged = []; spans = []
        for rec in unit_recs:
            near_start = rec["segments"][0][0] in upages[:4]          # contents tables open an issue
            if near_start and is_contents(rec["text"], rec["words"]):
                rec["kind"] = "contents"; rec["title"] = "Contents"; rec["section"] = ""; rec["byline"] = ""
                spans.append((rec["_a"], rec["_b"]))
                if merged and merged[-1].get("kind") == "contents" and merged[-1]["part"] == rec["part"]:
                    m = merged[-1]
                    m["text"] += "\n\n" + rec["text"]; m["words"] += rec["words"]; m["_b"] = rec["_b"]
                    m["segments"] += rec["segments"]
                    seen = {p["page"] for p in m["pages"]}
                    m["pages"] += [p for p in rec["pages"] if p["page"] not in seen]
                    stats["contents_fragments_merged"] += 1
                    continue
                stats["contents_records"] += 1
            merged.append(rec)
        for i, rec in enumerate(merged):
            if rec.get("kind") != "contents" and any(a <= rec["_sec_off"] < b for a, b in spans):
                rec["section"] = ""; stats["section_reset_after_contents"] += 1
            for k in ("_a", "_b", "_sec_off"):
                rec.pop(k, None)
            rec.setdefault("kind", "article")                   # ids keep their numbers (split_from points at them)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            stats["articles"] += 1; stats["words"] += rec["words"]; stats["canonical"] += rec["canonical"]
    print(dict(stats), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
