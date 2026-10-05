#!/usr/bin/env python3
"""Gold set for Jim: 100 profiles from the grounding tranche (>=10 mentions), stratified by Wikidata decision
(35 auto, 35 review, 30 none), to measure
(a) profile purity: are the mentions the build attached by inference really this person, and
(b) Wikidata precision: is the auto/review QID right.

gold_profiles.tsv  one row per profile: evidence + the Wikidata decision; fill verdict_* columns
gold_mentions.tsv  up to 4 sampled mentions per profile, preferring inferred links (article, corpus_*),
                   each with a text snippet and the scan URL; fill the verdict column
Verdict codes: y = right, n = wrong, ? = can't tell from the evidence. correct_qid: the right QID if known, or
"none" if the person is not in Wikidata."""
import json, gzip, re, random, collections, pathlib
random.seed(20261005)
here = pathlib.Path(__file__).resolve().parent
P = here.parent
profiles = [json.loads(l) for l in gzip.open(P / "out/profiles.jsonl.gz", "rt")]
tranche = [p for p in profiles if p["mentions"] >= 10]
wd = {}
if (P / "wd/out/candidates.jsonl").exists():
    for l in open(P / "wd/out/candidates.jsonl"):
        r = json.loads(l); wd[r["pid"]] = r

# stratified by the Wikidata decision so auto precision, review quality and missed matches are all measured
by_dec = collections.defaultdict(list)
for p in tranche:
    by_dec[wd.get(p["pid"], {}).get("decision", "none")].append(p)
strata = [(by_dec["auto"], 35), (by_dec["review"], 35), (by_dec["none"], 30)]
pick = []
for pool, k in strata:
    pick += random.sample(pool, min(k, len(pool)))
pids = {p["pid"] for p in pick}

ments = collections.defaultdict(list)
for l in gzip.open(P / "out/mentions.tsv.gz", "rt"):
    f = l.rstrip("\n").split("\t")
    if len(f) > 9 and f[8] in pids:
        ments[f[8]].append({"article": f[0], "idx": f[1], "year": f[2], "text": f[3], "role": f[5], "method": f[9]})
PREF = ["corpus_dominant", "corpus_unique", "corpus_honorific", "pool", "article", "norm", "explicit"]
sample = {}
for pid in pids:
    ms = ments[pid]; random.shuffle(ms)
    chosen = []
    for m in PREF:                       # one per inferred method first, then fill
        chosen += [x for x in ms if x["method"] == m][:1]
    chosen += [x for x in ms if x not in chosen]
    sample[pid] = chosen[:4]
need = {m["article"] for v in sample.values() for m in v}
art = {}
for f in (P.parent.parent / "articles/by_year").glob("articles_*.jsonl.gz"):
    for l in gzip.open(f, "rt", encoding="utf-8"):
        a = json.loads(l)
        if a["id"] in need:
            art[a["id"]] = (re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", a["text"])).replace("|  |", "|"), (a.get("pages") or [{}])[0].get("viewer_url", ""), a.get("title", ""))

def snippet(text, surf):
    i = text.find(surf.strip())
    if i < 0:
        last = surf.split()[-1] if surf.split() else surf
        i = text.find(last)
    if i < 0:
        return "(surface not found in text)"
    a, b = max(0, i - 220), min(len(text), i + len(surf) + 220)
    return ("…" if a else "") + text[a:i] + "[[" + text[i:i + len(surf)] + "]]" + text[i + len(surf):b] + ("…" if b < len(text) else "")

order = sorted(pick, key=lambda p: -p["mentions"])
with open(here / "gold_profiles.tsv", "w") as fp, open(here / "gold_mentions.tsv", "w") as fm:
    fp.write("gid\tpid\tkind\tdisplay\tmentions\tyears\tsurface_forms\troles\twd_decision\twd_qid\twd_label\twd_description\t"
             "wd_other_candidates\tverdict_one_person\tverdict_qid\tcorrect_qid\tnote\n")
    fm.write("gid\tpid\tdisplay\tmethod\tyear\tsurface\trole\tsnippet\tscan\tarticle\tverdict\tnote\n")
    for n, p in enumerate(order, 1):
        g = f"G{n:03d}"; w = wd.get(p["pid"], {})
        best = next((c for c in w.get("candidates", []) if c["qid"] == w.get("qid")), {})
        others = [f"{c['qid']} {c['label']} ({(c['desc'] or '')[:40]})" for c in w.get("candidates", [])
                  if c["s"]["passes"] and c["qid"] != w.get("qid")][:3]
        fp.write("\t".join(str(x).replace("\t", " ") for x in [
            g, p["pid"], p["kind"], p["display"], p["mentions"], f"{p['first']}-{p['last']}",
            " | ".join(s for s, _ in p["surface_forms"][:5]), " | ".join(r for r, _ in p["roles"][:5]),
            w.get("decision", "not run"), w.get("qid") or "", best.get("label") or "", best.get("desc") or "",
            " ; ".join(others), "", "", "", ""]) + "\n")
        for m in sample[p["pid"]]:
            t, url, title = art.get(m["article"], ("", "", ""))
            fm.write("\t".join(str(x).replace("\t", " ") for x in [
                g, p["pid"], p["display"], m["method"], m["year"], m["text"], m["role"], snippet(t, m["text"]), url,
                m["article"], "", ""]) + "\n")
print(f"{len(order)} profiles, {sum(len(v) for v in sample.values())} mentions; methods:",
      dict(collections.Counter(m["method"] for v in sample.values() for m in v)))
