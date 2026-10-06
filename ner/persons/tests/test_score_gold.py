"""Scorer validation: an export must match the frozen gold set exactly, or nothing is scored."""
import sys, pathlib, csv, json, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "gold"))
import pytest
import score_gold as sg

GOLD = pathlib.Path(sg.__file__).resolve().parent
COLS = ["dataset", "student", "gid", "pid", "row_type", "mention_idx", "mention_key", "one_person", "wd_choice", "wd_qid",
        "mention_certainty", "note", "active_minutes", "exported_at"]


def export(tmp_path, mutate=lambda r: r, answer=True):
    man = json.load(open(GOLD / "manifest.json"))
    gp = sg.tsv(GOLD / "gold_profiles.tsv"); gm = sg.tsv(GOLD / "gold_mentions.tsv")
    rows = []
    for g in gp:
        q = g["final_qid"]
        rows.append({"dataset": man["dataset"], "student": "T", "gid": g["gid"], "pid": g["pid"], "row_type": "person",
                     "mention_idx": "", "mention_key": "", "one_person": "y" if answer else "",
                     "wd_choice": ("proposed" if q else "none") if answer else "", "wd_qid": (q or "none") if answer else "",
                     "mention_certainty": "", "note": "", "active_minutes": "1.0", "exported_at": "2026-10-06T00:00:00Z"})
        for i, m in enumerate(x for x in gm if x["gid"] == g["gid"]):
            rows.append({**rows[-1], "row_type": "mention", "mention_idx": str(i), "mention_key": m["mention_key"],
                         "one_person": "", "wd_choice": "", "wd_qid": "", "mention_certainty": "5" if answer else ""})
    rows = [mutate(dict(r)) for r in rows]
    p = tmp_path / "e.tsv"
    with open(p, "w") as f:
        f.write("\t".join(COLS) + "\n")
        for r in rows:
            f.write("\t".join(r[c] for c in COLS) + "\n")
    return p


def test_valid_export_agreeing_with_pipeline(tmp_path):
    man, gp, gm, ans = sg.load(export(tmp_path))
    out, dis, H = sg.score(man, gp, gm, ans)
    assert dis == []
    assert out["final_precision_all_asserted"].startswith(f"{sum(1 for g in gp.values() if g['final_qid'])}/")


def test_unanswered_is_not_scored(tmp_path):
    man, gp, gm, ans = sg.load(export(tmp_path, answer=False))
    out, dis, H = sg.score(man, gp, gm, ans)
    assert out["answered"]["unanswered"] == len(gp) and dis == []


def test_wrong_dataset_refused(tmp_path):
    with pytest.raises(sg.Invalid):
        sg.load(export(tmp_path, mutate=lambda r: {**r, "dataset": "000000000000"}))


def test_mismatched_pid_refused(tmp_path):
    with pytest.raises(sg.Invalid):
        sg.load(export(tmp_path, mutate=lambda r: {**r, "pid": "P999999"} if r["gid"] == "G001" else r))


def test_unknown_mention_key_refused(tmp_path):
    with pytest.raises(sg.Invalid):
        sg.load(export(tmp_path, mutate=lambda r: {**r, "mention_key": "x#1"} if r["row_type"] == "mention" else r))


def test_certainty_out_of_range_refused(tmp_path):
    with pytest.raises(sg.Invalid):
        sg.load(export(tmp_path, mutate=lambda r: {**r, "mention_certainty": "y"} if r["row_type"] == "mention" else r))


def test_certainty_summary(tmp_path):
    vals = iter("5544332211" * 40)
    man, gp, gm, ans = sg.load(export(tmp_path, mutate=lambda r: {**r, "mention_certainty": next(vals)} if r["row_type"] == "mention" else r))
    out, _, _ = sg.score(man, gp, gm, ans)
    tot = collections.Counter()
    for v in out["mentions_by_method"].values():
        tot.update(v["certainty"])
    assert tot == {"1": 80, "2": 80, "3": 80, "4": 80, "5": 80}


def test_wilson():
    assert sg.wilson(0, 0) == "—"
    assert sg.wilson(9, 10).startswith("9/10 = 90%")
