"""Identity gate for the person authority table (used by combine.py; tested in tests/test_identity.py).

resolve() decides which external identities a profile may ASSERT, and which stay CANDIDATES. Rules, strongest
evidence first; disagreements are flagged, never silently resolved:

  model decision (fresh)   LINK    -> assert its QID (source model_adjudicated, decided_by model); a different
                                      CO List KG QID is flagged as a conflict
                           MIXED   -> assert NOTHING: no QID, no CO List person, no planter id. A valid QID does not
                                      make a mixed profile one person. All candidates kept; flagged for splitting
                           NONE    -> no QID; any rule-based QID kept as a candidate and flagged
                           UNSURE  -> no QID; the model's and the rules' QIDs kept as candidates and flagged
  model decision (stale: the profile changed since it was judged) -> not applied; flagged for re-adjudication
  no model decision        tier-1 Wikidata auto -> assert (source wd_auto, decided_by rule)
                           else CO List auto match whose KG record has a QID -> assert (source colist_kg)
                           tier-1 review never adjudicated -> candidate, flagged pending
Human decisions (RA review) will override all of the above once imported; none exist yet."""

def resolve(adj=None, adj_fresh=True, wd=None, co=None, pl=None, nonhuman=frozenset()):
    """adj: {decision, qid, confidence, evidence} or None; wd: tier-1 row {decision, qid, label} or None;
    co: CO List row {decision, co_person_id, co_wikidata_qid} or None; pl: planters row {decision, planter_ids, url}.
    Returns a dict of asserted ids, candidate QIDs, flags and a note."""
    out = {"qid": "", "qid_source": "", "qid_confidence": "", "decided_by": "", "candidates": [],
           "colist_person_id": "", "planter_id": "", "planter_url": "", "flags": [], "note": ""}
    wd_auto = wd["qid"] if wd and wd.get("decision") == "auto" and wd.get("qid") else ""
    co_auto = bool(co and co.get("decision") == "auto")
    co_qid = co.get("co_wikidata_qid", "") if co_auto else ""
    mixed = False

    def cand(q, why):
        if q and q not in [c.split(" ")[0] for c in out["candidates"]]:
            out["candidates"].append(f"{q} ({why})")

    if adj and not adj_fresh:
        out["flags"].append(f"stale model decision ({adj['decision']} {adj.get('qid', '')}): profile changed, re-adjudicate")
        cand(adj.get("qid"), "stale model decision")
        adj = None
    if adj:
        d = adj["decision"]
        out["note"] = f"model {d} {adj.get('qid', '')} ({adj.get('confidence', '')}): {adj.get('evidence', '')}"
        out["decided_by"] = "model"
        if d == "LINK" and adj.get("qid"):
            out.update(qid=adj["qid"], qid_source="model_adjudicated", qid_confidence=adj.get("confidence", ""))
            if co_qid and co_qid != adj["qid"]:
                out["flags"].append(f"qid_conflict: colist_kg {co_qid} vs model {adj['qid']}")
                cand(co_qid, "colist_kg")
            elif co_qid:
                out["qid_source"] += "+colist_kg"
        else:
            mixed = d == "MIXED"
            cand(adj.get("qid"), f"model {d}")
            cand(wd_auto, "wd_auto")
            cand(co_qid, "colist_kg")
            if mixed:
                out["flags"].append("mixed profile: identity links withheld until it is split")
            elif out["candidates"]:
                out["flags"].append(f"model {d}: candidate QID not asserted")
    elif wd_auto:
        out.update(qid=wd_auto, qid_source="wd_auto", qid_confidence="high", decided_by="rule")
        if co_qid and co_qid != wd_auto:
            out["flags"].append(f"qid_conflict: colist_kg {co_qid} vs wd_auto {wd_auto}")
            cand(co_qid, "colist_kg")
        elif co_qid:
            out["qid_source"] += "+colist_kg"
    elif co_qid:
        out.update(qid=co_qid, qid_source="colist_kg", qid_confidence="high", decided_by="rule")
    if not out["qid"] and wd and wd.get("decision") == "review" and not adj:
        cand(wd.get("qid"), "wd review, not adjudicated")
        out["flags"].append("pending adjudication")
    if co_auto and not mixed:
        out["colist_person_id"] = co.get("co_person_id", "")
    if pl and pl.get("decision") == "link" and not mixed:
        out["planter_id"], out["planter_url"] = pl.get("planter_ids", ""), pl.get("url", "")
    if out["qid"] in nonhuman:
        out["flags"].append("item is not typed as human (personification / legendary figure): check")
    return out


def jaccard(a, b):
    return len(a & b) / max(1, len(a | b))
