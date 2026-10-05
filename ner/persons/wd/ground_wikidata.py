#!/usr/bin/env python3
"""Stage 4, tier 1: ground person profiles to Wikidata through the WikidataMCP vector search.

For each profile in the tranche (default: >=10 mentions):
  1. two vector searches (search_items): "<name> <occupation word from its roles>" and "<name>" alone;
  2. keep candidates whose label contains the profile's surname; read their statements with SPARQL
     (label, aliases, human?, birth/death years, occupations) -- SPARQL only reads QIDs that search returned;
  3. checks, per the plan: name compatible with the label or an alias (initials vs full names, "John" != "James");
     born >= 15 years before the first mention; occupation/description agrees with the role evidence;
  4. decision: auto (exactly one candidate passes name + dates with a specific occupation match, and no
     other passing candidate has one), review (candidates pass but evidence is weaker or split), none.

Caches every search and entity read under wd/cache/ (resumable). Output:
  wd/out/candidates.jsonl   per profile: queries, every scored candidate, decision
  wd/out/links.tsv          one row per profile: decision, best candidate and its evidence
"""
import json, gzip, re, sys, pathlib, collections, argparse, threading
from concurrent.futures import ThreadPoolExecutor
here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here)); sys.path.insert(0, str(here.parent))
import mcp_client as mcp
from parse import parse, given_compat, skey

ap = argparse.ArgumentParser()
ap.add_argument("--min-mentions", type=int, default=10)
ap.add_argument("--workers", type=int, default=3)     # <=5 req/s on the MCP server; each call takes ~1.7 s
ap.add_argument("--limit", type=int, default=0)
args = None

CACHE = here / "cache"; CACHE.mkdir(exist_ok=True)
OUT = here / "out"; OUT.mkdir(exist_ok=True)
lock = threading.Lock()

def load_cache(name):
    d = {}
    p = CACHE / name
    if p.exists():
        for l in open(p):
            r = json.loads(l); d[r["k"]] = r["v"]
    return d
search_cache = load_cache("search.jsonl")
entity_cache = load_cache("entities_v3.jsonl")   # v1 was mis-parsed (fixed-position CSV); not used

def cached(cache, name, k, fn):
    if k in cache:
        return cache[k]
    v = fn(k)
    with lock:
        cache[k] = v
        with open(CACHE / name, "a") as f:
            f.write(json.dumps({"k": k, "v": v}, ensure_ascii=False) + "\n")
    return v

# ---------------- occupation evidence ---------------------------------------------------------------
CLASSES = {
    "botanist": ["botan", "herbari", "flora of", "taxonom"],
    "entomologist": ["entomolog", "insect", "coccid", "lepidopter", "coleopter"],
    "mycologist": ["mycolog", "fung", "plant patholog", "patholog"],
    "chemist": ["chemist", "chemistry", "analyst", "analytical", "assayer"],
    "agriculturist": ["agricultur", "agronom", "soil scien", "experiment station", "agrostolog"],
    "veterinarian": ["veterinar", "v.s.", "m.r.c.v.s"],
    "planter": ["planter", "plantation", "estate", "coffee grower", "tea grower"],
    "administrator": ["governor", "colonial secretary", "administrator", "civil servant", "civil service",
                      "government agent", "commissioner", "colonial official", "viceroy", "consul", "diplomat",
                      "surveyor-general", "collector of", "british resident", "resident of"],
    "journalist": ["editor", "journalist", "newspaper", "publisher"],
    "physician": ["physician", "surgeon", "medical", "medicine"],
    "engineer": ["engineer", "inventor"],
    "clergy": ["missionary", "priest", "clergy", "bishop", "reverend", "chaplain", "theolog"],
    "politician": ["politician", "member of parliament", "legislative council", "statesman", "prime minister",
                   "legislator", "minister of"],
    "explorer": ["explorer", "traveller", "traveler"],
    "naturalist": ["naturalist", "zoolog", "ornitholog", "biologist", "natural histor"],
    "horticulturist": ["horticultur", "gardener", "nurseryman", "garden"],
    "forester": ["forest", "conservator"],
    "geologist": ["geolog", "mineralog"],
    "economist": ["economist", "statistic"],
    "businessperson": ["merchant", "broker", "businessman", "business", "trader", "banker", "manufacturer",
                       "industrialist", "entrepreneur", "shipowner", "company"],
    "military": ["army officer", "military", "soldier", "colonel", "naval officer", "royal navy", "officer of the army"],
    "lawyer": ["lawyer", "barrister", "advocate", "judge", "proctor", "counsel", "jurist", "solicitor"],
    "royalty": ["monarch", "king", "queen", "emperor", "prince", "sultan", "maharaja", "nobleman"],
    "writer": ["writer", "author", "poet", "novelist", "historian"],                       # generic
    "scientist": ["scientist", "researcher", "professor", "lecturer", "academic", "physiologist", "physicist"],  # generic
}
GENERIC = {"writer", "scientist"}
HON_CLASS = {"capt": "military", "col": "military", "major": "military", "gen": "military", "lieut": "military",
             "admiral": "military", "rev": "clergy", "bishop": "clergy", "father": "clergy", "judge": "lawyer",
             "king": "royalty", "queen": "royalty", "emperor": "royalty", "prince": "royalty", "lord": "royalty"}
OCC_WORD = {"botanist": "botanist", "entomologist": "entomologist", "mycologist": "mycologist", "chemist": "chemist",
            "agriculturist": "agriculturist", "veterinarian": "veterinarian", "planter": "planter",
            "administrator": "colonial administrator", "journalist": "journalist", "physician": "physician",
            "engineer": "engineer", "clergy": "missionary", "politician": "politician", "explorer": "explorer",
            "naturalist": "naturalist", "horticulturist": "horticulturist", "forester": "forester",
            "geologist": "geologist", "economist": "economist", "businessperson": "merchant", "military": "army officer",
            "lawyer": "lawyer", "royalty": "monarch", "writer": "writer", "scientist": "scientist"}
BIBLIO = re.compile(r"\b(author|cited|authority|quoted|writer|scientist|researcher|chemist|botanist|naturalist|"
                    r"historian|poet|referred|according|investigator|experimenter|discoverer|inventor)", re.I)

def classes(text):
    t = text.lower()
    c = {c for c, kws in CLASSES.items() if any(k in t for k in kws)}
    if re.search(r"(academic|university|sports|school|hospital|arts) administrator", t) and "colonial" not in t:
        c.discard("administrator")
    if "veterinar" in t:          # Veterinary Surgeon is not a physician
        c.discard("physician")
    if "botanic" in t:            # Director of the Botanic Gardens = a botanist, not a gardener
        c.discard("horticulturist")
    return c

JOURNAL = re.compile(r"tropical agriculturist|planters' association|agricultural society|board of agriculture", re.I)

def profile_classes(p):
    c = collections.Counter()
    for role, n in p["roles"]:
        for k in classes(JOURNAL.sub(" ", role)):
            c[k] += n
    for h, n in p["honorifics"]:
        if h in HON_CLASS:
            c[HON_CLASS[h]] += n
    total = sum(n for _, n in p["roles"]) + sum(n for h, n in p["honorifics"] if h in HON_CLASS)
    return collections.Counter({k: v for k, v in c.items() if v >= max(2, 0.05 * total)})

RELATED = [{"botanist", "horticulturist", "mycologist", "forester", "agriculturist", "naturalist"},
           {"entomologist", "naturalist", "agriculturist"}, {"chemist", "agriculturist"},
           {"physician", "veterinarian"}, {"administrator", "politician", "lawyer"}, {"planter", "agriculturist"},
           {"journalist", "writer"}]

# ---------------- queries ----------------------------------------------------------------------------
def name_for_query(p):
    if p["kind"] == "surname_pool":
        return p["display"]
    toks = [n.capitalize() if not n.endswith(".") else n.upper() for n in p["given"].split()]
    return " ".join(toks + [p["display"].split()[-1] if p["display"] else p["skey"]]) if toks else p["display"]

def queries(p):
    name = p["display"] if p["kind"] == "named" else name_for_query(p)
    pc = profile_classes(p)
    spec = [c for c, _ in pc.most_common() if c not in GENERIC]
    occs = [OCC_WORD[c] for c in spec[:2]] or ([OCC_WORD[pc.most_common(1)[0][0]]] if pc else [])
    qs = [f"{name} {o}" for o in occs] + [name]
    return list(dict.fromkeys(qs))

# ---------------- entity reads ------------------------------------------------------------------------
SPARQL = """SELECT ?item ?lab ?desc ?human (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases)
(MIN(YEAR(?b)) AS ?birth) (MIN(YEAR(?d)) AS ?death) (GROUP_CONCAT(DISTINCT ?occL; separator="|") AS ?occs) (SAMPLE(?sexL) AS ?sex) WHERE {
VALUES ?item { %s }
OPTIONAL { ?item rdfs:label ?lab FILTER(lang(?lab)="en") } OPTIONAL { ?item schema:description ?desc FILTER(lang(?desc)="en") }
OPTIONAL { ?item wdt:P569 ?b } OPTIONAL { ?item wdt:P570 ?d }
OPTIONAL { ?item wdt:P106 ?o . ?o rdfs:label ?occL FILTER(lang(?occL)="en") }
OPTIONAL { ?item skos:altLabel ?alias FILTER(lang(?alias)="en") }
OPTIONAL { ?item wdt:P21 ?sx . ?sx rdfs:label ?sexL FILTER(lang(?sexL)="en") }
BIND(EXISTS { ?item wdt:P31 wd:Q5 } AS ?human) } GROUP BY ?item ?lab ?desc ?human"""

def read_entities(qids):
    todo = [q for q in dict.fromkeys(qids) if q not in entity_cache]
    for k in range(0, len(todo), 40):
        batch = todo[k:k + 40]
        txt = mcp.call("execute_sparql", sparql=SPARQL % " ".join("wd:" + q for q in batch), K=200)
        got = {}
        lines = txt.splitlines()
        head = lines[0].split(";")
        for line in lines[1:]:
            f = line.split(";")
            if len(f) > len(head):   # ';' inside the description: fold the surplus back into it
                k = head.index("desc"); extra = len(f) - len(head)
                f = f[:k] + [";".join(f[k:k + extra + 1])] + f[k + extra + 1:]
            if len(f) != len(head):
                continue
            row = dict(zip(head, f))
            item, lab, desc = row["item"], row["lab"], row["desc"]
            occs, death, birth, aliases, human = row["occs"], row["death"], row["birth"], row["aliases"], row["human"]
            got[item] = {"label": lab.strip('"'), "desc": desc.strip('"'), "human": human == "true",
                         "aliases": [a for a in aliases.strip('"').split("|") if a],
                         "birth": int(birth) if re.fullmatch(r"-?\d+", birth) else None,
                         "death": int(death) if re.fullmatch(r"-?\d+", death) else None,
                         "occs": [o for o in occs.strip('"').split("|") if o], "sex": row.get("sex", "").strip('"')}
        with lock:
            with open(CACHE / "entities_v3.jsonl", "a") as fh:
                for q in batch:
                    v = got.get(q, {"missing": True})
                    entity_cache[q] = v
                    fh.write(json.dumps({"k": q, "v": v}, ensure_ascii=False) + "\n")
    return {q: entity_cache[q] for q in qids}

# ---------------- scoring --------------------------------------------------------------------------------
def name_ok(p, e):
    # the commonest printed form, not the merged signature (merging can misplace names: "Ernest Ernest Green")
    dp = parse(p["display"]) if p["kind"] == "named" else {"given": []}
    pg = dp["given"] if dp.get("kind") == "person" else []
    # a full given name anywhere in the label/aliases that contradicts the profile's rules the candidate out
    # ("Robert Cross" vs alias "R. A. Cross" of "Richard Assheton Cross")
    if pg and any(n for _, n in pg):
        for nm in [e["label"]] + e["aliases"]:
            q = parse(nm)
            if q["kind"] == "person" and q["skey"].split(":")[-1] == p["skey"].split(":")[-1] and \
                    any(n for _, n in q["given"]) and not given_compat(pg, q["given"]):
                return False, None, False, False
    for nm in [e["label"]] + e["aliases"]:
        q = parse(nm)
        if q["kind"] != "person":
            continue
        sk = q["skey"].split(":")[-1]
        if sk != p["skey"].split(":")[-1] and not (len(p["skey"]) >= 4 and sk.endswith(p["skey"].split(":")[-1])):
            continue
        if pg and not q["given"]:
            continue
        if not pg or given_compat(pg, q["given"]):
            exact = bool(pg) and any(n for _, n in pg) and all(
                n is None or any(n == m for _, m in q["given"]) for _, n in pg)
            # strong = the profile's given names are a prefix of the candidate's ("F. A." ~ "Frank Arthur");
            # weak = matched only through a middle name ("William" ~ "John William Muir")
            strong = not pg or (all(a[0] == b[0] and (a[1] is None or b[1] is None or a[1] == b[1])
                                    for a, b in zip(pg, q["given"]))
                                # a full given name of the profile the candidate lacks ("H. Drummond Deane")
                                and not any(n for _, n in pg[len(q["given"]):]))
            best = (True, nm, exact, strong)
            if strong:
                return best
            weak = best
    return locals().get("weak", (False, None, False, False))

def score(p, e, rank):
    r = {"rank": rank}
    ok, via, exact, strong = name_ok(p, e)
    r.update(name_ok=ok, name_via=via, name_exact=exact, name_strong=strong)
    ys = YEARS.get(p["pid"]) or [y for y in (p["first"], p["last"]) if y]
    b, d = e.get("birth"), e.get("death")
    n = max(1, len(ys))
    # robust to a few mis-attached mentions: shares of the profile's mentions, not its first/last year
    r["born_ok"] = not (b and sum(1 for y in ys if y < b + 15) > 0.1 * n)
    bib = sum(k for role, k in p["roles"] if BIBLIO.search(role)) >= 0.5 * max(1, sum(k for _, k in p["roles"]))
    after = sum(1 for y in ys if d and y > d + 3) / n
    r["posthumous"] = bool(d and after > 0.5)
    # died before most mentions: still a candidate (it blocks rivals: Sir William Gregory, d. 1892, remembered
    # for decades), but it can be auto-linked only when the profile is mostly citations of an author
    med = sorted(ys)[len(ys) // 2] if ys else 0
    r["dates_ok"] = r["born_ok"] and not (d and med and d + 60 < med and not bib and p["kind"] != "surname_pool")
    r["auto_eligible"] = not r["posthumous"] or bib or p["kind"] == "surname_pool"
    r["dates_known"] = bool(b or d)
    pc = profile_classes(p)
    ec = classes(e.get("desc", "") + " " + " ".join(e.get("occs", [])))
    shared = set(pc) & ec
    r["occ_specific"] = sorted(shared - GENERIC)
    r["occ_generic"] = sorted(shared & GENERIC)
    r["occ_related"] = sorted({a for a in set(pc) - GENERIC for g in RELATED if a in g for b in ec if b in g and b != a})
    hons = dict(p["honorifics"])
    pf = p["gender"] == "f" or sum(hons.get(h, 0) for h in ("mrs", "miss", "lady", "mme", "mlle")) > sum(hons.get(h, 0) for h in ("mr", "sir"))
    pm = not pf and (p["gender"] == "m" or sum(hons.get(h, 0) for h in ("mr", "sir", "lord", "herr", "mons")) > 0)
    sex = e.get("sex", "")
    r["sex_ok"] = not ((pf and sex == "male") or (pm and sex == "female"))
    r["passes"] = bool(e.get("human") and ok and r["dates_ok"] and r["sex_ok"])
    return r

def decide(p, cands):
    passing = [c for c in cands if c["s"]["passes"]]
    if not passing:
        return "none", None
    spec = [c for c in passing if c["s"]["occ_specific"]]
    if len(spec) == 1 and spec[0]["s"]["name_strong"] and spec[0]["s"]["dates_known"] and spec[0]["s"]["auto_eligible"]:
        return "auto", spec[0]
    best = sorted(passing, key=lambda c: (-len(c["s"]["occ_specific"]), -len(c["s"]["occ_related"]), -len(c["s"]["occ_generic"]),
                                          -c["s"]["name_exact"], c["s"]["rank"]))[0]
    return "review", best

YEARS = {}

def main():
    global args
    args = ap.parse_args()
    for l in gzip.open(here.parent / "out/mentions.tsv.gz", "rt"):
        f = l.rstrip("\n").split("\t")
        if len(f) > 9 and f[8] and f[2].isdigit() and f[2] != "0":
            YEARS.setdefault(f[8], []).append(int(f[2]))
    # ---- run ------------------------------------------------------------------------------------
    profiles = [json.loads(l) for l in gzip.open(here.parent / "out/profiles.jsonl.gz", "rt")]
    tranche = [p for p in profiles if p["mentions"] >= args.min_mentions]
    if args.limit:
        tranche = tranche[:args.limit]
    print(f"tranche: {len(tranche)} profiles (>= {args.min_mentions} mentions)", flush=True)
    mcp.init()

    def do_search(p):
        res = []
        for q in queries(p):
            hits = cached(search_cache, "search.jsonl", q, mcp.search)
            res.append((q, hits))
        return p["pid"], res

    searched = {}
    with ThreadPoolExecutor(args.workers) as ex:
        for n, (pid, res) in enumerate(ex.map(do_search, tranche), 1):
            searched[pid] = res
            if n % 100 == 0:
                print(f"searched {n}/{len(tranche)}", flush=True)

    def surname_hit(p, label):
        s = p["skey"].split(":")[-1]
        return s and s in skey(label)

    pre = {}
    for p in tranche:
        seen = {}
        for q, hits in searched[p["pid"]]:
            for rank, (qid, label, desc) in enumerate(hits):
                if qid not in seen and surname_hit(p, label):
                    seen[qid] = rank
        pre[p["pid"]] = seen
    allq = sorted({q for s in pre.values() for q in s})
    print(f"candidate QIDs to read: {len(allq)} ({sum(1 for q in allq if q not in entity_cache)} not cached)", flush=True)
    read_entities(allq)

    dec_count = collections.Counter()
    with open(OUT / "candidates.jsonl", "w") as fc, open(OUT / "links.tsv", "w") as fl:
        fl.write("pid\tkind\tdisplay\tmentions\tfirst\tlast\troles\tdecision\tqid\tlabel\tdescription\tbirth\tdeath\t"
                 "occupations\tname_via\tocc_match\tn_passing\tother_passing\n")
        for p in tranche:
            cands = []
            for qid, rank in sorted(pre[p["pid"]].items(), key=lambda x: x[1]):
                e = entity_cache.get(qid, {})
                if e.get("missing"): continue
                cands.append({"qid": qid, **{k: e.get(k) for k in ("label", "desc", "birth", "death", "occs")}, "s": score(p, e, rank)})
            d, best = decide(p, cands)
            dec_count[d] += 1
            passing = [c for c in cands if c["s"]["passes"]]
            fc.write(json.dumps({"pid": p["pid"], "display": p["display"], "queries": [q for q, _ in searched[p["pid"]]],
                                 "decision": d, "qid": best["qid"] if best else None, "candidates": cands}, ensure_ascii=False) + "\n")
            roles = " | ".join(r for r, _ in p["roles"][:4])
            b = best or {}
            fl.write("\t".join(str(x if x is not None else "").replace("\t", " ") for x in [
                p["pid"], p["kind"], p["display"], p["mentions"], p["first"], p["last"], roles, d, b.get("qid"), b.get("label"),
                b.get("desc"), b.get("birth"), b.get("death"), "|".join((b.get("occs") or [])[:5]),
                b.get("s", {}).get("name_via"), ",".join(b.get("s", {}).get("occ_specific", []) + ["~" + x for x in b.get("s", {}).get("occ_related", [])] + b.get("s", {}).get("occ_generic", [])),
                len(passing), " ; ".join(f"{c['qid']} {c['label']} ({c['desc'][:40]})" for c in passing if c is not best)[:400]]) + "\n")
    print("decisions:", dict(dec_count), flush=True)


if __name__ == "__main__":
    main()
