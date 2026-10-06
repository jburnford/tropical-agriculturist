#!/usr/bin/env python3
"""Gold set for the RA check: 100 profiles from the grounding tranche (>= 10 records), stratified by the
FIRST-PASS Wikidata decision (35 auto, 35 review, 30 none), to measure
  (a) profile purity: are the records the build attached by inference really this person, and
  (b) identity precision: is the final asserted QID right (and, per stage: first pass, model, CO List KG).
The strata oversample auto/review relative to the tranche (see manifest.json for population sizes): report per
stratum, and weight explicitly if an aggregate estimate is wanted.

gold_profiles.tsv  one row per profile, with the pipeline's answers frozen at sampling time (hidden from the RA)
gold_mentions.tsv  up to 4 records per profile, preferring inferred links; each with a stable key
                   (article#extraction-index), the located scan page and a snippet
manifest.json      dataset fingerprint, population sizes, sample sizes, source commit
Reproducible: profiles are visited in sorted order and each profile's records are drawn with an RNG seeded by
its own key, so the same inputs always give the same sample."""
import json, gzip, re, random, collections, pathlib, csv, hashlib, subprocess
here = pathlib.Path(__file__).resolve().parent
P = here.parent
SEED = 20261005

def tsv(p):
    return list(csv.DictReader(open(p), delimiter="\t", quoting=csv.QUOTE_NONE)) if p.exists() else []

profiles = [json.loads(l) for l in gzip.open(P / "out/profiles.jsonl.gz", "rt")]
tranche = [p for p in profiles if p["mentions"] >= 10]
wd = {}
for l in open(P / "wd/out/candidates.jsonl"):
    r = json.loads(l); wd[r["pid"]] = r
final = {r["pid"]: r for r in tsv(P / "out/persons.tsv")}

by_dec = collections.defaultdict(list)
for p in sorted(tranche, key=lambda p: p["pid"]):
    by_dec[wd.get(p["pid"], {}).get("decision", "none")].append(p)
rng = random.Random(SEED)
strata = [("auto", 35), ("review", 35), ("none", 30)]
pick = []
for s, k in strata:
    pick += [(s, p) for p in rng.sample(by_dec[s], min(k, len(by_dec[s])))]
pids = {p["pid"] for _, p in pick}

ments = collections.defaultdict(list)
for l in gzip.open(P / "out/mentions.tsv.gz", "rt"):
    f = l.rstrip("\n").split("\t")
    if len(f) > 9 and f[8] in pids:
        ments[f[8]].append({"article": f[0], "idx": f[1], "year": f[2], "text": f[3], "role": f[5], "method": f[9]})
PREF = ["corpus_dominant", "corpus_unique", "corpus_honorific", "pool", "article", "norm", "explicit"]
sample = {}
for pid in sorted(pids):
    r = random.Random(f"{SEED}:{pid}")
    ms = sorted(ments[pid], key=lambda m: (m["article"], int(m["idx"])))
    r.shuffle(ms)
    chosen = []
    for m in PREF:                       # one per inferred method first, then fill
        chosen += [x for x in ms if x["method"] == m][:1]
    chosen += [x for x in ms if x not in chosen]
    sample[pid] = chosen[:4]

need = {m["article"] for v in sample.values() for m in v}
art = {}
for f in sorted((P.parent.parent / "articles/by_year").glob("articles_*.jsonl.gz")):
    for l in gzip.open(f, "rt", encoding="utf-8"):
        a = json.loads(l)
        if a["id"] in need:
            art[a["id"]] = a

def locate(a, surface):
    """-> (start, end, how) in the raw article text. how: exact | loose (case/spacing differs) |
    surname (only the surname located) | none."""
    t = a["text"]; s = surface.strip()
    i = t.find(s)
    if i >= 0:
        return i, i + len(s), "exact"
    m = re.search(r"\s+".join(re.escape(w) for w in s.split()), t, re.I)
    if m:
        return m.start(), m.end(), "loose"
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]+", s) if len(w) > 2]
    if words:
        m = re.search(r"\b" + re.escape(words[-1]) + r"\b", t, re.I)
        if m:
            return m.start(), m.end(), "surname"
    return None, None, "none"

def page_of(a, off):
    """Scan page holding character `off` of the article text (text = concatenated page segments)."""
    pos = 0
    for page, s, e in a["segments"]:
        if off < pos + (e - s):
            return page
        pos += e - s
    return a["segments"][-1][0]

def clean(x):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", x)).replace("|  |", "|").strip()

def snippet(a, st, en):
    t = a["text"]
    if st is None:
        return ""
    lo, hi = max(0, st - 240), min(len(t), en + 240)
    return ("…" if lo else "") + clean(t[lo:st]) + " [[" + clean(t[st:en]) + "]] " + clean(t[en:hi]) + ("…" if hi < len(t) else "")

LOCATE_NOTE = {"exact": "", "loose": "printed form differs slightly in case/spacing",
               "surname": "only the surname was found in the OCR text; check the scan",
               "none": "name not found in the OCR text; check the scan pages"}

order = sorted(pick, key=lambda x: (-x[1]["mentions"], x[1]["pid"]))
rows_p, rows_m = [], []
for n, (stratum, p) in enumerate(order, 1):
    g = f"G{n:03d}"; f = final.get(p["pid"], {})
    rows_p.append({"gid": g, "pid": p["pid"], "tap_id": f.get("id", ""), "kind": p["kind"], "display": p["display"],
                   "mentions": p["mentions"], "years": f"{p['first']}-{p['last']}", "stratum_first_pass": stratum,
                   "first_pass_qid": wd.get(p["pid"], {}).get("qid") or "",
                   "final_qid": f.get("wikidata_qid", ""), "final_qid_source": f.get("qid_source", ""),
                   "decided_by": f.get("decided_by", ""), "candidate_qids": f.get("candidate_qids", ""),
                   "flags": f.get("flags", ""), "model_note": f.get("note", "")})
    for m in sample[p["pid"]]:
        a = art[m["article"]]
        st, en, how = locate(a, m["text"])
        pg = page_of(a, st) if st is not None else None
        urls = {x["page"]: x["viewer_url"] for x in a["pages"]}
        rows_m.append({"gid": g, "pid": p["pid"], "mention_key": f"{m['article']}#{m['idx']}", "article": m["article"],
                       "idx": m["idx"], "method": m["method"], "year": m["year"], "surface": m["text"], "role": m["role"],
                       "located": how, "locate_note": LOCATE_NOTE[how], "page": pg if pg is not None else "",
                       "scan": urls.get(pg, "") if pg is not None else "",
                       "all_scans": " ".join(f"{k}={v}" for k, v in sorted(urls.items())),
                       "snippet": snippet(a, st, en)})

def write(path, rows):
    with open(path, "w") as fh:
        fh.write("\t".join(rows[0]) + "\n")
        for r in rows:
            fh.write("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in r.values()) + "\n")
write(here / "gold_profiles.tsv", rows_p)
write(here / "gold_mentions.tsv", rows_m)
fp = hashlib.sha256((json.dumps(rows_p, sort_keys=True) + json.dumps(rows_m, sort_keys=True)).encode()).hexdigest()[:12]
commit = subprocess.run(["git", "-C", str(P), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
json.dump({"dataset": fp, "seed": SEED, "source_commit_at_sampling": commit,
           "population_first_pass": {k: len(v) for k, v in by_dec.items()},
           "sample": dict(collections.Counter(s for s, _ in pick)), "profiles": len(rows_p), "mentions": len(rows_m),
           "located": dict(collections.Counter(r["located"] for r in rows_m))},
          open(here / "manifest.json", "w"), indent=2)
print(f"dataset {fp}: {len(rows_p)} profiles, {len(rows_m)} mentions; located:",
      dict(collections.Counter(r["located"] for r in rows_m)), "| methods:", dict(collections.Counter(r["method"] for r in rows_m)))
