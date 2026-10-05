#!/usr/bin/env python3
"""Merge the array outputs (out/part_NN.jsonl, pulled from Trillium) into mentions.jsonl and report
coverage against jobs/part_NN.jsonl. Usage: collect.py  (run in ner/ after rsync of out/)."""
import json, pathlib, collections
jobs = {p.name: {json.loads(l)["id"] for l in open(p)} for p in sorted(pathlib.Path("jobs").glob("part_*.jsonl"))}
done = {}; dup = 0; errs = 0; ments = 0
with open("mentions.jsonl", "w") as out:
    for p in sorted(pathlib.Path("out").glob("part_*.jsonl")):
        for l in open(p):
            r = json.loads(l)
            if r["id"] in done: dup += 1; continue
            done[r["id"]] = p.name; errs += len(r["errors"]); ments += len(r["mentions"]); out.write(l if l.endswith("\n") else l + "\n")
for name, ids in jobs.items():
    n = sum(1 for i in ids if i in done)
    print(f"{name}: {n}/{len(ids)} articles done{'  COMPLETE' if n == len(ids) else ''}")
print(f"total {len(done)}/{sum(len(v) for v in jobs.values())} articles, {ments:,} mentions, {errs} chunk errors, {dup} duplicate lines skipped")
