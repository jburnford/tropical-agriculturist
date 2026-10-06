#!/usr/bin/env python3
"""Stage 4 merge: one authority row per person profile, every link with its provenance.

Inputs: out/profiles.jsonl.gz (stages 1-3); wd/out/links.tsv (tier 1 auto/review/none);
wd/adjudication/decisions.tsv (model adjudication of review + high-mention none, by persistent id); colist/links.tsv (tier 2);
planters/links.tsv (tier 3).

Which identities a profile may ASSERT is decided by identity.resolve() (see its docstring): model decisions
(wd/adjudication/decisions.tsv, keyed by the persistent id, applied only while the profile's article set is
unchanged, Jaccard >= 0.8) > tier-1 Wikidata auto > the CO List KG's QID. MIXED/NONE/UNSURE never become an
asserted QID; MIXED also withholds CO List and planter ids. Candidates and disagreements are kept and flagged.
"model_adjudicated" means a model's decision, not a human's; decided_by says which (model | rule; human later).

Persistent ids: every profile gets a minted id TAP-P-nnnnnn from ids/registry.tsv. On a rebuild, a profile
inherits the id of the registered profile with the same surname key whose article set overlaps it most
(Jaccard >= 0.5); otherwise a new id is minted. Ids are never reused.

Output: out/persons.tsv (all profiles) and out/persons_head.tsv (>= 10 mentions)."""
import json, gzip, csv, collections, pathlib, re, sys
here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here))
from identity import resolve, jaccard

def tsv(path):
    if not path.exists():
        return []
    return list(csv.DictReader(open(path), delimiter="\t", quoting=csv.QUOTE_NONE))

profiles = [json.loads(l) for l in gzip.open(here / "out/profiles.jsonl.gz", "rt")]
arts = collections.defaultdict(set)
for l in gzip.open(here / "out/mentions.tsv.gz", "rt"):
    f = l.rstrip("\n").split("\t")
    if len(f) > 9 and f[8]:
        arts[f[8]].add(f[0])

wd = {r["pid"]: r for r in tsv(here / "wd/out/links.tsv")}
adj = {}
for r in tsv(here / "wd/adjudication/decisions.tsv"):          # keyed by persistent id (TAP-P-...)
    r["arts"] = set(r["articles_v1"].split(",")) if r["articles_v1"] else set(); adj[r["tap_id"]] = r
NONHUMAN = set(json.load(open(here / "wd/adjudication/nonhuman_links.json"))) if (here / "wd/adjudication/nonhuman_links.json").exists() else set()
co = {r["pid"]: r for r in tsv(here / "colist/links.tsv")}
pl = {r["pid"]: r for r in tsv(here / "planters/links.tsv")}

# ---------------- persistent ids ------------------------------------------------------------------------
REG = here / "ids/registry.tsv"; REG.parent.mkdir(exist_ok=True)
reg = []
if REG.exists():
    for r in tsv(REG):
        r["arts"] = set(r["articles"].split(",")) if r["articles"] else set(); reg.append(r)
by_s = collections.defaultdict(list)
for r in reg:
    by_s[r["skey"]].append(r)
next_n = max([int(r["id"].split("-")[-1]) for r in reg] or [0]) + 1
taken = set(); new_reg = []
def assign(p):
    global next_n
    a = arts[p["pid"]]
    best, bj = None, 0.0
    for r in by_s.get(p["skey"], []):
        if r["id"] in taken: continue
        j = len(a & r["arts"]) / max(1, len(a | r["arts"]))
        if j > bj: best, bj = r, j
    if best is not None and bj >= 0.5:
        i = best["id"]
    else:
        i = f"TAP-P-{next_n:06d}"; next_n += 1
    taken.add(i)
    new_reg.append({"id": i, "skey": p["skey"], "display": p["display"], "first": p["first"], "last": p["last"],
                    "articles": ",".join(sorted(a))})
    return i

# ---------------- merge ---------------------------------------------------------------------------------
NONHUMAN = frozenset(NONHUMAN)
rows = []; stats = collections.Counter()
for p in profiles:
    pid = p["pid"]; mid = assign(p)
    a = adj.get(mid)
    fresh = bool(a) and jaccard(arts[pid], a["arts"]) >= 0.8
    c, t = co.get(pid), pl.get(pid)
    r = resolve(adj=a, adj_fresh=fresh, wd=wd.get(pid), co=c, pl=t, nonhuman=NONHUMAN)
    stats["qid:" + (r["qid_source"].split("+")[0] if r["qid"] else "none")] += 1
    if a: stats["model_decision:" + ("fresh" if fresh else "stale")] += 1
    if c: stats["colist:" + c["decision"]] += 1
    if t: stats["planter:" + t["decision"]] += 1
    rows.append([mid, pid, p["kind"], p["display"], p["mentions"], p["articles"], p["first"], p["last"],
                 " | ".join(x for x, _ in p["roles"][:4]), r["qid"], r["qid_source"], r["qid_confidence"],
                 r["decided_by"], " ; ".join(r["candidates"]), r["colist_person_id"], (c or {}).get("decision", ""),
                 r["planter_id"], (t or {}).get("decision", ""), r["planter_url"], "; ".join(r["flags"]), r["note"]])

# profiles grounded to the same QID are the same person split by the conservative stage-3 rules
# ("Clements Markham" / "Clements R. Markham"): flag them for merging, keep the ids apart for now
by_q = collections.defaultdict(list)
for r in rows:
    if r[9]: by_q[r[9]].append(r)
FL = 19
for q, rs in by_q.items():
    if len(rs) > 1:
        for r in rs:
            others = ", ".join(f"{x[0]} {x[3]}" for x in rs if x is not r)
            r[FL] = "; ".join(x for x in [r[FL], f"same_qid_as: {others}"] if x)
with open(REG, "w") as f:
    f.write("id\tskey\tdisplay\tfirst\tlast\tarticles\n")
    for r in sorted(new_reg + [r for r in reg if r["id"] not in taken], key=lambda r: r["id"]):
        f.write(f"{r['id']}\t{r['skey']}\t{r['display']}\t{r['first']}\t{r['last']}\t{r['articles'] if isinstance(r['articles'], str) else ','.join(sorted(r['articles']))}\n")
HEAD = ("id\tpid\tkind\tdisplay\tmentions\tarticles\tfirst\tlast\troles\twikidata_qid\tqid_source\tqid_confidence\t"
        "decided_by\tcandidate_qids\tcolist_person_id\tcolist_decision\tplanter_id\tplanter_decision\tplanter_url\t"
        "flags\tnote\n")
with open(here / "out/persons.tsv", "w") as f, open(here / "out/persons_head.tsv", "w") as fh:
    f.write(HEAD); fh.write(HEAD)
    for r in rows:
        line = "\t".join(str(x if x is not None else "").replace("\t", " ") for x in r) + "\n"
        f.write(line)
        if r[4] >= 10: fh.write(line)
print(dict(sorted(stats.items())))
print("model decisions:", len(adj), "| rows with flags:", sum(1 for r in rows if r[FL]))
print(collections.Counter(f.split(":")[0].split(" (")[0] for r in rows for f in r[FL].split("; ") if f).most_common())
