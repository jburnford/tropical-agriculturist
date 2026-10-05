#!/usr/bin/env python3
"""
Pack the deduped manifest into chunk files, one per SLURM array task.

Chunking is by *page budget*, not document count. The corpus mixes 66-page
monthly issues with 1,418-page bound volumes, so a fixed docs-per-job packing
produces jobs that differ by 20x in runtime -- and the walltime then has to
cover the worst case for every job.

Each chunk is processed by a single vLLM server. That is the whole point: at
40.1 pages/min a 72-page issue is 1.8 minutes of OCR against 2.6 minutes of
server startup, so one-document-per-job spends 29% of the allocation starting
servers it immediately throws away.

Packing also limits the blast radius of a walltime overrun. Chandra writes a
document's output only when its last page finishes, so a job that runs out of
time loses whatever it was working on -- but with a loop, every document that
already finished has been written.
"""
import argparse, math, pathlib, sys

ap = argparse.ArgumentParser()
ap.add_argument("--manifest", default="/scratch/jic823/tropical/manifest.dedup.tsv")
ap.add_argument("--outdir",   default="/scratch/jic823/tropical/chunks")
ap.add_argument("--budget",   type=int, default=2500, help="target pages per chunk")
ap.add_argument("--rate",     type=float, default=40.1, help="measured pages/min")
ap.add_argument("--safety",   type=float, default=1.6, help="margin for repeat-token retries")
a = ap.parse_args()

docs = []
for line in open(a.manifest):
    if line.startswith("#"):
        continue
    f = line.rstrip("\n").split("\t")
    if len(f) >= 3:
        docs.append((f[0], f[1], int(f[2])))

# Largest first: a greedy descending pack keeps the big volumes from being
# stranded together in a final oversized chunk.
docs.sort(key=lambda d: -d[2])

chunks, cur, cur_pages = [], [], 0
for d in docs:
    if cur and cur_pages + d[2] > a.budget:
        chunks.append(cur)
        cur, cur_pages = [], 0
    cur.append(d)
    cur_pages += d[2]
if cur:
    chunks.append(cur)

out = pathlib.Path(a.outdir)
out.mkdir(parents=True, exist_ok=True)
for old in out.glob("chunk_*.tsv"):
    old.unlink()

worst = 0
for i, ch in enumerate(chunks, 1):
    p = out / f"chunk_{i:03d}.tsv"
    with open(p, "w") as fh:
        for tag, pdf, pages in ch:
            fh.write(f"{tag}\t{pdf}\t{pages}\n")
    worst = max(worst, sum(d[2] for d in ch))

startup = 3.0
mins = worst / a.rate * a.safety + startup
h, m = divmod(math.ceil(mins), 60)
print(f"documents : {len(docs)}  pages: {sum(d[2] for d in docs):,}")
print(f"chunks    : {len(chunks)}  -> {a.outdir}/chunk_001..{len(chunks):03d}.tsv")
print(f"largest   : {worst:,} pages")
print(f"walltime  : {h}:{m:02d}:00  ({worst:,}pp / {a.rate} pp-min x {a.safety} + {startup:.0f}min startup)")
print(f"\nsubmit with --array=1-{len(chunks)}%<concurrency>")
