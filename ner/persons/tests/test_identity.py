"""Identity gate tests, including review defect 1: MIXED/UNSURE/NONE must never become an asserted QID."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from identity import resolve

CO = {"decision": "auto", "co_person_id": "kgp_x", "co_wikidata_qid": "Q3181373"}
PL = {"decision": "link", "planter_ids": "11111128", "url": "https://example.org/p"}


def test_mixed_with_colist_qid_asserts_nothing():          # John Douglas P000704 in v1
    r = resolve(adj={"decision": "MIXED", "qid": "", "confidence": "medium", "evidence": "two careers"}, co=CO, pl=PL)
    assert r["qid"] == "" and r["colist_person_id"] == "" and r["planter_id"] == ""
    assert any(c.startswith("Q3181373") for c in r["candidates"])
    assert any("mixed profile" in f for f in r["flags"])


def test_unsure_with_colist_qid_is_candidate_and_flagged():  # E. B. Denham P000175 in v1
    r = resolve(adj={"decision": "UNSURE", "qid": "Q1291745", "confidence": "low", "evidence": "?"},
                co={"decision": "auto", "co_person_id": "kgp_d", "co_wikidata_qid": "Q1291745"})
    assert r["qid"] == ""
    assert r["candidates"] and r["flags"]
    assert r["colist_person_id"] == "kgp_d"        # the CO List person match itself is not withheld (not mixed)


def test_none_keeps_rule_qid_as_candidate():
    r = resolve(adj={"decision": "NONE", "qid": "", "confidence": "medium", "evidence": ""},
                wd={"decision": "auto", "qid": "Q1", "label": "x"})
    assert r["qid"] == "" and r["candidates"] == ["Q1 (wd_auto)"]


def test_link_asserts_and_flags_conflict():
    r = resolve(adj={"decision": "LINK", "qid": "Q9", "confidence": "high", "evidence": ""}, co=CO)
    assert r["qid"] == "Q9" and r["qid_source"] == "model_adjudicated" and r["decided_by"] == "model"
    assert any("qid_conflict" in f for f in r["flags"])


def test_link_agreeing_with_colist():
    r = resolve(adj={"decision": "LINK", "qid": "Q3181373", "confidence": "high", "evidence": ""}, co=CO)
    assert r["qid_source"] == "model_adjudicated+colist_kg" and not r["flags"]


def test_stale_decision_not_applied():
    r = resolve(adj={"decision": "LINK", "qid": "Q9", "confidence": "high", "evidence": ""}, adj_fresh=False)
    assert r["qid"] == "" and any("stale" in f for f in r["flags"])


def test_rule_paths():
    assert resolve(wd={"decision": "auto", "qid": "Q5", "label": ""})["qid_source"] == "wd_auto"
    assert resolve(co=CO)["qid_source"] == "colist_kg"
    r = resolve(wd={"decision": "review", "qid": "Q7", "label": ""})
    assert r["qid"] == "" and "pending adjudication" in r["flags"]


def test_nonhuman_flag():
    r = resolve(adj={"decision": "LINK", "qid": "Q742971", "confidence": "medium", "evidence": ""},
                nonhuman=frozenset({"Q742971"}))
    assert r["qid"] == "Q742971" and any("not typed as human" in f for f in r["flags"])
