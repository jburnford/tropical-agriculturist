"""Regression tests for person grounding. Run: python3 -m pytest ner/persons/tests -q
Includes the two defects confirmed by the 2026-10-06 review (tropical-project-review-2026-10-06.md)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from parse import parse, display, given_compat, supported_given


# ---------------- stage 1: parsing ----------------------------------------------------------------------
@pytest.mark.parametrize("text,norm,kind,disp,skey", [
    ("Mr. F. G. A. LANE", "F. G. A. Lane", "person", "F. G. A. Lane", "lane"),
    ("Mr. Petch", "T. Petch", "person", "T. Petch", "petch"),
    ("Asst. Govt. Agent, Puttalam", "Assistant Government Agent, Puttalam", "title", "", ""),
    ("Peiris, H. C.", "H. C. Peiris", "person", "H. C. Peiris", "peiris"),
    ("Tissot, C. L.", "Tissot, C. L.", "person", "C. L. Tissot", "tissot"),
    ("President and Mrs. Cleveland", "President and Mrs. Cleveland", "title", "", ""),
    ("Messrs. H. G. Turner and Wolfe-Murray", "", "list", "", ""),
    ("W. S.", "W. S.", "initials", "", ""),
    ("JOHN HUGHES, F.I.C.", "John Hughes", "person", "John Hughes", "hughes"),
    ("F. A. STOCKDALE, C.B.E., M.A., F.L.S.", "", "person", "F. A. Stockdale", "stockdale"),
    ("Gate Mudaliyar A. E. Rajapakse", "A. E. Rajapakse", "person", "A. E. Rajapakse", "rajapakse"),
    ("W. A. DE SILVA", "W. A. de Silva", "person", "W. A. de Silva", "desilva"),
    ("Director of Agriculture", "", "title", "", ""),
    ("Minister for Agriculture and Lands", "", "title", "", ""),
    ("Wm. Mackenzie", "", "person", "William Mackenzie", "mackenzie"),
    ("King Edward", "", "person", "King Edward", "king:edward"),
    ("Dr. King", "King", "person", "King", "king"),
    ("Lord Derby", "", "person", "Lord Derby", "lord:derby"),
    ("Green, E. E.", "E. E. Green", "person", "E. E. Green", "green"),
    ("J. L. Shand, junr.", "", "person", "J. L. Shand Jr.", "shand"),
    ("C.DRIEBERG", "", "person", "C. Drieberg", "drieberg"),
    ("Baron von Mueller", "", "person", "von Mueller", "mueller"),
])
def test_parse(text, norm, kind, disp, skey):
    p = parse(text, norm)
    assert p["kind"] == kind
    if kind == "person":
        assert display(p) == disp
        assert p["skey"] == skey


def test_parse_honorific_and_suffix():
    p = parse("F. A. STOCKDALE, C.B.E., M.A., F.L.S.")
    assert p["suffix"] == ["cbe", "ma", "fls"]
    p = parse("Mrs. Christison", "Mrs. Christison")
    assert p["hon"] == ["mrs"] and p["gender"] == "f"
    assert parse("J. L. Shand, junr.")["gen"] == "jr"


# ---------------- name compatibility -----------------------------------------------------------------------
@pytest.mark.parametrize("a,b,ok", [
    ("J. Shand", "J. L. Shand", True),          # prefix
    ("W. Shand", "J. L. Shand", False),
    ("John Hughes", "J. Hughes", True),
    ("John Hughes", "James Hughes", False),
    ("Kelway Bamber", "M. Kelway Bamber", True),  # subsequence through a matching full name
    ("L. Shand", "J. L. Shand", False),          # subsequence of initials only is not enough
])
def test_given_compat(a, b, ok):
    assert given_compat(parse(a)["given"], parse(b)["given"]) is ok


# ---------------- review defect 2: model-supplied given names need source support ---------------------------
@pytest.mark.parametrize("name,source,status,kept", [
    # the review's three probes: none may validate the expanded name
    ("James Watt", "Mr. J. Watt writes about tea.", "initials", [("j", None)]),
    ("Henry Trimen", "Mr. H. Trimen writes about tea.", "initials", [("h", None)]),
    ("John Smith", "Mr. John Smithson writes about tea.", "none", []),
    # the review's corpus case: "Sir F. von Mueller" does not print "Ferdinand"
    ("Ferdinand von Mueller", "Sir F. von Mueller wrote", "initials", [("f", None)]),
    # positive cases
    ("James Watt", "Dr. James Watt said", "full", [("j", "james")]),
    ("James Watt", "JAMES WATT, F.R.S.", "full", [("j", "james")]),
    ("T. Petch", "by T. PETCH, Mycologist", "full", [("t", None)]),
    ("E. E. Green", "Green, E. E., on scale insects", "full", [("e", None), ("e", None)]),
    # partial support keeps what is printed, per position
    ("Edward Ernest Green", "E. Ernest Green, Entomologist", "initials", [("e", None), ("e", "ernest")]),
    # printed abbreviations count as the full name
    ("Wm. Robinson", "*Robinson, Wm., of Gowhatti*", "full", [("w", "william")]),
    ("Wm. Thompson", "the company of Mr. Wm. Thompson, jur., of", "full", [("w", "william")]),
    # no support
    ("James Watt", "J. Smith and Watt", "none", []),
    ("H. F. C. Trimen", "Dr. Trimen said", "none", []),
    ("James Watt", "Mr. Watts wrote", "none", []),
])
def test_supported_given(name, source, status, kept):
    given, st = supported_given(parse(name), source)
    assert st == status
    assert given == kept
