#!/usr/bin/env python3
"""
HTML review sheet for assembled articles: one table per issue, one row per article,
with links to every page image on the Internet Archive and the opening/closing text,
so a wrong boundary can be checked against the scan in one click.

Usage: review.py ARTICLES.jsonl OUT.html [max_articles_per_issue]
"""
import html, json, sys, collections

arts = [json.loads(l) for l in open(sys.argv[1])]
cap = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 6
by = collections.OrderedDict()
for a in arts:
    by.setdefault((a["volume"], a["issue"], a["doc"]), []).append(a)
e = html.escape
out = ["""<!doctype html><meta charset="utf-8"><title>Tropical Agriculturist — article pilot</title>
<style>body{font:14px/1.4 system-ui,sans-serif;margin:1.5em;max-width:1400px}
table{border-collapse:collapse;width:100%;margin-bottom:2em}td,th{border:1px solid #ccc;padding:4px 6px;vertical-align:top}
th{background:#f3f3f3;text-align:left}.t{font-weight:600}.s{color:#666;font-size:12px}.x{font-family:Georgia,serif;font-size:13px;color:#333}
.p a{margin-right:4px}h2{margin-top:1.5em}.sup{background:#fff7e0}</style>
<h1>Tropical Agriculturist — articles assembled from the pilot labels</h1>
<p>Each row is one article. Page numbers are printed folios (scan page in brackets) and link to the page image on the
Internet Archive. Check that the title is where the page image shows it, and that "ends" is where the article ends.
Rows shaded yellow are in the Supplement.</p>"""]
for (vol, iss, doc), rows in by.items():
    out.append(f"<h2>Vol. {vol} — {e(iss)} <span class=s>{e(doc)} · {len(rows)} articles</span></h2>")
    out.append("<table><tr><th>#</th><th>Title / section / byline</th><th>Pages</th><th>Words</th><th>Opens</th><th>Ends</th></tr>")
    for k, a in enumerate(rows[:cap], 1):
        pages = " ".join(f'<a href="{e(p["viewer_url"])}" target=_blank>{e(p["folio"] or "?")}<span class=s>[{p["page"]}]</span></a>'
                         for p in a["pages"])
        body = a["text"]
        cls = ' class=sup' if a["part"] == "supplement" else ""
        out.append(f"<tr{cls}><td>{k}</td><td><div class=t>{e(a['title'][:160])}</div>"
                   f"<div class=s>{e(a['section'][:80])}{' · ' + e(a['byline'][:80]) if a['byline'] else ''}</div></td>"
                   f"<td class=p>{pages}</td><td>{a['words']}</td>"
                   f"<td class=x>{e(body[:260])}</td><td class=x>…{e(body[-200:])}</td></tr>")
    out.append("</table>")
open(sys.argv[2], "w").write("\n".join(out))
print(f"{len(arts)} articles, {len(by)} issues -> {sys.argv[2]}")
