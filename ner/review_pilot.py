#!/usr/bin/env python3
"""Review the NER pilot: stats by type, gazetteer hit rates, and an HTML with mentions highlighted.
Usage: review_pilot.py pilot_articles.jsonl pilot_mentions.jsonl pilot_review.html"""
import json, re, sys, csv, html, collections, pathlib
arts = {json.loads(l)["id"]: json.loads(l) for l in open(sys.argv[1])}
res = [json.loads(l) for l in open(sys.argv[2])]
G = pathlib.Path(__file__).resolve().parent / "gazetteer"
# gazetteers: planter surnames+initials from slugs; estate names; col_matching persons and Ceylon places
def slug_keys(slug):
    parts = [p for p in slug.split("-") if p]
    words = [p for p in parts if len(p) > 1]; inits = "".join(p[0] for p in parts if len(p) == 1)
    return {(w.lower(), inits) for w in words}      # (surname candidate, initials) - order unknown
planters = collections.defaultdict(list)
for r in csv.DictReader(open(G / "planters_index.tsv"), delimiter="\t"):
    for k in slug_keys(r["slug"]): planters[k].append(r["id"])
estates = collections.defaultdict(list)
for r in csv.DictReader(open(G / "estates_index.tsv"), delimiter="\t"):
    if r["name_from_slug"]: estates[r["name_from_slug"].lower()].append(r["id"])
CM = pathlib.Path.home() / "col_matching/data/kg/graph_stage3"
cm_persons = collections.defaultdict(list); cm_places = {}
try:
    for l in open(CM / "persons.jsonl"):
        p = json.loads(l); s = (p.get("surname") or "").lower(); g = p.get("given_names") or ""
        inits = "".join(w[0] for w in re.findall(r"[A-Za-z]+", g) if w.lower() not in ("sir", "hon", "the", "rev", "dr", "mr"))
        cm_persons[(s, inits.upper())].append(p["person_id"])
    for l in open(CM / "places.jsonl"):
        p = json.loads(l); cm_places[p["place"].lower()] = p["qid"]
except FileNotFoundError: pass

def person_key(norm):
    n = re.sub(r"^(Mr|Mrs|Dr|Sir|Hon|Rev|Capt|Col|Major|Prof|Messrs)\.?\s+", "", norm.strip(), flags=re.I)
    toks = re.findall(r"[A-Za-z][A-Za-z'’\-]*", n)
    if not toks: return None
    sur = toks[-1].lower(); inits = "".join(t[0].upper() for t in toks[:-1])
    return sur, inits

stats = collections.Counter(); bytype = collections.Counter(); linked = collections.Counter(); examples = collections.defaultdict(list)
per_article = []
for r in res:
    a = arts[r["id"]]; ms = r["mentions"]
    stats["articles"] += 1; stats["mentions"] += len(ms); stats["errors"] += len(r["errors"]); stats["seconds"] += r["seconds"]
    for m in ms:
        bytype[m["type"]] += 1; m["link"] = ""
        if m["type"] == "PERSON":
            k = person_key(m["norm"] or m["text"])
            if k:
                if k in planters: m["link"] = f"planter:{planters[k][0]}"; linked["PERSON->planters"] += 1
                elif k[1] and k in cm_persons: m["link"] = f"colist:{cm_persons[k][0]}"; linked["PERSON->col_matching"] += 1
                elif (k[0], "") in planters and not k[1]: pass
        elif m["type"] == "ESTATE":
            n = re.sub(r"\s+(estate|group|gardens?)\.?$", "", (m["norm"] or m["text"]).strip(), flags=re.I).lower()
            if n in estates: m["link"] = f"estate:{estates[n][0]}"; linked["ESTATE->estates"] += 1
        elif m["type"] == "PLACE":
            n = (m["norm"] or m["text"]).strip().lower()
            if n in cm_places: m["link"] = f"wd:{cm_places[n]}"; linked["PLACE->col_matching/Wikidata"] += 1
        if len(examples[m["type"]]) < 12: examples[m["type"]].append((m["text"], m["norm"], m["role"], m["link"]))
    per_article.append((a, r))
print(f"articles {stats['articles']}  mentions {stats['mentions']}  errors {stats['errors']}  mean {stats['mentions']/max(1,stats['articles']):.1f} mentions/article  "
      f"{stats['mentions']/max(1,sum(a['words'] for a,_ in per_article))*1000:.1f} per 1,000 words  GPU-side seconds {stats['seconds']:.0f}")
print("by type:", dict(bytype.most_common()))
print("linked:", dict(linked), " of", {t: bytype[t] for t in ("PERSON", "ESTATE", "PLACE")})
for t, ex in examples.items():
    print(f"\n{t}:"); [print(f"   {e[0][:40]!r:42} -> {e[1][:35]!r:37} {e[2][:45]!r} {e[3]}") for e in ex]

# HTML
COL = {"PERSON": "#ffd6d6", "ORG": "#d6e4ff", "ESTATE": "#d8f5d0", "PLACE": "#fff1b8", "PUBLICATION": "#ead6ff", "TAXON": "#c8f0ee", "COMMODITY": "#ffe0c2", "EVENT": "#e0e0e0", "OTHER": "#eee"}
def highlight(text, ms):
    surf = sorted({m["text"] for m in ms if len(m["text"]) >= 3}, key=len, reverse=True)
    typ = {m["text"]: m["type"] for m in ms}
    out = html.escape(text)
    for s in surf:
        out = re.sub(re.escape(html.escape(s)), lambda mm: f'<mark style="background:{COL.get(typ[s], "#eee")}" title="{typ[s]}">{mm.group(0)}</mark>', out)
    return out.replace("\n\n", "<br><br>")
H = ['<!doctype html><meta charset="utf-8"><title>NER pilot review</title><style>body{font:14px Georgia,serif;max-width:1100px;margin:1rem auto;padding:0 1rem}'
     'article{border:1px solid #ddd;margin:1rem 0;padding:.7rem 1rem;background:#fff}h3{margin:.2rem 0}.meta{color:#666;font-size:.85rem}'
     'table{border-collapse:collapse;font-size:.85rem;margin:.5rem 0}td,th{border:1px solid #ddd;padding:.1rem .4rem;vertical-align:top}.text{column-count:1;font-size:.9rem;line-height:1.4;max-height:28em;overflow:auto;border-top:1px solid #eee;padding-top:.5rem}'
     'mark{padding:0 .1em;border-radius:2px}.key span{display:inline-block;padding:0 .4em;margin-right:.4em;border-radius:3px}</style>'
     f'<h1>NER pilot — {stats["articles"]} articles, {stats["mentions"]} mentions</h1><p class="key">' + " ".join(f'<span style="background:{c}">{t} {bytype[t]}</span>' for t, c in COL.items() if bytype[t]) + '</p>']
for a, r in sorted(per_article, key=lambda x: x[0]["issue"]):
    ms = r["mentions"]
    rows = "".join(f'<tr><td style="background:{COL.get(m["type"], "#eee")}">{m["type"]}</td><td>{html.escape(m["text"])}</td><td>{html.escape(m["norm"])}</td><td>{html.escape(m["role"])}</td><td>{html.escape(m["link"])}</td></tr>' for m in ms)
    H.append(f'<article><h3>{html.escape(a["title"])}</h3><div class="meta">{a["issue"]} · Vol. {a["volume"]} · {a["words"]} words · {r["chunks"]} chunk(s) · {len(ms)} mentions · {r["seconds"]}s'
             f'{" · ERRORS " + str(len(r["errors"])) if r["errors"] else ""} · <a href="{a["pages"][0]["viewer_url"]}" target="_blank">page image</a></div>'
             f'<details><summary>mentions table</summary><table><tr><th>type</th><th>text</th><th>norm</th><th>role</th><th>link</th></tr>{rows}</table></details>'
             f'<div class="text">{highlight(a["text"], ms)}</div></article>')
open(sys.argv[3], "w").write("\n".join(H))
print(f"\nwrote {sys.argv[3]}")
