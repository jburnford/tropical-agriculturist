# Tropical Agriculturist — header/footer re-run plan (2026-09-29)

**Historical document.** This plan was carried out: the re-run produced `output_v6` (done 2026-10-04).
Kept as the record of what was planned; the text below is as written on 2026-09-29.

## What went wrong before (both times)

| Run | Output | Result |
|---|---|---|
| Sep 12 | `output` | Defaults: `Page-Header`/`Page-Footer` blocks dropped, no page breaks |
| Sep 13 | `output_v2` | Flag added to `run_volume_trillium.slurm`, but the job ran `run_chunk_trillium.slurm`, which didn't have it. ~40 GPU-h producing identical output |
| Sep 14 | `output_v3` | Test of the patched chunk script, 1 chunk only. **Worked, never evaluated** (below) |

Both failures had the same cause: success was declared from a check that could
not have detected failure.

## Evidence gathered today (read-only)

1. **The fix works in the script that will run.** `output_v3` (chunk 30, 39 docs, 2,448 pp) vs `output`:
   - page markers: 0 → **2,409** (= pages − 1 for every document)
   - folio lines: 37 → **1,511** bare numbers, 0 → **733** fused heads (`124[MARCH, 1919.`)
   - Local and remote `run_chunk_trillium.slurm` md5 match: `a475b9b2…`
2. **Titles: the effect depends on era.** 1917–41 monthlies already had titles as body headings in v1, so no change there. In the 1942 quarterly (`output_hdr`, vol098_iss02) the flag added 9 headings, 8 of them article titles.
3. **Bound volumes 1881–1915 (most of the pages) have never been tested with the flag.**
4. **A second silent loss: the output-token cap.** Chandra 0.2.0 caps each page at 12,384 tokens. In v1, **66 pages hit the cap exactly** (88 are ≥ 12,000), mostly in vols 011–021. One v3 page (vol067_iss03 p63) is cut off mid-table. Headers add tokens, so this would get worse. Fix: `--max-output-tokens 24000`, with vLLM `--max-model-len 40000` (the model supports 262k).
5. **No shortcut.** The v1 `.html` has no `data-label` attributes, so the headers are gone and only a re-run recovers them.
6. Trillium GPU fair share is **0.26**. v2 cost ~40 GPU-h; expect roughly 45–55 this time, because of more tokens per page.

## Changes to the script (before any GPU use)

1. **Use one script.** Retire `run_volume_trillium.slurm` and do all tests through `run_chunk_trillium.slurm` with a small chunk file. Add an optional 4th TSV column for `--page-range`.
2. **Hard-code the flags** (no `${VAR:-default}` override): `--include-headers-footers --paginate_output --max-output-tokens 24000`. Echo the full `chandra` command line into the job log.
3. **Build in a check that fails if the flags are missing.** After each document:
   - page markers must equal pages − 1, otherwise the document FAILS
   - folio-bearing pages (number in the first/last 3 lines of a page) must be ≥ 50%, otherwise it FAILS
   - count pages that hit the new cap and report them
   - **If the first document in a job fails, the job exits immediately.** A missing flag then costs one document, not a corpus.
4. **Refuse to write into an existing output dir.** New `OUTDIR=output_v4`. The idempotent skip would otherwise report "all complete, nothing to do" as success on an old tree.
5. Size walltimes from **measured v2 elapsed per chunk** (same chunk files) × 1.5, not from a rate estimate.
6. rsync to Trillium, then show `md5sum` and `grep` of the flag lines **from the remote copy** before any `sbatch`.

## Stages, each gated on Jim's approval

**Stage 1: bound-volume smoke test** (`debug` partition, ~0.5 GPU-h).
Slices by `--page-range`: vol020 (the 1894 volume with the known DocAI running head `468 | THE TROPICAL AGRICULTURIST. | [JAN. 1, 1894.`), including pages that hit the cap in v1, plus ~30 ordinary pages from vol003 and vol043.
Success criteria, fixed before launch:
- markers = pages − 1
- running head present on ≥ 80% of body pages; the folio sequence increases by 1, cross-checked against the DocAI page index where available
- previously capped pages now end in complete text, with none at the new cap
- body text vs v1 on the same pages differs only by the added furniture. The baseline is 0.002% word difference between two runs.

I show the command output. Jim decides.

**Stage 2: chunk 1 only** (the largest bound volumes). Check the **first completed document** while the job is still running, against the Stage 1 criteria. Jim decides.

**Stage 3: chunks 2–30**, `--array=2-30%8`. The in-script check aborts any task whose first document fails. I report the first completed document of each task as it lands.

**Stage 4: corpus verification** before anything is called done: per-document marker equality, folio coverage per volume, count of pages at the cap, body-text diff vs v1, 253/253 present. Pull to local as `output_v4`. **Leave `output` untouched.**

## Decisions for Jim

- **Re-run the 39 docs in `output_v3`, or keep them?** One page there is truncated by the old cap. Recommend: re-run them (~1 GPU-h), so the whole corpus has one configuration.
- **Stage 1 on Trillium `debug` vs Plato.** Recommend Trillium: the test has to run on the exact script and hardware that the production run will use.
