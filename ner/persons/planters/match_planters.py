#!/usr/bin/env python3
"""Stage 4, tier 3: match person profiles to the historyofceylontea.com planters registry (ids/URLs only;
see ../../gazetteer/README.md -- grounding, not content).

The registry slug is the only evidence on its side ("murray-w-a-f", "f-r-sabonadiere"; word order varies), so
the rule is strict:
  name     surname equal AND the exact sequence of initials equal (profile full names -> initials);
           "J. Shand" does not match "j-l-shand";
  planter  the profile's roles say planter/estate/superintendent/manager/proprietor/visiting agent, or its
           roles carry it in >= 2 mentions (co-occurring estates are not evidence: they are everywhere);
  period   the profile's mentions overlap the registry's span (1871-1930, +5);
  unique   exactly one registry id fits -> link (confidence medium); several -> review.
Output: planters/links.tsv"""
import json, gzip, re, sys, collections, pathlib
here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent))
from parse import parse, skey, PARTICLES

GAZ = here.parent.parent / "gazetteer/planters_index.tsv"
PLANTER = re.compile(r"planter|\bestate\b|\bof [A-Z][a-z]+ (estate|group)|(manager|superintendent|proprietor|owner) of|"
                     r"visiting agent|planting", re.I)
NOT_PLANTER = re.compile(r"estates? products committee|botanic|experiment station|government|director of agriculture", re.I)

def slug_readings(slug):
    """-> [(surname_key, initials)] for each plausible word order."""
    toks = [t for t in slug.split("-") if t and t not in {"mr", "mrs", "miss", "dr", "rev", "capt", "major", "col", "sir"}]
    inits = [t for t in toks if len(t) == 1]
    words = [t for t in toks if len(t) > 1]
    if not words:
        return []
    out = []
    # join particles with the following word ("de-silva" -> "desilva")
    joined, k = [], 0
    while k < len(words):
        if words[k] in PARTICLES and k + 1 < len(words):
            joined.append(words[k] + words[k + 1]); k += 2
        else:
            joined.append(words[k]); k += 1
    if len(joined) == 1:
        out.append((skey(joined[0]), [(i, None) for i in inits]))
    else:   # "aiyadorai-freddy" / "john-smith": either end may be the surname; other words are given names
        out.append((skey(joined[-1]), [(x[0], x) for x in joined[:-1]] + [(i, None) for i in inits]))
        out.append((skey(joined[0]), [(i, None) for i in inits] + [(x[0], x) for x in joined[1:]]))
    return out

reg = collections.defaultdict(list)
for l in list(open(GAZ))[1:]:
    pid, slug, live, wb = l.rstrip("\n").split("\t")
    for sk, g in slug_readings(slug):
        if sk and g:
            reg[(sk, "".join(i for i, _ in g))].append((pid, slug, live, g))

years = collections.defaultdict(list)
for l in gzip.open(here.parent / "out/mentions.tsv.gz", "rt"):
    f = l.rstrip("\n").split("\t")
    if len(f) > 9 and f[8] and f[2].isdigit() and f[2] != "0":
        years[f[8]].append(int(f[2]))
profiles = [json.loads(l) for l in gzip.open(here.parent / "out/profiles.jsonl.gz", "rt")]
dec = collections.Counter(); rows = []
for p in profiles:
    if p["kind"] != "named" or p["mentions"] < 2:
        continue
    dp = parse(p["display"])
    if dp["kind"] != "person" or not dp["given"]:
        continue
    ini = "".join(i for i, _ in dp["given"])
    # same initials, and no full given name contradicting ("James" vs slug "john")
    hits = {x[0]: x for x in reg.get((p["skey"].split(":")[-1], ini), [])
            if all(a[1] is None or b[1] is None or a[1] == b[1] for a, b in zip(dp["given"], x[3]))}
    if not hits:
        continue
    ys = years.get(p["pid"]) or [p["first"]]
    if not any(1866 <= y <= 1935 for y in ys):
        dec["out_of_period"] += 1; continue
    # planter evidence must come from the profile's own roles (>=2 mentions), not from co-occurring estates,
    # which appear in nearly every article
    pr = sum(n for r, n in p["roles"] if PLANTER.search(r) and not NOT_PLANTER.search(r))
    if pr < 2:
        dec["not_planter"] += 1; continue
    d = "link" if len(hits) == 1 else "review"
    dec[d] += 1
    h = list(hits.values())
    rows.append([p["pid"], p["display"], p["mentions"], f"{p['first']}-{p['last']}", " | ".join(r for r, _ in p["roles"][:4]),
                 " | ".join(e for e, _ in p["estates"][:3]), d, " ; ".join(x[0] for x in h), " ; ".join(x[1] for x in h),
                 h[0][2] if len(h) == 1 else ""])
with open(here / "links.tsv", "w") as f:
    f.write("pid\tdisplay\tmentions\tyears\troles\testates\tdecision\tplanter_ids\tslugs\turl\n")
    for r in rows:
        f.write("\t".join(str(x).replace("\t", " ") for x in r) + "\n")
print(dict(dec))
