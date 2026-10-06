#!/usr/bin/env python3
"""Builds review/index.html: a self-contained page on which the RA records the gold verdicts.

One screen per person: evidence (names as printed, roles, years, places), the proposed Wikidata item (the
pipeline's FINAL asserted QID, if any) and every other candidate with its real provenance, Colonial Office List /
planters-registry matches with their status, and 4 sampled records with the located scan page, links to all the
article's pages, and a snippet. Answers live in the browser under a storage key that includes the dataset
fingerprint (manifest.json), and every exported row carries the fingerprint and the record's stable key, so a
regenerated page can never silently attach old answers to different material. The page does not show the
stratum or which stage proposed the QID beyond its provenance labels."""
import json, csv, gzip, pathlib, re, sys
here = pathlib.Path(__file__).resolve().parent
P = here.parent
sys.path.insert(0, str(P / "wd"))

def tsv(p):
    return list(csv.DictReader(open(p), delimiter="\t", quoting=csv.QUOTE_NONE)) if p.exists() else []

manifest = json.load(open(here / "manifest.json"))
gp = tsv(here / "gold_profiles.tsv"); gm = tsv(here / "gold_mentions.tsv")
prof = {}
for l in gzip.open(P / "out/profiles.jsonl.gz", "rt"):
    p = json.loads(l); prof[p["pid"]] = p
persons = {r["pid"]: r for r in tsv(P / "out/persons.tsv")}
cands = {}
for l in open(P / "wd/out/candidates.jsonl"):
    r = json.loads(l); cands[r["pid"]] = r
co = {r["pid"]: r for r in tsv(P / "colist/links.tsv")}
pl = {r["pid"]: r for r in tsv(P / "planters/links.tsv")}
slug = {r["id"]: r["slug"] for r in tsv(P.parent / "gazetteer/planters_index.tsv")}
ent = {}
for l in open(P / "wd/cache/entities_v3.jsonl"):
    r = json.loads(l); ent[r["k"]] = r["v"]

PROV = {"wd_auto": "found by search; accepted by the matching rules",
        "model_adjudicated": "chosen by a model after checking Wikidata (not yet checked by a person)",
        "colist_kg": "from the Colonial Office List database",
        "wd review, not adjudicated": "found by search; not confirmed",
        "model MIXED": "a model's best guess, but it judged the evidence mixed",
        "model UNSURE": "a model's best guess, but it was unsure",
        "model NONE": "rejected by a model",
        "stale model decision": "an earlier model decision (profile has since changed)"}

def life(e):
    return f"{e.get('birth') or '?'}–{e.get('death') or '?'}" if (e.get("birth") or e.get("death")) else ""

items, missing = [], set()
for r in gp:
    pid = r["pid"]; p = prof[pid]; f = persons.get(pid, {})
    final_q = f.get("wikidata_qid", "")
    cl = {}
    def add(q, label, desc, lf, why):
        c = cl.setdefault(q, {"qid": q, "label": label, "desc": desc, "life": lf, "prov": []})
        if why and why not in c["prov"] and not any(why in x for x in c["prov"]):
            c["prov"].append(why)
        if not c["label"] and label: c.update(label=label, desc=desc, life=lf)
    if final_q:
        for s in f.get("qid_source", "").split("+"):
            add(final_q, "", "", "", PROV.get(s, s))
    for x in f.get("candidate_qids", "").split(" ; "):
        m = re.match(r"(Q\d+) \((.+)\)", x.strip())
        if m:
            add(m.group(1), "", "", "", PROV.get(m.group(2), m.group(2)))
    for x in cands.get(pid, {}).get("candidates", []):
        if x["s"]["passes"]:
            add(x["qid"], x["label"] or "", x["desc"] or "", life(x), "found by search")
    for c in cl.values():
        e = ent.get(c["qid"])
        if e and not e.get("missing") and not c["label"]:
            c.update(label=e["label"], desc=e["desc"], life=life(e))
        if not c["label"]:
            missing.add(c["qid"])
    k = co.get(pid); t = pl.get(pid)
    colist = None
    if k:
        st = ("matched" if f.get("colist_person_id") else "matched, but withheld: the profile may mix several people") \
            if k["decision"] == "auto" else "possible match only (not confirmed)"
        colist = {"text": f"{k['co_name']} — {k['co_postings']}", "status": st}
    planter = None
    if t:
        ids = [i.strip() for i in t["planter_ids"].split(";") if i.strip()]
        urls = [f"https://www.historyofceylontea.com/tea-planters/planters-registry/{slug.get(i, '')}--{i}.html" for i in ids]
        st = ("matched" if f.get("planter_id") else "matched, but withheld: the profile may mix several people") \
            if t["decision"] == "link" else "possible records (several fit; not confirmed)"
        planter = {"urls": urls, "status": st}
    ms = [m for m in gm if m["pid"] == pid]
    items.append({
        "gid": r["gid"], "pid": pid, "name": p["display"], "mentions": p["mentions"],
        "years": f"{p['first']}–{p['last']}", "forms": [s for s, _ in p["surface_forms"][:6]],
        "roles": [f"{a} ({n})" for a, n in p["roles"][:6]], "places": [a for a, _ in p["places"][:5]],
        "proposed": final_q, "candidates": sorted(cl.values(), key=lambda c: c["qid"] != final_q)[:8],
        "colist": colist, "planter": planter,
        "ments": [{"key": m["mention_key"], "how": m["method"], "year": m["year"], "surface": m["surface"],
                   "role": m["role"], "snippet": m["snippet"], "scan": m["scan"], "page": m["page"], "note": m["locate_note"],
                   "pages": [x.split("=", 1) for x in m["all_scans"].split()], "idx": i} for i, m in enumerate(ms)]})

if missing:   # labels for QIDs not in the cache: read their statements (known QIDs only; never a search)
    import mcp_client as mcp
    mcp.init()
    q = " ".join("wd:" + x for x in sorted(missing))
    txt = mcp.call("execute_sparql", K=200, sparql=f"""SELECT ?item ?lab ?desc (MIN(YEAR(?b)) AS ?birth) (MIN(YEAR(?d)) AS ?death) WHERE {{
      VALUES ?item {{ {q} }} OPTIONAL {{ ?item rdfs:label ?lab FILTER(lang(?lab) IN ("en", "mul")) }}
      OPTIONAL {{ ?item schema:description ?desc FILTER(lang(?desc)="en") }}
      OPTIONAL {{ ?item wdt:P569 ?b }} OPTIONAL {{ ?item wdt:P570 ?d }} }} GROUP BY ?item ?lab ?desc""")
    lines = txt.splitlines(); head = lines[0].split(";")
    got = {}
    for line in lines[1:]:
        f = line.split(";")
        if len(f) > len(head):
            k = head.index("desc"); x = len(f) - len(head); f = f[:k] + [";".join(f[k:k + x + 1])] + f[k + x + 1:]
        if len(f) == len(head):
            d = dict(zip(head, f)); got[d["item"]] = d
    for it in items:
        for c in it["candidates"]:
            d = got.get(c["qid"])
            if d and not c["label"]:
                c.update(label=d["lab"].strip('"'), desc=d["desc"].strip('"'),
                         life=f"{d['birth'] or '?'}–{d['death'] or '?'}" if (d["birth"] or d["death"]) else "")

payload = {"dataset": manifest["dataset"], "items": items}
data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
page = (here / "review_template.html").read_text().replace("/*DATA*/", data)
out = here / "review"; out.mkdir(exist_ok=True)
(out / "index.html").write_text(page)
unl = sum(1 for it in items for c in it["candidates"] if not c["label"])
print(f"review/index.html: dataset {manifest['dataset']}, {len(items)} people, {sum(len(i['ments']) for i in items)} "
      f"mentions, {len(page)//1024} KB; labels fetched for {len(missing)} QIDs; still unlabelled: {unl}")
