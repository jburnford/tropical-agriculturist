#!/usr/bin/env python3
"""Score an RA export of the person check against the frozen gold set. Measurement only: nothing in the
authority table is changed; disagreements are written out for discussion before any correction is applied.

    python3 score_gold.py person_check_<name>_<date>.tsv

1. Validate: every row's dataset fingerprint = manifest.json; each gid/pid pair and each mention_key exists in
   gold_profiles.tsv / gold_mentions.tsv; no duplicates. Any mismatch -> refuse (exit 2), score nothing.
2. Preserve: copy the export unchanged to returns/ and record its sha256.
3. Score, keeping stages and strata apart (the sample oversamples auto/review; see manifest.json):
   - first pass: precision of first-pass auto QIDs (stratum "auto");
   - final asserted QID, by source (wd_auto, model_adjudicated, colist_kg): precision;
   - final "no QID": share where the RA found the person in Wikidata (missed identities);
   - model decisions (LINK / NONE / MIXED / UNSURE) vs the RA;
   - profile purity: RA "one person" vs "mixed", and agreement with the model's MIXED;
   - sampled records by resolution method: the RA's 1-5 certainty that the record is this person
     (1 certainly not, 2 probably not, 3 can't tell, 4 probably, 5 certainly); reported as the full distribution
     and as the share rated 4-5 among records rated 4-5 or 1-2 (3 = can't tell, excluded). A diagnostic sample,
     not a random sample of all records.
   Unanswered and "can't tell" are counted separately and excluded from rates. Rates carry Wilson 95% intervals.
   A population-weighted figure is given only for one stated estimand.
4. Write results/<dataset>_<student>_<date>.md and ..._disagreements.tsv."""
import csv, json, sys, pathlib, hashlib, shutil, collections, math, re, datetime
here = pathlib.Path(__file__).resolve().parent


class Invalid(Exception):
    pass


def tsv(p):
    return list(csv.DictReader(open(p), delimiter="\t", quoting=csv.QUOTE_NONE))


def wilson(k, n, z=1.96):
    if n == 0:
        return "—"
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return f"{k}/{n} = {p:.0%} (95% CI {max(0, c - h):.0%}–{min(1, c + h):.0%})"


def load(path, gold_dir=here):
    """Validate an export against the frozen gold set; returns (manifest, profiles, mentions, answers)."""
    man = json.load(open(gold_dir / "manifest.json"))
    gp = {r["gid"]: r for r in tsv(gold_dir / "gold_profiles.tsv")}
    gm = {r["mention_key"]: r for r in tsv(gold_dir / "gold_mentions.tsv")}
    rows = tsv(path)
    if not rows or "dataset" not in rows[0]:
        raise Invalid("not an export of this checklist (no dataset column)")
    bad = {r["dataset"] for r in rows} - {man["dataset"]}
    if bad:
        raise Invalid(f"export is for dataset {sorted(bad)}, gold set is {man['dataset']}")
    if "mention_certainty" not in rows[0]:
        raise Invalid("export from the yes/no version of the page: load it into the current page, re-rate the "
                      "flagged records 1-5, and export again")
    people, ments, seen = {}, {}, set()
    for r in rows:
        g = gp.get(r["gid"])
        if g is None or g["pid"] != r["pid"]:
            raise Invalid(f"row {r['gid']}/{r['pid']} does not match the gold set")
        key = (r["row_type"], r["gid"], r.get("mention_key", ""))
        if key in seen:
            raise Invalid(f"duplicate row {key}")
        seen.add(key)
        if r["row_type"] == "person":
            people[r["gid"]] = r
        elif r["row_type"] == "mention":
            if r["mention_certainty"] not in ("", "1", "2", "3", "4", "5"):
                raise Invalid(f"certainty {r['mention_certainty']!r} is not 1-5 for {r['mention_key']}")
            m = gm.get(r["mention_key"])
            if m is None or m["gid"] != r["gid"]:
                raise Invalid(f"mention {r['mention_key']} does not belong to {r['gid']} in the gold set")
            ments[r["mention_key"]] = r
        else:
            raise Invalid(f"unknown row_type {r['row_type']}")
    return man, gp, gm, {"people": people, "ments": ments, "rows": rows}


def human_identity(a):
    """-> Qnnn | none | ? | '' (unanswered)"""
    if not a:
        return ""
    q = (a.get("wd_qid") or "").strip()
    if a.get("wd_choice") in ("proposed", "other"):
        return q if re.fullmatch(r"Q\d+", q) else ""
    return {"none": "none", "unsure": "?"}.get(a.get("wd_choice", ""), "")


def model_decision(g):
    m = re.match(r"model (LINK|NONE|MIXED|UNSURE) ?(Q\d+)?", g.get("model_note", ""))
    return (m.group(1), m.group(2) or "") if m else ("", "")


def score(man, gp, gm, ans):
    P = ans["people"]; out = {}
    H = {g: human_identity(P.get(g)) for g in gp}
    decided = {g for g, h in H.items() if h not in ("", "?")}
    out["answered"] = {"people_with_identity_answer": sum(1 for h in H.values() if h), "cant_tell": sum(1 for h in H.values() if h == "?"),
                       "unanswered": sum(1 for h in H.values() if not h), "total": len(gp)}
    # first pass auto
    auto = [g for g in decided if gp[g]["stratum_first_pass"] == "auto"]
    out["first_pass_auto_precision"] = wilson(sum(1 for g in auto if gp[g]["first_pass_qid"] == H[g]), len(auto))
    # final asserted QID by source
    by_src = collections.defaultdict(list)
    for g in decided:
        if gp[g]["final_qid"]:
            by_src[gp[g]["final_qid_source"].split("+")[0]].append(g)
    out["final_precision_by_source"] = {s: wilson(sum(1 for g in gs if gp[g]["final_qid"] == H[g]), len(gs)) for s, gs in sorted(by_src.items())}
    allq = [g for gs in by_src.values() for g in gs]
    out["final_precision_all_asserted"] = wilson(sum(1 for g in allq if gp[g]["final_qid"] == H[g]), len(allq))
    noq = [g for g in decided if not gp[g]["final_qid"]]
    out["final_no_qid_but_ra_found_one"] = wilson(sum(1 for g in noq if H[g] != "none"), len(noq))
    # model decisions
    md = collections.defaultdict(lambda: collections.Counter())
    for g in decided:
        d, q = model_decision(gp[g])
        if not d:
            continue
        if d == "LINK":
            md[d]["agree" if q == H[g] else "disagree"] += 1
        elif d == "NONE":
            md[d]["agree" if H[g] == "none" else "disagree (RA found " + H[g] + ")"] += 1
        else:
            md[d]["RA: none" if H[g] == "none" else "RA: model's candidate" if H[g] == q else "RA: other QID"] += 1
    out["model_decisions_vs_ra"] = {k: dict(v) for k, v in md.items()}
    # purity
    pur = collections.Counter(); agree = collections.Counter()
    for g in gp:
        o = (P.get(g) or {}).get("one_person", "")
        pur[o or "unanswered"] += 1
        if o in ("y", "mixed"):
            agree[("model MIXED" if "mixed profile" in gp[g]["flags"] else "model not mixed") + " / RA " + o] += 1
    out["purity"] = dict(pur); out["purity_vs_model"] = dict(agree)
    # mentions by method
    mm = collections.defaultdict(collections.Counter)
    for k, m in gm.items():
        v = (ans["ments"].get(k) or {}).get("mention_certainty", "")
        mm[m["method"]][v or "unanswered"] += 1
    out["mentions_by_method"] = {}
    for meth, c in sorted(mm.items()):
        hi, lo = c["4"] + c["5"], c["1"] + c["2"]
        rated = [int(x) for x in "12345" for _ in range(c[x])]
        out["mentions_by_method"][meth] = {
            "certainty": {x: c[x] for x in "12345"}, "unanswered": c["unanswered"],
            "match_rate": wilson(hi, hi + lo), "mean": f"{sum(rated) / len(rated):.2f}" if rated else "—"}
    # one weighted estimand: tranche profiles whose final identity status (QID or none) matches the RA
    pop = man["population_first_pass"]; num = den = 0.0
    for s in pop:
        gs = [g for g in decided if gp[g]["stratum_first_pass"] == s]
        if gs:
            ok = sum(1 for g in gs if (gp[g]["final_qid"] or "none") == H[g])
            num += pop[s] * ok / len(gs); den += pop[s]
    out["weighted_final_status_match"] = (f"{num / den:.0%} (estimand: share of the {sum(pop.values())} tranche profiles with >=10 "
                                          f"records whose final identity status, QID or none, matches the RA; strata weighted by "
                                          f"first-pass population; excludes can't-tell/unanswered)") if den else "—"
    dis = [g for g in sorted(decided) if (gp[g]["final_qid"] or "none") != H[g]]
    return out, dis, H


def main(path):
    path = pathlib.Path(path)
    try:
        man, gp, gm, ans = load(path)
    except Invalid as e:
        print("REFUSED:", e); sys.exit(2)
    (here / "returns").mkdir(exist_ok=True); (here / "results").mkdir(exist_ok=True)
    keep = here / "returns" / path.name
    if not keep.exists():
        shutil.copy2(path, keep)
    sha = hashlib.sha256(keep.read_bytes()).hexdigest()
    out, dis, H = score(man, gp, gm, ans)
    student = ans["rows"][0]["student"]; when = ans["rows"][0]["exported_at"][:10]
    stem = f"{man['dataset']}_{re.sub(r'\W+', '_', student)}_{when}"
    mins = max(float(r["active_minutes"] or 0) for r in ans["rows"])
    lines = [f"# Person check results — {student}, exported {when}", "",
             f"Dataset {man['dataset']} (gold sampled at {man['source_commit_at_sampling']}); export preserved as "
             f"`returns/{path.name}` (sha256 {sha[:16]}…); active time {mins:.0f} min.", "",
             "Model decisions are a model's, the RA's are human; this report measures, it changes nothing.", "",
             "## Coverage", "", "```", json.dumps(out["answered"], indent=1), "```", "",
             "## Identity (Wikidata)", "",
             f"- First-pass auto links (stratum auto): {out['first_pass_auto_precision']}",
             f"- Final asserted QIDs, all sources: {out['final_precision_all_asserted']}"]
    lines += [f"  - {s}: {v}" for s, v in out["final_precision_by_source"].items()]
    lines += [f"- Final 'no QID' where the RA found one: {out['final_no_qid_but_ra_found_one']}",
              f"- Model decisions vs RA: `{json.dumps(out['model_decisions_vs_ra'])}`",
              f"- Weighted: {out['weighted_final_status_match']}", "",
              "## Profile purity", "", f"- RA answers: `{json.dumps(out['purity'])}`",
              f"- vs model MIXED: `{json.dumps(out['purity_vs_model'])}`", "",
              "## Sampled records by resolution method (diagnostic sample)", ""]
    lines += ["Certainty 1 certainly not · 2 probably not · 3 can't tell · 4 probably · 5 certainly. Match rate = rated 4–5 "
              "among those rated 4–5 or 1–2.", ""]
    lines += [f"- {k}: match {v['match_rate']}; mean {v['mean']}; ratings `{json.dumps(v['certainty'])}`; unanswered {v['unanswered']}"
              for k, v in out["mentions_by_method"].items()]
    lines += ["", f"## Disagreements ({len(dis)}): see `results/{stem}_disagreements.tsv`", ""]
    (here / "results" / f"{stem}.md").write_text("\n".join(lines) + "\n")
    with open(here / "results" / f"{stem}_disagreements.tsv", "w") as f:
        f.write("gid\tpid\tdisplay\tstratum\tfinal_qid\tfinal_source\tmodel_note\tra_identity\tra_one_person\tra_note\n")
        for g in dis:
            a = ans["people"].get(g, {})
            f.write("\t".join(str(x).replace("\t", " ") for x in [g, gp[g]["pid"], gp[g]["display"], gp[g]["stratum_first_pass"],
                    gp[g]["final_qid"] or "none", gp[g]["final_qid_source"], gp[g]["model_note"][:160], H[g],
                    a.get("one_person", ""), a.get("note", "")]) + "\n")
    print((here / "results" / f"{stem}.md").read_text())


if __name__ == "__main__":
    main(sys.argv[1])
