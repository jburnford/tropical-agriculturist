#!/usr/bin/env python3
"""Stage 4, tier 2: match person profiles to the Colonial Office List KG (~/col_matching, Imperial Careers KG).

A CO List person is a candidate for a profile when:
  name     surname key equal; given names compatible with the profile's commonest printed form (initials vs full
           names, prefix order); a contradicting full given name rules it out ("John" vs "JAMES");
  period   the CO person's listed career (event years + List editions) overlaps the profile's core mention years
           (10th-90th percentile) within 5 years;
  place    the CO career has a Ceylon posting, or a posting in a place the profile co-occurs with.
Decision: auto = exactly one candidate passes AND its CO positions share a role word with the profile's roles
          ("director"+"agriculture", "veterinary", "botanic", "government agent"...);
          review = candidates pass but no role agreement, or several pass; none.
Output: colist/links.tsv (+ the CO person's own Wikidata QID when the KG has one)."""
import json, gzip, re, sys, collections, pathlib
here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent))
from parse import parse, given_compat, skey, DROP

KG = pathlib.Path.home() / "col_matching/data/kg/graph_stage3"
TITLES = {"sir", "hon", "rev", "dr", "capt", "major", "col", "lieut", "lt", "gen", "the", "mr", "mrs", "miss", "lord",
          "lady", "ven", "very", "right", "rt", "revd", "prof", "surgeon", "commander", "admiral", "count", "baron"}
ABBR = {"bot": "botanic", "agr": "agriculture", "agrl": "agriculture", "agric": "agriculture", "vet": "veterinary",
        "govt": "government", "gov": "government", "dir": "director", "asst": "assistant", "supt": "superintendent",
        "secy": "secretary", "sec": "secretary", "commr": "commissioner", "insp": "inspector", "dept": "department",
        "kach": "kachcheri", "ag": "agent", "g.a.": "government agent", "a.g.a.": "assistant government agent"}
STOP = {"author", "member", "present", "letter", "writer", "report", "paper", "the", "and", "for", "with", "from",
        "his", "her", "who", "was", "has", "had", "this", "that", "acting", "late", "former", "formerly", "mr",
        "ceylon", "colombo", "government", "assistant", "office", "officer", "signatory", "speaker", "board",
        "chairman", "committee", "meeting", "moved", "seconded", "attended", "resolution", "proposed", "president",
        "secretary", "vice", "honorary", "hony", "conference", "visitor", "correspondent", "contributor",
        # too generic to identify a career: shared only these, a match is not role evidence
        "public", "service", "colonial", "department", "official", "special", "district", "works", "attend",
        "attended", "attending", "member", "director", "managing", "deputy", "senior", "junior", "chief", "general",
        "majesty", "expert", "head", "first", "second", "class", "local", "provincial", "province", "western",
        "eastern", "northern", "southern", "central", "acting", "temporary", "additional", "officiating",
        "council", "councillor", "unofficial", "nominated", "elected", "representative", "proprietor", "owner"}
GENERIC_PLACES = {"england", "london", "india", "scotland", "ireland", "wales", "south", "north", "east", "west",
                  "british", "great", "britain", "europe", "france", "germany", "america", "united", "states",
                  "kingdom", "new", "island", "islands", "colony", "colonies", "empire", "world", "edinburgh",
                  "paris", "berlin", "holland", "australia", "africa", "asia", "china", "japan"}

def stems(text):
    out = set()
    for w in re.findall(r"[a-z][a-z.\-]+", text.lower()):
        w = ABBR.get(w.strip(".-"), w.strip(".-"))
        for x in w.split():
            if len(x) >= 4 and x not in STOP:
                out.add(x[:7])
    return out

def co_given(g):
    out = []
    for t in re.findall(r"[A-Za-z][A-Za-z'\-]*\.?", g or ""):
        b = t.strip(".").lower()
        if b in TITLES:
            continue
        out.append((b[0], None) if len(b) == 1 or t.endswith(".") and len(b) <= 2 else (b[0], b))
    return out

def co_skey(surname):
    toks = [t for t in re.split(r"\s+", (surname or "").strip()) if t]
    while len(toks) > 1 and toks[0].lower().strip(".") in DROP:
        toks = toks[1:]
    return skey(" ".join(toks))

# ---------------- load CO List KG -------------------------------------------------------------------------
co = {}; by_s = collections.defaultdict(list)
for l in open(KG / "persons.jsonl"):
    p = json.loads(l)
    sk = co_skey(p["surname"])
    if len(sk) < 2:
        continue
    p["g"] = co_given(p["given_names"]); p["sk"] = sk; p["ev"] = []
    co[p["person_id"]] = p; by_s[sk].append(p)
for l in open(KG / "career_events.jsonl"):
    e = json.loads(l)
    p = co.get(e["person_id"])
    if p is not None:
        p["ev"].append((e["year_start"], e["position"] or "", e["place_raw"] or "", e.get("colony_label") or ""))
for p in co.values():
    ys = [y for y, *_ in p["ev"] if y] + list(p["editions"] or [])
    p["lo"], p["hi"] = (min(ys), max(ys)) if ys else (None, None)
    p["ceylon"] = any("ceylon" in (c + " " + pl).lower() for _, _, pl, c in p["ev"])
    p["pos_stems"] = stems(" ".join(pos for _, pos, _, _ in p["ev"]))
    p["places"] = {w.lower() for _, _, pl, c in p["ev"] for w in re.findall(r"[A-Za-z]{4,}", pl + " " + c)}

# ---------------- profiles ---------------------------------------------------------------------------------
years = collections.defaultdict(list)
for l in gzip.open(here.parent / "out/mentions.tsv.gz", "rt"):
    f = l.rstrip("\n").split("\t")
    if len(f) > 9 and f[8] and f[2].isdigit() and f[2] != "0":
        years[f[8]].append(int(f[2]))
profiles = [json.loads(l) for l in gzip.open(here.parent / "out/profiles.jsonl.gz", "rt")]
profiles = [p for p in profiles if p["kind"] == "named" and p["mentions"] >= 3]

def name_check(pg, cg):
    if any(n for _, n in pg) and any(n for _, n in cg) and not given_compat(pg, cg):
        return False
    if not cg:
        return False
    return all(a[0] == b[0] and (a[1] is None or b[1] is None or a[1] == b[1]) for a, b in zip(pg, cg)) \
        and not any(n for _, n in pg[len(cg):])

out = []; dec = collections.Counter()
for p in profiles:
    dp = parse(p["display"])
    if dp["kind"] != "person" or not dp["given"]:
        continue
    ys = sorted(years.get(p["pid"]) or [p["first"], p["last"]])
    lo, hi = ys[len(ys) // 10], ys[(len(ys) * 9) // 10]
    pplaces = {w.lower() for pl, _ in p["places"] for w in re.findall(r"[A-Za-z]{4,}", pl)} - {"ceylon"} - GENERIC_PLACES
    prole = stems(" ".join(r for r, _ in p["roles"]))
    cands = []
    for c in by_s.get(p["skey"].split(":")[-1], []):
        if not name_check(dp["given"], c["g"]) or c["lo"] is None:
            continue
        if not (c["lo"] - 5 <= hi and lo <= c["hi"] + 5):
            continue
        if c["birth_year"] and c["birth_year"] > lo - 15:
            continue
        place_ok = c["ceylon"] or bool(pplaces & c["places"])
        if not place_ok:
            continue
        shared = sorted(prole & c["pos_stems"])
        cands.append((c, shared))
    if not cands:
        d, best, shared = "none", None, []
    else:
        withrole = [x for x in cands if x[1]]
        # a CO record with fewer given names than the profile ("JOHN" for "J. F. Anderson") is never auto
        if len(cands) == 1 and withrole and len(cands[0][0]["g"]) >= len(dp["given"]):
            d, (best, shared) = "auto", cands[0]
        elif len(withrole) == 1:
            d, (best, shared) = "review", withrole[0]
        else:
            d, (best, shared) = "review", sorted(cands, key=lambda x: -len(x[1]))[0]
    dec[d] += 1
    if best is None:
        continue
    cey = [f"{y} {pos}" for y, pos, pl, col in best["ev"] if "ceylon" in (col + pl).lower()][:3] or \
          [f"{y} {pos} ({pl})" for y, pos, pl, col in best["ev"]][:3]
    out.append([p["pid"], p["display"], p["mentions"], f"{p['first']}-{p['last']}", " | ".join(r for r, _ in p["roles"][:3]),
                d, best["person_id"], f"{best['given_names']} {best['surname']}", best["birth_year"] or "",
                f"{best['lo']}-{best['hi']}", " ; ".join(cey), ",".join(shared), best.get("wikidata_qid") or "",
                best.get("wikidata_label") or "", len(cands)])
with open(here / "links.tsv", "w") as f:
    f.write("pid\tdisplay\tmentions\tyears\troles\tdecision\tco_person_id\tco_name\tco_birth\tco_listed\tco_postings\t"
            "shared_role_words\tco_wikidata_qid\tco_wikidata_label\tn_candidates\n")
    for r in out:
        f.write("\t".join(str(x).replace("\t", " ") for x in r) + "\n")
print(f"profiles checked: {sum(dec.values())}; decisions: {dict(dec)}")
