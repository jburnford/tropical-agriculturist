#!/usr/bin/env python3
"""
Post-pass over heading labels: fix ARTICLE starts that own no text.

An ARTICLE line with fewer than MIN_OWN words of its own (its text up to the next
ARTICLE/SECTION, excluding the heading itself, page markers, images, HTML) is one of:
  * a SIGNATURE at the foot of the piece before it ("W. FERGUSON.", "A PLANTER.",
    '"IGNOTUS."', "PEPPERCORN." under the Upcountry Planting Report) -> relabelled OTHER,
    so its line joins the previous article;
  * a TITLE whose body sits under the next ARTICLE line on the same page
    ("BOARD OF AGRICULTURE." / "MINUTES OF THE 40TH MEETING.") -> the next line is
    relabelled CONT, so the two lines form one title;
  * anything else is left alone.
Signature tests (any): initials + surname; "A/AN <WORD...>" or quoted pseudonym; a short
line (<= 4 words, no topic words) ending a piece that reads as a letter ("SIR,", "To the
Editor", "Yours ..."); or a text that recurs >= 3 times as a no-body line under one and
the same preceding title (a column's signature).
Writes labels + a decisions TSV for review. Usage: merge_stubs.py LABELS_IN LABELS_OUT DECISIONS.tsv
"""
import csv, json, re, sys, pathlib, collections
ROOT = pathlib.Path.home() / "tropical/output_v6"
MIN_OWN = 4
STRIP = re.compile(r"<!--.*?-->|!\[[^\]]*\]\([^)]*\)|<[^>]+>|^\d+-{20,}$", re.S | re.M)
W = lambda s: re.findall(r"[A-Za-z]{2,}", s)
INITIALS = re.compile(r"^\(?(?:[A-Z][a-z]{0,2}\.\s*){1,4}[A-Z][A-Za-z'’\-]+(?:,\s*[A-Za-z.,& ]{1,40})?[.,]?\)?$")
# "Claxheugh, Sunderland, 30th May, 1881." / "London, January 3, 1891." -- a dateline under a signature is part of it
DATELINE = re.compile(r"^\W*[A-Z][A-Za-z.'’ \-]{2,40},?\s+(?:\d{1,2}(?:st|nd|rd|th)?,?\s+)?[A-Z][a-z]{2,9}\.?,?\s*(?:\d{1,2}(?:st|nd|rd|th)?,?\s*)?(?:\d{4})?\.?\W*$", re.M)
PERSON = (r"(PLANTER|OBSERVER|SPORTSMAN|SUBSCRIBER|READER|CORRESPONDENT|FRIEND|AGRICULTURIST|PROPRIETOR|MERCHANT|BROKER|"
          r"VISITOR|TRAVELLER|RESIDENT|SUFFERER|LOVER|ENQUIRER|INQUIRER|STUDENT|NATIVE|SETTLER|GROWER|CULTIVATOR|FARMER|"
          r"GARDENER|ENGINEER|CHEMIST|SURVEYOR|WELL-WISHER|LOOKER-ON|SUPERINTENDENT|MANAGER|COLONIST|COFFEESHIP|HAND|MAN)")
PSEUD = re.compile(r"^\"?(AN? |ANOTHER |OLD |YOUNG )?[A-Z][A-Z\-' ]{0,30}" + PERSON + r"\.?\"?,?$|^[“\"][A-Z][A-Za-z .\-]+[”\"]\.?$|^\(?Signed\)?\b")
ROLE = re.compile(r"^\(?(Hon\.? |Acting |Assistant |Asst\. )?(Secretary|Chairman|Director|Superintendent|Manager|Curator|Agent|Government Agent|Editor|Proprietor)\b")
LETTER = re.compile(r"\bSIR,|\bSir,—|DEAR SIR|To the Editor|Yours (truly|faithfully|obediently|&c)", re.I)
TOPIC = set("products product insects insect research scheme disease diseases acacia figs banana coconut coconuts health "
            "cane canes new company companies association society board meeting minutes exhibition show garden gardens "
            "london ceylon india java sumatra straits australia africa america season sale sales prices price "
            "manufacture manure manures soil soils seed seeds tree trees crop crops estate estates".split()) | set("the of and in for on tea coffee ceylon india indian cultivation planting notes report editorial "
            "miscellaneous meteorological agricultural agriculture rubber cacao cocoa sugar cotton fibre fibres "
            "oils fats pests sanitation plant plants culture industry industries trade market rates review reviews "
            "correspondence news items general various produce finance returns return".split())


def main(lin, lout, ldec):
    units = {json.loads(l)["unit"]: json.loads(l) for l in open("skeleton.jsonl")}
    pages = {(r["doc"], int(r["page"])): r for r in csv.DictReader(open("pages.tsv"), delimiter="\t")}
    labs = [json.loads(l) for l in open(lin)]
    texts = {}
    stubs = []                                   # (unit, idx in bnd, cand, prev, nxt, own, letter)
    for j in labs:
        U = units[j["unit"]]; lab = {int(k): v for k, v in j["labels"].items()}; cands = U["cands"]; doc = U["doc"]
        if doc not in texts:
            texts.clear(); texts[doc] = next((ROOT / doc).glob("*/*.md")).read_text(encoding="utf-8", errors="replace")
        md = texts[doc]
        bnd = [c for c in cands if lab.get(c["id"]) in ("ARTICLE", "SECTION")]
        end_all = int(pages[(doc, U["pages"][-1])]["char_end"])
        for i, c in enumerate(bnd):
            if lab.get(c["id"]) != "ARTICLE":
                continue
            nb = bnd[i + 1] if i + 1 < len(bnd) else None
            a, b = c["offset"], nb["offset"] if nb else end_all
            body = STRIP.sub(" ", md[a:b])
            own = len(W(body)) - len(W(c["text"]))
            t0 = c["text"].strip(" *")
            siglike = bool(INITIALS.match(t0) or PSEUD.match(t0) or ROLE.match(t0))
            if own >= MIN_OWN:
                # a signature followed by its dateline ("Claxheugh, Sunderland, 30th May, 1881.") still owns nothing
                if not (siglike and len(W(DATELINE.sub(" ", body))) - len(W(c["text"])) < MIN_OWN):
                    continue
                own = -1                                       # mark: only the backward merge may use this
            prev = next((d for d in reversed(bnd[:i]) if lab.get(d["id"]) == "ARTICLE" and d["part"] == c["part"]), None)
            letter = bool(prev) and bool(LETTER.search(md[prev["offset"]:a]))
            stubs.append((j, lab, c, prev, nb, own, letter))
    # recurring column signatures: same no-body text >= 3 times, >= 2/3 under one preceding title
    by_text = collections.defaultdict(collections.Counter); key_topical = {}
    for j, lab, c, prev, nb, own, letter in stubs:
        if prev:
            key = re.sub(r"[^A-Za-z]", "", c["text"]).upper()
            by_text[key][re.sub(r"[^A-Za-z]", "", prev["text"]).upper()[:20]] += 1   # letters only: UP-COUNTRY = UPCOUNTRY
            key_topical[key] = bool({w.lower() for w in W(c["text"])} & TOPIC)
    column_sig = {t for t, cnt in by_text.items() if sum(cnt.values()) >= 3 and cnt.most_common(1)[0][1] >= 2 / 3 * sum(cnt.values())
                  and not key_topical[t]}
    dept = {t for t, cnt in by_text.items() if sum(cnt.values()) >= 3 and len(cnt) >= 2
            and cnt.most_common(1)[0][1] < 2 / 3 * sum(cnt.values())} - column_sig
    dec = csv.writer(open(ldec, "w"), delimiter="\t")
    dec.writerow(["unit", "page", "kind", "text", "own_words", "decision", "reason", "prev_title", "next_title"])
    counts = collections.Counter(); changed = collections.defaultdict(dict)
    for j, lab, c, prev, nb, own, letter in stubs:
        t = c["text"].strip(" *"); key = re.sub(r"[^A-Za-z]", "", t).upper()
        words = [w.lower() for w in W(t)]
        topical = bool(set(words) & TOPIC)
        reason = None
        question = t.rstrip(" .").endswith("?") and len(words) <= 5
        heading_like = not question and (len(words) >= 4 or topical or key in dept or t.endswith(":") or bool(re.search(r"\(\d+\)|\bNo\.|\b[IVX]+\.$", t)))
        if prev and INITIALS.match(t): reason = "initials+surname"
        elif prev and ROLE.match(t): reason = "role-line"
        elif prev and key in column_sig: reason = "column-signature"
        elif prev and PSEUD.match(t) and key not in dept: reason = "pseudonym"
        elif prev and letter and len(words) <= 3 and not heading_like: reason = "letter-signature"
        maybe_sig = PSEUD.match(t) or INITIALS.match(t) or ROLE.match(t) or question or (len(words) <= 3 and not heading_like)
        if reason:
            d = "BACK"; changed[j["unit"]][c["id"]] = "OTHER"
        elif own >= 0 and nb and lab.get(nb["id"]) == "ARTICLE" and nb["page"] == c["page"] and heading_like and not maybe_sig \
                and not INITIALS.match(nb["text"].strip(" *")):
            d = "FORWARD"; reason = "heading+title same page"; changed[j["unit"]][nb["id"]] = "CONT"
        else:
            d = "KEEP"; reason = "ambiguous" if maybe_sig else "no next title on page"
        counts[d] += 1
        dec.writerow([j["unit"], c["page"], c["kind"], t[:80], own, d, reason, (prev or {}).get("text", "")[:60], (nb or {}).get("text", "")[:60]])
    with open(lout, "w") as out:
        for j in labs:
            if j["unit"] in changed:
                j = dict(j); j["labels"] = dict(j["labels"])
                for cid, L in changed[j["unit"]].items():
                    j["labels"][str(cid)] = L
            out.write(json.dumps(j) + "\n")
    print(f"no-body ARTICLE starts: {len(stubs)}  {dict(counts)}  column signatures: {sorted(column_sig)}", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
