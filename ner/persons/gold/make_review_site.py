#!/usr/bin/env python3
"""Builds review/index.html: a self-contained page on which a student records the gold verdicts.

One screen per person: evidence (names as printed, roles, years, places), the proposed Wikidata item and other
candidates, Colonial Office List / planters-registry matches, and 4 sample mentions with snippet + scan link.
The student answers: one person or mixed?; which Wikidata item (proposed / other QID / none / can't tell)?;
does each mention refer to this person? Answers live in the browser (localStorage) and export as a TSV.
The page does not show which decision bucket (auto/review/none) a person came from, so the student's QID is
an independent gold answer for every tier."""
import json, csv, gzip, html, pathlib, re
here = pathlib.Path(__file__).resolve().parent
P = here.parent

def tsv(p):
    return list(csv.DictReader(open(p), delimiter="\t", quoting=csv.QUOTE_NONE)) if p.exists() else []

gp = tsv(here / "gold_profiles.tsv"); gm = tsv(here / "gold_mentions.tsv")
prof = {}
for l in gzip.open(P / "out/profiles.jsonl.gz", "rt"):
    p = json.loads(l); prof[p["pid"]] = p
persons = {r["pid"]: r for r in tsv(P / "out/persons.tsv")}
cands = {}
if (P / "wd/out/candidates.jsonl").exists():
    for l in open(P / "wd/out/candidates.jsonl"):
        r = json.loads(l); cands[r["pid"]] = r
co = {r["pid"]: r for r in tsv(P / "colist/links.tsv")}
pl = {r["pid"]: r for r in tsv(P / "planters/links.tsv")}

HOW = {"explicit": "name printed with initials/first name",
       "norm": "surname here; the full name is printed elsewhere in the article",
       "article": "surname only; linked to the full name in the same article",
       "corpus_unique": "surname only; linked across the journal (only person of that name at the time)",
       "corpus_dominant": "surname only; linked across the journal (by far the most frequent person of that name then)",
       "corpus_honorific": "surname only; linked across the journal by title (e.g. 'Dr.')",
       "pool": "surname only; no full name anywhere in the journal"}

items = []
for r in gp:
    pid = r["pid"]; p = prof[pid]; m = persons.get(pid, {}); c = cands.get(pid, {})
    qid = m.get("wikidata_qid") or ""
    cl = []
    for x in c.get("candidates", []):
        if x["s"]["passes"] or x["qid"] == qid:
            cl.append({"qid": x["qid"], "label": x["label"] or "", "desc": x["desc"] or "",
                       "life": f"{x['birth'] or '?'}–{x['death'] or '?'}" if (x["birth"] or x["death"]) else ""})
    if qid and not any(x["qid"] == qid for x in cl):
        cl.insert(0, {"qid": qid, "label": "", "desc": "(from the Colonial Office List graph)", "life": ""})
    proposed = qid   # the pipeline's final answer only (adjudication may have rejected the first-pass candidate)
    cl.sort(key=lambda x: x["qid"] != proposed)
    k = co.get(pid); t = pl.get(pid)
    items.append({
        "gid": r["gid"], "pid": pid, "name": p["display"], "mentions": p["mentions"],
        "years": f"{p['first']}–{p['last']}", "forms": [s for s, _ in p["surface_forms"][:6]],
        "roles": [f"{a} ({n})" for a, n in p["roles"][:6]], "places": [a for a, _ in p["places"][:5]],
        "proposed": proposed, "candidates": cl[:7],
        "colist": f"{k['co_name']} — {k['co_postings']}" if k else "",
        "planter": t["url"] if t and t["decision"] == "link" else "",
        "ments": [{"how": HOW.get(x["method"], x["method"]), "year": x["year"], "surface": x["surface"],
                   "role": x["role"], "snippet": x["snippet"], "scan": x["scan"], "article": x["article"],
                   "idx": i} for i, x in enumerate(m2 for m2 in gm if m2["pid"] == pid)]})

data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
page = (here / "review_template.html").read_text().replace("/*DATA*/", data)
out = here / "review"; out.mkdir(exist_ok=True)
(out / "index.html").write_text(page)
print(f"review/index.html: {len(items)} people, {sum(len(i['ments']) for i in items)} mentions, "
      f"{len(page)//1024} KB")
