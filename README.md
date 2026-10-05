# The Tropical Agriculturist (Colombo, 1881–1945): OCR corpus and article index

Code and evidence for OCR'ing every digitised volume of *The Tropical Agriculturist* with
Chandra 2 and splitting the result into page-linked articles.

**Current state (2026-10-04).** The OCR corpus (`output_v6`, 253 documents, 63,680 pages) and the
article file (`articles/articles.jsonl`, 54,259 canonical articles) are complete. Neither is in this
repository because of size; they live on Trillium `/scratch/jic823/tropical` and on the local
working copy. **Start with [`articles/README.md`](articles/README.md)** for the article file's
fields, the build pipeline and the measured accuracy. `RERUN_PLAN.md` and the `stage4/`, `repair/`
scripts document the header/footer re-run and the per-page repairs (faint pages, show-through,
summarised and side-by-side tables) that produced `output_v6` from the first run.

**Browse the articles:** `viewer/index.html` — by year and issue, every article with its text and the
archive.org page images beside it, plus a random-sample button for spot checks. Online at
<https://jburnford.github.io/tropical-agriculturist/viewer/> (GitHub Pages), or locally:

```bash
python3 -m http.server 8000
```

then open <http://localhost:8000/viewer/>. It reads `articles/by_year/*.jsonl.gz` directly; no build step.

**What is backed up here:** the OCR corpus `output_v6/` (253 documents, 63,680 pages: markdown, HTML,
page metadata, extracted images), the article file split per year in `articles/by_year/`, the heading
skeletons and labels the split was built from, and `output_v5_diff/` to rebuild the previous corpus
version. Not here: the September v1 corpus (`output/`, made without headers/footers; superseded) and the
raw IA PDFs (on Trillium and Nibi; re-downloadable from archive.org).

The rest of this file is the original inventory/download/submit README from September 2026.

---

## Inventory and OCR submission (September 2026)

Gather every digitised copy of *The Tropical Agriculturist* (Colombo, 1881–1960s)
and OCR it with Chandra 2 on the Nibi cluster.

## Status

As of 2026-09-11:

- **Inventory complete** — 693 IA items reconciled to 110 volumes (vol 1–117).
- **Downloaded** — 312 PDFs, 8.2 GB, at `/project/def-jic823/tropical/pdfs`.
- **Submitted** — 269 documents / 76,252 pages as SLURM arrays `21747929`
  (b2h, 219), `21747930` (b4h, 49), `21747932` (b8h, 1), at `CONCURRENCY=8`.
  All pending on `Priority`; SLURM estimated a 2026-09-13 start.
- **Scope** — volumes 1–101, i.e. up to 1945. The 1946–1961 volumes are
  downloaded but deliberately excluded from OCR (`04_manifest.py --volumes
  1-101`).
- **Outstanding gaps** — volumes 24, 25, 29, 36 (c. 1904–1911) are on no
  Archive.org copy; see below.
- **Not yet run** — `10_extract_docai.py` / `11_page_index.py`, which need the
  external SSD mounted in WSL.

Check progress with:

```bash
ssh nibi 'BASE=/project/def-jic823/tropical bash /project/def-jic823/tropical/06_status.sh'
```

## What the journal is, bibliographically

Founded June 1881 in Colombo as *The Tropical Agriculturist: a Monthly Record of
Information for Planters*, later *…and Magazine of the Ceylon Agricultural
Society*. One volume a year through 1912 (volume *N* spans (1880+N)–(1881+N)),
then **two volumes a year** from 1913. That break is why volume numbers cannot be
derived from dates alone, and why `02_inventory.py` learns the mapping from the
data instead of hardcoding it.

## Sources

It was digitised at least five times over by unrelated projects, so the same
volume appears under wholly different identifier schemes:

| Family | Identifier shape | Level | Notes |
|---|---|---|---|
| `cornell` | `tropicalagricult1518ceyl` | volume | Cornell/BHL. Best scans; the 1880s–1900s run |
| `lbg` | `lbg.630.5.tag.v.37` | volume | Indian library shelf-marks. **Title metadata is unreliable** — `…tag.v.71` is titled "Vol-VI" |
| `dli` | `dli.ernet.229230` | volume | Digital Library of India; opaque accession numbers, roman numerals in the title |
| `unse` | `tropicalagricult0054unse` | volume | |
| `per-issue` | `tropical-agriculturist_1915-06_44_6` | issue | Covers the whole run, including the post-1920 volumes the others miss |
| `tdl` | `tdl.34540-…` | issue | Tamil Digital Library. **Volume/issue appear only in the *filename*** (`…_Vol_37_no_2_1911.pdf`), never in the metadata |

`02_inventory.py` picks **one** copy per volume, preferring a volume-level scan
(one OCR job, continuous pagination) over stitching six issue scans together.

### Traps this corpus sets

Each of these cost a wrong answer before it was fixed, so they are all
regression-tested by the rules in `ta_common.py`:

- **`advancedsearch.php` silently under-returns.** Paging it has no stable sort,
  so consecutive pages overlap and drift — a three-page run returned 671 unique
  items against a reported `numFound` of 694. `01_enumerate.py` uses the
  cursor-based `scrape` service instead, which returns all 715.
- **Title metadata loses to the identifier.** `lbg.630.5.tag.v.71` is titled
  "Vol-VI" but is volume 71 (its 1928 date agrees). Identifier-embedded numbers
  are trusted first; roman numerals in titles are a last resort.
- **Works that merely share the name.** `tropicalagricul01portgoog` (1833) is
  G. R. Porter's treatise on sugar cane; `tropicalagricult0000*` items from the
  1960s–90s are unrelated *Tropical Agriculture* textbooks. Filtered by
  `is_the_journal()` and a volume range guard.
- **The Colombo imprints carry no volume number**, only a year range
  (`"1884-1885"`), resolved via the pre-1913 one-volume-a-year rule.
- **Free-text dates.** `"April-May 1926"` yielded a year of `"Apri"` until the
  parser was made to demand four digits.
- **A volume/year regression check** (`volume_year_outliers`) flags anything
  more than ~12 years off the series trend line. Diagnostic only — nothing is
  dropped on its basis. It is what caught the Trinidad journal. Note its
  sensitivity is limited: IA's `year` field is unreliable for the Cornell
  items, many of which report the series start year rather than the volume's
  own (volumes 28, 30, 35 and 37 all claim 1905), so a genuinely mislabelled
  early volume could slip past it. Volume resolution itself does not depend on
  `year` — only this check does.

## Pipeline

```bash
python3 01_enumerate.py                        # IA -> inventory/ia_meta.jsonl
python3 02_inventory.py                        # -> ta_manifest.csv, coverage.txt
python3 03_download.py --out $BASE/pdfs        # on a Nibi LOGIN node
python3 04_manifest.py --pdfs $BASE/pdfs --out $BASE/manifest.tsv
bash    05_submit.sh --dry-run                 # check before committing
bash    05_submit.sh                           # bucketed arrays on MIG slices
bash    06_status.sh                           # progress
bash    06_status.sh --failed                  # documents needing a retry
```

`BASE` defaults to `/project/def-jic823/tropical` throughout. Steps 1–2 run
anywhere and are cached; only step 3 needs internet, which is why it must run on
a login node — Nibi compute nodes have none, and the model is pre-staged with
`HF_HUB_OFFLINE=1`.

Every step is resumable. A volume counts as done only when it has a non-empty
`.md`, so re-running `05_submit.sh` after any failure submits only what is left.

`05_submit.sh` is also safe to run *while a round is still in the queue*. It
skips not only finished volumes but any tag that already has a pending or
running array task, reconstructed by mapping live array job ids back through
the tasklist snapshots saved at submission time. Without that check the script
skipped only *finished* work, so re-running it mid-round would resubmit every
outstanding volume as a duplicate and bump each one's attempt count, pushing it
into a longer bucket for no reason. Verified against a live queue of 269
documents: it correctly submitted nothing.

`06_status.sh` separates **done / in queue / needs retry** for the same reason.
Because attempts are recorded at submission time, a status check consulting only
the attempts file reports a freshly queued round as "attempted, no output" —
which reads as total failure when nothing has actually run. It also prints
observed pages/min once tasks complete, with the `--rate` value to feed back
into `04_manifest.py` if the buckets need re-budgeting.

## Why MIG slices

`run_volume.slurm` asks for `nvidia_h100_80gb_hbm3_3g.40gb:1`, not a whole H100.
Chandra 2 is a ~8B VLM: bf16 weights plus a working KV cache fit inside 40 GB.
`--max-num-seqs` is halved to 32 to match the smaller cache — 64 on a 40 GB
slice makes vLLM either preempt constantly or refuse to start.

**Slices do not currently queue faster, and that is not why we use them.**
Measured on 2026-09-11, the 3g.40gb pool was contended about as hard as the
whole cards:

| request | pending | running | pool size |
|---|---|---|---|
| `gpu:h100:1` | 732 | 64 | 232 cards (g1–29) |
| `3g.40gb:1` | 253 | 8 | 56 slices (g30–36) |

That is ~3.2 jobs deep per whole card against ~4.5 per slice. The real
constraint is our own fair share, which sat at **0.22** for
`def-jic823_gpu` — and that is what puts these jobs behind, not the slice size.

The argument for slices is **cost**, which is also what recovers fair share
fastest: `sacct` bills a 3g.40gb job at 10,457 against 12,200 for a whole
H100, for a job that measurably runs at 14.3 pages/min (see below). A whole
card would cost ~17% more billing per volume for throughput we do not need,
and would deplete an already-low fair share faster.

Jobs are submitted to `gpubase_bygpu_b1,gpubackfill`, so they are backfill-
eligible. SLURM's `--start` estimate is a pessimistic upper bound: the cluster
completed 10,305 jobs in the six hours before submission, so the queue drains
far faster than the estimate suggests.

**The planning rate is measured, not assumed.** The `sessional_papers` corpus
was already run on these same 3g.40gb slices (job `20413297`, 132 completed
tasks of 858–1,962 pages), giving:

| gross pages/min, incl. model load | |
|---|---|
| p10 | 9.2 |
| median | 14.3 |
| p90 | 25.2 |
| slowest volume observed | 6.5 |

So the slices are *faster* than the 9 pages/min once quoted for a whole H100 —
that figure came from an older run and should not be reused. `04_manifest.py`
budgets at the **p10 (9.2)**, not the median: nine volumes in ten then finish
comfortably, and a 1,200-page volume gets 208 minutes, which still covers the
worst rate ever seen here.

This matters because Chandra writes a document only when its *last* page
finishes — a volume that overruns its walltime produces **nothing**, and there is
no checkpointing. If one does overrun, `05_submit.sh` escalates it a bucket
(2h → 4h → 8h → 16h) on the next round automatically.

## Scale

See `inventory/coverage.txt` for the current numbers. As built:

| | |
|---|---|
| IA items examined | 693 |
| Volumes covered | 110 (vol 1 – vol 117, 1881–1961) |
| Files to OCR | 301, 8.2 GB |
| Pages | 61,611 |
| From volume-level scans | 68 volumes / 83 files / 44,939 pp |
| Assembled from issue scans | 42 volumes / 218 files / 16,672 pp |
| Already held on `E:` | 42 files |
| Est. GPU-hours (median 14.3 pp/min) | ~72 |
| Est. GPU-hours (p10 9.2 pp/min) | ~112 |

The early run (volumes 1–47, 1881–1917) comes almost entirely from volume-level
Cornell/BHL scans of 900–1,200 pages each; the later run is assembled from
per-issue scans of 60–100 pages. That split matters for walltime bucketing —
the early volumes are the ones at risk of overrunning.

### The seven missing volumes

Confirmed absent from Archive.org across **all five** digitisation families, not
merely missed by the search:

- Cornell/BHL scanned volumes 1, 7–23, 26–28, 30–35, 37–39 (plus the 1882–87
  Colombo imprints as volumes 2–6). Volumes 24, 25, 29 and 36 were never
  scanned there.
- The Tamil Digital Library covers volumes 1–3, 10–11, 15–22, 26–28, 30, 33–34,
  37, 39, 76–77 — none of the gaps.
- The per-issue run does not reach back before volume 48.

Known alternative holdings, none of them machine-harvestable from here
(HathiTrust and BHL both return HTTP 403 to automated requests, which I did not
work around):

- **South Asia Open Archives** (CRL, open access via JSTOR) —
  `jstor.org/stable/saoa.crl.34601980`. Best candidate for the pre-1913 gaps.
- **Sri Lanka Journals Online** — `ta.sljol.info`, the journal's current home.
- **HathiTrust** — catalog record `009422773`.
- **University of Hawai'i at Mānoa** holds a run in eVols.

| Volume | Falls between |

| Volume | Falls between |
|---|---|
| 24, 25 | vol 23 and vol 26 (c. 1904–1906) |
| 29 | vol 28 and vol 30 (c. 1907–1908) |
| 36 | vol 35 and vol 37 (c. 1911) |
| 102 | vol 101 (1945) and vol 103 (1947) |
| 109 | vol 108 (1952) and vol 110 (1955) |
| 111 | vol 110 (1955) and vol 112 (1956) |

### Open question: the supplements

Seven items are *The Supplement to the Tropical Agriculturist* rather than the
journal proper — six of them issues 1–6 of volume 11, one attached to volume 39,
all from the Tamil Digital Library. They are **currently not selected**, because
volume 11 has a Cornell volume-level scan that outranks them.

Whether that is right depends on something I could not establish from the
metadata: if the supplements were bound into the annual volume, the Cornell scan
already contains them and selecting them would duplicate pages; if they
circulated separately, the pipeline is silently dropping content. They are small
and only touch two volumes, so adding them is cheap either way — worth one look
at the Cornell volume 11 scan to settle it.

## Second copy: Google Document AI output

The external SSD holds a 2025 pass over **44 volumes** of this journal through
Google Cloud Document AI: **3,670 response shards, 82.4 GB**, covering roughly
volumes 1–55 (the colonial run, ~36,000 pages). Ten pages per shard; the page
number in each shard is already global, so no ordering has to be inferred.

Measured composition of a shard (volume 13, mid-volume):

| | |
|---|---|
| base64 JPEG page images | **68–83% of every file** |
| text | 0.1% |
| layout (blocks/paragraphs/lines/tokens) | the remainder |
| per page | 7,264 chars, 1,494 tokens, 159 lines, 7–24 blocks |
| token confidence | median 0.977, mean 0.938, 3.5% below 0.70 |
| embedded image | ~1,700 × 2,400 px (~150–180 dpi) |

**The images are the bulk and we do not need them** — the source PDFs are better
copies at higher resolution. Stripping them collapses 82.4 GB to roughly:

| granularity | per page | whole set |
|---|---|---|
| `--granularity none` (text only) | 5 KB | ~0.2 GB |
| `--granularity line` (default) | 15 KB | ~0.5 GB |
| `--granularity token` | 65 KB | ~2.3 GB |

### What is actually worth having

The OCR text itself is *not* the prize. It is legibly degraded — from one real
passage: `"he pos-s s308: he's a spler did example"` for "he possesses: he's a
splendid example", and `"Iv'e sen bim oboked with gobur and watty"`. Visible
word error looks like 5–10%, well worse than the 0.977 median confidence
suggests, so treat that confidence as optimistic. Chandra should beat this
comfortably, which is the point of re-OCR'ing from the originals.

What Document AI has and **Chandra does not produce at all** is geometry: a
bounding box and a confidence for every token, line, paragraph and block.

The concrete payoff is a **page index**, and it fixes a known defect in the
Chandra output. Chandra emits continuous Markdown with no page breaks — the
`sessional_papers` corpus had to recover page numbers from image anchors plus
token-count interpolation, accurate only to within a few pages, which makes
precise citation impossible. Every page of this journal carries a running head
that Document AI captures as positioned lines:

```
468 | THE TROPICAL AGRICULTURIST. | [JAN. 1, 1894.
```

Taking every line in the top 7.5% of the page and sorting left-to-right yields
the **issue date and the printed folio on every body page** (10/10 in the
sample; a topmost-line heuristic finds only 1 in 10, because the head alternates
sides). That gives an exact scan-page → printed-page → issue-date mapping for
~36,000 pages: enough to date and cite any passage in the 1881–1920 run to the
day.

Folios carry OCR noise, repaired by modal offset (`folio − scan_page` is locally
constant) rather than from neighbours — in the sample, scan pages 504 and 505
were *adjacent* errors, a misread `476` and a missing folio, which is exactly
the case a neighbour-based repair cannot fix. Both were recovered.

```bash
python3 10_extract_docai.py --src /mnt/e/data --out docai/   # strip images
python3 11_page_index.py    --src docai/ --out page_index.csv
```

Other uses worth noting, not built:

- **An OCR benchmark, for the working paper — deferred, but set up by accident.**
  All 44 of these volumes are also in this Chandra run, so once it finishes
  there will be Chandra and Google Document AI output over the *same scans*,
  page-aligned via `11_page_index.py`. That is the awkward part of an OCR
  comparison already done: same images, same pages, no alignment guesswork. The
  Google confidence scores give a per-token difficulty signal to stratify by,
  and the degraded passages quoted above are ready-made hard cases. Adding
  Tesseract (there is a baseline script in `~/chandra`) and olmOCR would make it
  a four-way comparison on a real historical corpus rather than a synthetic
  bench.
- **Confidence-based triage**: flag pages where Document AI confidence is low
  *and* Chandra output is short — likely genuine OCR failure rather than a
  sparse page.
- **Word-level coordinates for Chandra text**: attach Document AI token boxes to
  Chandra's output for region highlighting and provenance in a Graph-RAG
  interface.

This is **not** an input to the OCR pipeline. The 2025 attempt to parse it into
`E:\data\tropical_agriculturist_full_corpus.db` and
`~/Dropbox/2025/tropical_agriculturist_corpus.sqlite` did not go well; those
derivatives are not used here and this run starts from the original scans.

`E:` is not mounted in WSL — only `C:` is — so scripts 10 and 11 cannot run
until it is:

```bash
sudo mkdir -p /mnt/e && sudo mount -t drvfs E: /mnt/e
```

Until then it is readable only through PowerShell, which runs in
ConstrainedLanguage mode here (cmdlets work, .NET method calls do not).

## Layout

```
01_enumerate.py     IA search + per-item metadata (cached, resumable)
02_inventory.py     reconcile duplicates -> one source per volume
03_download.py      fetch the chosen PDFs (login node)
04_manifest.py      page counts -> walltime buckets
05_submit.sh        bucketed SLURM arrays, MIG slices, attempt escalation
06_status.sh        progress: done / in queue / needs retry, plus observed rate
run_volume.slurm    per-volume Chandra 2 + vLLM runner
10_extract_docai.py Google Document AI shards -> per-page text + layout JSONL
11_page_index.py    running heads -> issue date + printed folio per page
ta_common.py        volume-resolution rules and source ranking
inventory/          ia_items_raw.json, ia_meta.jsonl, ta_items.csv,
                    ta_manifest.csv, coverage.txt
```
