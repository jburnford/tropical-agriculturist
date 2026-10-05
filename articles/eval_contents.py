#!/usr/bin/env python3
"""
Score article-start labels against printed contents tables (gold_contents.tsv).

For every gold row (issue, title, start folio) in a unit we hold:
  ceiling  -- the gold title appears in some skeleton candidate of the unit at all
              (if not, no labelling can find it: OCR dropped or merged the title);
  title    -- some candidate labelled ARTICLE matches the gold title;
  strict   -- ... and sits on a scan page whose folio is the gold folio (or the
              page before, for titles at the foot of a page).
Title match: >= 60% of the gold title's content words (len >= 3) occur in the
candidate text plus the next candidate's text (titles split over two lines).
Also reports predicted ARTICLE count per unit vs gold count (over-segmentation
is expected: contents list only the main items, not every short note).

Usage: eval_contents.py LABELS.jsonl   ({unit, labels: {id: LABEL}} per line)
       eval_contents.py --baseline     (h2/h3 = ARTICLE)
"""
import csv, json, re, sys, collections

STOP = set("the and for with from into its their this that are was were has have been of on in to by at an a as or".split())


def words(s):
    return [w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in STOP]


def match(gold, text):
    g = words(gold)
    if not g:
        return False
    t = set(words(text))
    return sum(w in t for w in g) / len(g) >= 0.6


def is_start(cands, lab, i):
    """ARTICLE, SECTION with its own text, or a CONT line continuing an ARTICLE line (two-line title)."""
    L = lab.get(cands[i]["id"])
    if L == "ARTICLE":
        return True
    if L == "SECTION":
        return own_text(cands, lab, i)
    if L != "CONT":
        return False
    for d in reversed(cands[max(0, i - 3):i]):   # the ARTICLE line it continues (a BYLINE/OTHER may sit between)
        if lab.get(d["id"]) in ("ARTICLE", "SECTION"):
            return lab.get(d["id"]) == "ARTICLE"
        if lab.get(d["id"]) != "CONT" and d["page"] != cands[i]["page"]:
            return False
    return False


def own_text(cands, lab, i):
    """A SECTION line that is followed by its own prose (no ARTICLE/SECTION within the next
    3 candidates on the same page) is also an article: "Editorial", "Correspondence"."""
    for c in cands[i + 1:i + 4]:
        if c["page"] != cands[i]["page"]:
            break
        if lab.get(c["id"]) in ("ARTICLE", "SECTION"):
            return False
    return True


def main():
    units = {json.loads(l)["unit"]: json.loads(l) for l in open("skeleton.jsonl")}
    if sys.argv[1] == "--baseline":
        labels = {u: {c["id"]: ("ARTICLE" if c["kind"] in ("h2", "h3") else "OTHER") for c in U["cands"]}
                  for u, U in units.items()}
    else:
        labels = {}
        for l in open(sys.argv[1]):
            j = json.loads(l)
            labels[j["unit"]] = {int(k): v for k, v in j["labels"].items()}
    gold = collections.defaultdict(list); seen = set()
    for r in csv.DictReader(open("gold_contents.tsv"), delimiter="\t"):
        k = (r["volume"], r["issue"], r["title"].lower(), r["folio"])
        if k not in seen:                    # both copies of a duplicated issue print the same contents
            seen.add(k); gold[(r["volume"], r["issue"])].append(r)
    tot = collections.Counter(); per = []
    for u, lab in labels.items():
        U = units[u]
        # Quarterlies are keyed "1942-01/03" by tag, "1942-01" by their masthead; a volume-level
        # unit ("1941-07/12": issue unknown) is not one issue and is not scored.
        quarterly = "/" in U["issue"] and int(U["volume"]) >= 98
        if quarterly:      # "1942-01/03" by tag; the masthead date may name any month of the quarter
            y, m1, m2 = U["issue"][:4], int(U["issue"][5:7]), int(U["issue"][8:10])
            g = [r for (v, k), rows in gold.items() if v == U["volume"] and k[:4] == y and m1 <= int(k[5:7]) <= m2 for r in rows]
        else:
            g = gold.get((U["volume"], U["issue"]))
        if not g:
            continue
        cands = U["cands"]
        art = [c for c in cands if is_start(cands, lab, c["id"])]
        sec = {}; cur = ""                       # section in force at each candidate
        for c in cands:
            if lab.get(c["id"]) == "SECTION":
                cur = c["text"]
            sec[c["id"]] = cur
        nxt = {c["id"]: (cands[c["id"] + 1]["text"] if c["id"] + 1 < len(cands) else "") for c in cands}
        hit = collections.Counter()
        for r in g:
            f = r["folio"]
            ceil = any(match(r["title"], c["text"] + " " + nxt[c["id"]]) for c in cands)
            tm = [c for c in art if match(r["title"], c["text"] + " " + nxt[c["id"]])]
            pages_ok = {c["page"] for c in cands if c["folio"] in (f, str(int(f) - 1))}
            st = [c for c in tm if c["folio"] in (f, str(int(f) + 1)) or c["page"] in pages_ok]
            nofolio = [c for c in tm if not c["folio"]]
            hit["gold"] += 1; hit["ceiling"] += ceil; hit["title"] += bool(tm); hit["strict"] += bool(st)
            hit["title_nofolio"] += bool(tm) and not st and bool(nofolio)
            # contents say "Editorial"; the editorial is found under its own subtitle in that section
            hit["section"] += not tm and any(match(r["title"], sec[c["id"]]) and (c["folio"] == f or not c["folio"]) for c in art)
        hit["pred"] = sum(lab.get(c["id"]) != "CONT" for c in art)   # a CONT line is part of a start, not another one
        tot.update(hit)
        per.append((u, hit))
    for u, h in per:
        print(f"{u[:70]:70} gold {h['gold']:3} ceil {h['ceiling']:3} title {h['title']:3} strict {h['strict']:3} pred {h['pred']:4}")
    G = tot["gold"] or 1
    print(f"\nUNITS {len(per)}  GOLD {tot['gold']}  ceiling {tot['ceiling']/G:.1%}  title {tot['title']/G:.1%}"
          f"  strict {tot['strict']/G:.1%}  (+{tot['title_nofolio']/G:.1%} title on unfoliated page)  pred/gold {tot['pred']/G:.2f}"
          f"\n  title or found under a matching section heading on that page: {(tot['title'] + tot['section'])/G:.1%}")


if __name__ == "__main__":
    main()
