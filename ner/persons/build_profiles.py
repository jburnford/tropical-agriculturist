#!/usr/bin/env python3
"""Stages 1-3 of person grounding (deterministic, CPU): parse -> in-article coreference -> corpus profiles.

Input  ../mentions.jsonl (PERSON mentions), ../../articles/by_year/*.jsonl.gz (article years)
Output (in this directory, out/):
  mentions.tsv.gz    one row per PERSON mention: article, idx, text, norm, kind, pid, method
  profiles.jsonl.gz  one record per profile (the unit that gets grounded in stage 4)
  profiles.tsv.gz    the same, flattened, ranked by mentions; profiles_head.tsv = the >=10-mention tranche
  stats.md           counts per stage and per resolution method

Resolution methods (mention level), strongest first:
  explicit       the surface text itself carries initials/given names
  norm           the surface is bare ("Mr. Petch") but the extractor's norm carries them ("T. Petch")
  article        bare surname -> the only compatible full name of that surname in the same article
  corpus_dominant  bare surname, several candidates, one has >=5 named mentions within +-5 years and 5x the next
  corpus_honorific bare surname with a discriminating honorific ("Dr.", "Prof.", "Capt.") that only one candidate
                 carries in its printed full-name mentions (>=2 times)
  corpus_unique  bare surname, no full name in the article -> the only compatible named profile with that
                 surname active in that period (medium confidence; one candidate, not a string merge)
  pool           bare surname with no named profile anywhere in the corpus -> a surname_pool row
                 ("Liebig", "Pliny"): a candidate for adjudication, NOT an identity
  ambiguous      several compatible candidates; left unassigned, candidates recorded
  unresolved     bare surname, named profiles exist but none fits the period/gender
  -              not a person (title, list, initials-only signature, empty)

Profile ids (pid) are build-local (rank order), not persistent; persistent ids are minted in stage 4."""
import json, gzip, re, collections, pathlib, sys
here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here))
from parse import parse, display, IDENTITY, pos_ok, given_compat

PAD = 15          # years of slack around a profile's active span for corpus-level attachment
OUT = here / "out"; OUT.mkdir(exist_ok=True)

# ---------------- compatibility -----------------------------------------------------------------
def other_compat(u, v):
    if (u["gender"] == "f") != (v["gender"] == "f"):   # "Mrs. J. Smith" is not J. Smith (usually his wife)
        return False
    if u["gen"] and v["gen"] and u["gen"] != v["gen"]:
        return False
    return True

def merge_given(g1, g2):
    """The most specific consistent signature (caller has checked compatibility)."""
    s, l = (g1, g2) if len(g1) <= len(g2) else (g2, g1)
    l = list(l)
    if len(s) == len(l) and all(pos_ok(a, b) for a, b in zip(s, l)):   # "Ernest Green" may be a middle name
        for k, a in enumerate(s):
            if a[1] and not l[k][1] and a[1] not in {n for _, n in l}:   # never "Ernest Ernest Green"
                l[k] = a
    return l

def sigstr(g):
    return " ".join(n if n else i + "." for i, n in g)

# ---------------- load --------------------------------------------------------------------------
year = {}
for f in (here.parent.parent / "articles/by_year").glob("articles_*.jsonl.gz"):
    y = int(re.search(r"(\d{4})", f.name).group(1))
    for l in gzip.open(f, "rt", encoding="utf-8"):
        year[json.loads(l)["id"]] = y

rows = []            # every PERSON mention
art_ctx = {}         # article -> (places Counter, estates Counter)
kinds = collections.Counter()
for l in open(here.parent / "mentions.jsonl"):
    r = json.loads(l); aid = r["id"]; y = year.get(aid, 0)
    pl = collections.Counter(); es = collections.Counter()
    for idx, m in enumerate(r["mentions"]):
        if m["type"] == "PLACE": pl[(m["norm"] or m["text"]).strip()] += 1
        elif m["type"] == "ESTATE": es[(m["norm"] or m["text"]).strip()] += 1
        elif m["type"] == "PERSON":
            p = parse(m["text"], m["norm"])
            kinds[p["kind"]] += 1
            p0 = parse(m["text"]) if p["kind"] == "person" and p["given"] else None
            rows.append({"aid": aid, "idx": idx, "year": y, "text": m["text"], "norm": m["norm"],
                         "role": (m["role"] or "").strip(), "p": p, "pid": None, "method": "-",
                         "from_norm": bool(p0 is not None and not (p0["kind"] == "person" and p0["given"]))})
    art_ctx[aid] = (pl, es)

# The extractor's norm sometimes supplies given names from world knowledge, not the page ("Dr. Trimen" ->
# "H. F. C. Trimen", "Watt" -> "James Watt"). Accept norm-supplied names only if the article prints them.
text = {}
need = {r["aid"] for r in rows}
for f in (here.parent.parent / "articles/by_year").glob("articles_*.jsonl.gz"):
    for l in gzip.open(f, "rt", encoding="utf-8"):
        a = json.loads(l)
        if a["id"] in need:
            text[a["id"]] = re.sub(r"\s+", " ", a["text"])

def printed(p, t):
    sur = re.escape(p["surname"].split()[-1])
    parts = [f"(?:{re.escape(n)}|{i}\\.?)" if n else f"{i}\\.?" for i, n in p["given"]]
    gp = r"[\s,]*".join(parts)
    return bool(re.search(r"\b" + gp + r"[\s,]*(?:[\w'-]+\s+){0,2}?" + sur, t, re.I) or
                re.search(sur + r",?\s*" + gp, t, re.I))

norm_check = collections.Counter(); surface_found = collections.Counter()
for r in rows:
    t = text.get(r["aid"], "")
    surface_found[re.sub(r"\s+", " ", r["text"].strip()) in t] += 1
    if r["from_norm"]:
        if printed(r["p"], t):
            norm_check["verified"] += 1
        else:
            norm_check["rejected"] += 1
            r["norm_guess"] = display(r["p"])
            p = parse(r["text"])
            if p["kind"] == "person" and not p["given"]:
                r["p"] = p
            else:   # surface unparseable on its own: keep the surname, drop the guessed given names
                r["p"] = dict(r["p"], given=[])
            r["from_norm"] = False
del text

# ---------------- stage 2: in-article coreference -----------------------------------------------
# A unit = one person within one article (several mentions). Named units carry a given-name signature.
units = []
by_art = collections.defaultdict(list)
for i, r in enumerate(rows):
    if r["p"]["kind"] == "person":
        by_art[r["aid"]].append(i)

def new_unit(aid, y, p, members):
    return {"aid": aid, "year": y, "skey": p["skey"], "given": list(p["given"]), "gen": p["gen"],
            "gender": p["gender"], "members": members, "cands": []}

for aid, idxs in by_art.items():
    y = rows[idxs[0]]["year"]
    by_s = collections.defaultdict(list)
    for i in idxs:
        by_s[rows[i]["p"]["skey"]].append(i)
    for sk, ii in by_s.items():
        named = sorted((i for i in ii if rows[i]["p"]["given"]),
                       key=lambda i: (-len(rows[i]["p"]["given"]), -sum(1 for _, n in rows[i]["p"]["given"] if n)))
        bare = [i for i in ii if not rows[i]["p"]["given"]]
        nu = []
        for i in named:
            p = rows[i]["p"]
            fits = [u for u in nu if given_compat(p["given"], u["given"]) and other_compat(p, u)]
            if len(fits) == 1:
                u = fits[0]; u["given"] = merge_given(u["given"], p["given"]); u["members"].append(i)
                u["gender"] = u["gender"] or p["gender"]; u["gen"] = u["gen"] or p["gen"]
            else:
                nu.append(new_unit(aid, y, p, [i]))
        for i in named:
            rows[i]["method"] = "norm" if rows[i]["from_norm"] else "explicit"
        # bare surnames: attach to the only compatible named unit; else one article-local bare unit per gender
        local = []
        for i in bare:
            p = rows[i]["p"]
            fits = [u for u in nu if other_compat(p, u)]
            if len(fits) == 1:
                fits[0]["members"].append(i); rows[i]["method"] = "article"
            elif len(fits) > 1:
                rows[i]["method"] = "ambiguous"
                rows[i]["cands_local"] = [sigstr(u["given"]) + " " + rows[u["members"][0]]["p"]["surname"] for u in fits]
            else:
                lf = [u for u in local if other_compat(p, u)]
                if lf:
                    lf[0]["members"].append(i); lf[0]["gender"] = lf[0]["gender"] or p["gender"]
                else:
                    local.append(new_unit(aid, y, p, [i]))
        units += nu
        for u in local:
            u["bare"] = True
        units += local

named_units = [u for u in units if u["given"]]
bare_units = [u for u in units if not u["given"]]

# ---------------- stage 3: corpus profiles ------------------------------------------------------
# Group named units by exact signature, then greedily attach signatures (largest first) to the one
# compatible cluster. A rarer, MORE specific signature never extends a cluster (J. D. W. Hughes must not
# swallow John Hughes's cluster by arriving later) -> recorded as possible_same_as instead.
sig_groups = collections.defaultdict(list)
for u in named_units:
    sig_groups[(u["skey"], tuple(u["given"]), u["gen"], "f" if u["gender"] == "f" else "")].append(u)

def n_mentions(us):
    return sum(len(u["members"]) for u in us)

def group_head(c):
    """Clusters kept apart only by the no-extension rule (possible_same_as) form one candidate group."""
    while c["same_as"] and len(c["same_as"]) == 1:
        c = c["same_as"][0]
    return c

clusters = collections.defaultdict(list)   # skey -> [cluster]
for key in sorted(sig_groups, key=lambda k: (-n_mentions(sig_groups[k]), repr(k))):
    sk, g, gen, gender = key; us = sig_groups[key]; g = list(g)
    ys = [u["year"] for u in us if u["year"]]
    lo, hi = (min(ys), max(ys)) if ys else (0, 9999)
    probe = {"gen": gen, "gender": gender}
    loose = [c for c in clusters[sk] if given_compat(g, c["given"]) and other_compat(probe, c)]
    fits = [c for c in loose if c["gen"] == gen]   # Jr./Sr. never join an unmarked cluster (A. M. Ferguson)
    if len(fits) > 1:   # let the period decide between candidates
        timed = [c for c in fits if lo <= c["hi"] + PAD and hi >= c["lo"] - PAD]
        if len(timed) == 1:
            fits = timed
    extends = lambda c: len(g) > len(c["given"])
    if len(fits) > 1:   # prefer the one cluster this form fits without extending it
        nonext = [c for c in fits if not extends(c)]
        if len(nonext) == 1:
            fits = nonext
    if len(fits) > 1 and len({id(group_head(c)) for c in fits}) == 1:
        fits = [group_head(fits[0])]
    if len(fits) == 1 and not extends(fits[0]):
        c = fits[0]
        c["given"] = merge_given(c["given"], g); c["units"] += us
        c["gender"] = c["gender"] or gender
        c["lo"] = min(c["lo"], lo); c["hi"] = max(c["hi"], hi)
    else:
        c = {"skey": sk, "given": g, "gen": gen, "gender": gender, "units": list(us), "lo": lo, "hi": hi,
             "ambiguous": [], "same_as": []}
        if len(fits) == 1:
            c["same_as"].append(fits[0])
        elif not fits and loose:
            c["same_as"] += loose
        elif len(fits) > 1:
            c["ambiguous"] = fits
        clusters[sk].append(c)

# bare units that stage 2 could not resolve: attach to the single compatible named cluster of that
# surname active in the period; surnames with no named cluster anywhere become surname pools.
pools = collections.defaultdict(list)
for cs in clusters.values():
    for c in cs:
        c["named_units"] = list(c["units"])
        hc = collections.Counter(h for v in c["units"] for i in v["members"] if rows[i]["p"]["given"]
                                 for h in rows[i]["p"]["hon"])
        c["hons"] = {h for h, n in hc.items() if n >= 2}

for u in bare_units:
    cs = clusters.get(u["skey"], [])
    if not cs:
        pools[(u["skey"], u["gender"] if u["gender"] == "f" else "")].append(u)
        for i in u["members"]: rows[i]["method"] = "pool"
        continue
    y = u["year"]
    fits = [c for c in cs if other_compat(u, c) and (not y or c["lo"] - PAD <= y <= c["hi"] + PAD)]
    heads = {}
    for c in fits:
        heads.setdefault(id(group_head(c)), group_head(c))
    if len(heads) == 1 and len(fits) > 1:
        fits = list(heads.values())
    if len(fits) == 1:
        fits[0]["units"].append(u); u["attached"] = True
        for i in u["members"]: rows[i]["method"] = "corpus_unique"
        continue
    # one candidate dominating the surname within +-5 years of the article (named mentions only)
    loc = sorted(((sum(len(v["members"]) for v in c["named_units"] if y and abs(v["year"] - y) <= 5), id(c), c)
                  for c in fits), key=lambda x: -x[0])
    if len(loc) > 1 and loc[0][0] >= 5 and loc[0][0] >= 5 * loc[1][0]:
        loc[0][2]["units"].append(u); u["attached"] = True
        for i in u["members"]: rows[i]["method"] = "corpus_dominant"
        continue
    # a discriminating honorific ("Dr. Thwaites"): the one candidate whose printed full-name mentions carry it
    uh = {h for i in u["members"] for h in rows[i]["p"]["hon"]} - {"mr", "messrs", "the"}
    if uh:
        hf = [c for c in fits if uh & c["hons"]]
        if len(hf) == 1:
            hf[0]["units"].append(u); u["attached"] = True
            for i in u["members"]: rows[i]["method"] = "corpus_honorific"
            continue
    if True:
        for i in u["members"]:
            rows[i]["method"] = "ambiguous" if fits else "unresolved"
            if fits: rows[i]["n_cands"] = len(fits)

# ---------------- profiles ----------------------------------------------------------------------
profiles = []
def build(kind, skey, given, gen, gender, us, extra):
    mem = [rows[i] for u in us for i in u["members"]]
    arts = sorted({r["aid"] for r in mem})
    ys = sorted(r["year"] for r in mem if r["year"])
    surf = collections.Counter(r["text"] for r in mem)
    roles = collections.Counter(r["role"][:80] for r in mem if r["role"])
    hons = collections.Counter(h for r in mem for h in r["p"]["hon"])
    suf = collections.Counter(s for r in mem for s in r["p"]["suffix"])
    meth = collections.Counter(r["method"] for r in mem)
    pl = collections.Counter(); es = collections.Counter()
    for a in arts:
        for k in art_ctx[a][0]: pl[k] += 1
        for k in art_ctx[a][1]: es[k] += 1
    surname = collections.Counter(r["p"]["surname"] for r in mem).most_common(1)[0][0]
    named_disp = collections.Counter(display(r["p"]) for r in mem if r["p"]["given"])
    disp = named_disp.most_common(1)[0][0] if named_disp else display(dict(mem[0]["p"], given=[], surname=surname))
    extra = dict(extra, signature=sigstr(given) + " " + surname if given else surname,
                 llm_guesses=collections.Counter(r["norm_guess"] for r in mem if r.get("norm_guess")).most_common(5))
    return {"kind": kind, "display": disp, "skey": skey, "given": sigstr(given), "gen": gen, "gender": gender,
            "mentions": len(mem), "articles": len(arts), "first": ys[0] if ys else None, "last": ys[-1] if ys else None,
            "decades": sorted({y // 10 * 10 for y in ys}), "surface_forms": surf.most_common(10),
            "honorifics": hons.most_common(6), "suffixes": suf.most_common(6), "roles": roles.most_common(10),
            "places": pl.most_common(8), "estates": es.most_common(8), "methods": dict(meth),
            "example_articles": arts[:3], "_members": [(r["aid"], r["idx"]) for r in mem], **extra}

for sk, cs in clusters.items():
    for c in cs:
        c["profile"] = build("named", sk, c["given"], c["gen"], c["gender"], c["units"], {})
for (sk, gender), us in pools.items():
    pr = build("surname_pool", sk, [], "", gender, us, {})
    profiles.append(pr)
for sk, cs in clusters.items():
    for c in cs:
        pr = c["profile"]
        pr["ambiguous_with"] = [x["profile"]["display"] for x in c["ambiguous"]]
        pr["possible_same_as"] = [x["profile"]["display"] for x in c["same_as"]]
        profiles.append(pr)

# OCR / spelling variants: same signature, surname keys one edit apart, overlapping years -> flag only
def del1(s):
    return {s[:k] + s[k + 1:] for k in range(len(s))} | {s}
idx = collections.defaultdict(list)
for pr in profiles:
    if pr["kind"] == "named" and pr["mentions"] >= 2 and len(pr["skey"]) >= 5:
        for d in del1(pr["skey"]):
            idx[(pr["given"], d)].append(pr)
for pr in profiles: pr.setdefault("possible_variant_of", [])
seen = set()
for grp in idx.values():
    for a in grp:
        for b in grp:
            if a is b or a["skey"] == b["skey"] or (id(a), id(b)) in seen: continue
            if a["first"] and b["first"] and a["first"] <= b["last"] + PAD and b["first"] <= a["last"] + PAD:
                seen.add((id(a), id(b)))
                if b["mentions"] >= a["mentions"]:
                    a["possible_variant_of"].append(b["display"])
for pr in profiles:
    pr["possible_variant_of"] = sorted(set(pr["possible_variant_of"]))

profiles.sort(key=lambda p: (-p["mentions"], p["display"]))
for n, pr in enumerate(profiles, 1):
    pr["pid"] = f"P{n:06d}"
    for aid, i in pr["_members"]:
        pass
pid_of = {}
for pr in profiles:
    for k in pr.pop("_members"):
        pid_of[k] = pr["pid"]

# ---------------- write -------------------------------------------------------------------------
with gzip.open(OUT / "mentions.tsv.gz", "wt", encoding="utf-8") as f:
    f.write("article\tidx\tyear\ttext\tnorm\trole\tkind\tparsed\tpid\tmethod\n")
    for r in rows:
        p = r["p"]
        f.write("\t".join(str(x).replace("\t", " ") for x in [r["aid"], r["idx"], r["year"], r["text"], r["norm"], r["role"],
                p["kind"], display(p) if p["kind"] == "person" else "", pid_of.get((r["aid"], r["idx"]), ""), r["method"]]) + "\n")
with gzip.open(OUT / "profiles.jsonl.gz", "wt", encoding="utf-8") as f:
    for pr in profiles:
        f.write(json.dumps({"pid": pr["pid"], **{k: v for k, v in pr.items() if k != "pid"}}, ensure_ascii=False) + "\n")
def fmt(c, k=5):
    return " | ".join(f"{a} ({b})" for a, b in c[:k])
HEAD = "pid\tkind\tdisplay\tmentions\tarticles\tfirst\tlast\thonorifics\troles\tsurface_forms\tplaces\testates\tmethods\tflags\n"
with gzip.open(OUT / "profiles.tsv.gz", "wt", encoding="utf-8") as f, open(OUT / "profiles_head.tsv", "w") as fh:
    f.write(HEAD); fh.write(HEAD)
    for pr in profiles:
        flags = "; ".join(x for x in [
            ("ambiguous_with: " + ", ".join(pr["ambiguous_with"])) if pr.get("ambiguous_with") else "",
            ("possible_same_as: " + ", ".join(pr["possible_same_as"])) if pr.get("possible_same_as") else "",
            ("possible_variant_of: " + ", ".join(pr["possible_variant_of"])) if pr["possible_variant_of"] else "",
            "long_span" if pr["first"] and pr["last"] - pr["first"] > 40 else ""] if x)
        line = "\t".join(str(x).replace("\t", " ") for x in [
            pr["pid"], pr["kind"], pr["display"], pr["mentions"], pr["articles"], pr["first"], pr["last"],
            fmt(pr["honorifics"]), fmt(pr["roles"]), fmt(pr["surface_forms"]), fmt(pr["places"]), fmt(pr["estates"]),
            " ".join(f"{k}:{v}" for k, v in sorted(pr["methods"].items())), flags]) + "\n"
        f.write(line)
        if pr["mentions"] >= 10:
            fh.write(line)

meth = collections.Counter(r["method"] for r in rows)
tot = len(rows); named = [p for p in profiles if p["kind"] == "named"]; pool = [p for p in profiles if p["kind"] == "surname_pool"]
with open(OUT / "stats.md", "w") as f:
    f.write(f"# Person profiles — build stats\n\nPERSON mentions: {tot:,}\n\n## Stage 1 kinds\n\n")
    for k, v in kinds.most_common(): f.write(f"- {k}: {v:,} ({v/tot:.1%})\n")
    f.write(f"\n## Extraction fidelity\n\n- surface text found verbatim in the article: {surface_found[True]:,} of {tot:,}"
            f" ({surface_found[True]/tot:.1%})\n- norm-supplied given names printed in the article: {norm_check['verified']:,};"
            f" rejected as guesses (mention treated as bare): {norm_check['rejected']:,}\n")
    f.write("\n## Resolution method (mentions)\n\n")
    for k, v in meth.most_common(): f.write(f"- {k}: {v:,} ({v/tot:.1%})\n")
    f.write(f"\n## Profiles\n\n- named: {len(named):,} ({sum(p['mentions'] for p in named):,} mentions)\n"
            f"- surname_pool: {len(pool):,} ({sum(p['mentions'] for p in pool):,} mentions)\n"
            f"- named with >=10 mentions: {sum(1 for p in named if p['mentions'] >= 10):,}\n"
            f"- named in 2+ articles: {sum(1 for p in named if p['articles'] >= 2):,}\n"
            f"- flagged ambiguous_with: {sum(1 for p in named if p['ambiguous_with']):,}; possible_same_as: "
            f"{sum(1 for p in named if p['possible_same_as']):,}; possible_variant_of: {sum(1 for p in profiles if p['possible_variant_of']):,}\n")
print(open(OUT / "stats.md").read())
