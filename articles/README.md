# Tropical Agriculturist — articles

*The Tropical Agriculturist* (Colombo, 1881–1945), OCR'd by Chandra 2 (`../output_v6`), split into
articles. Every article is linked to the page images it was read from.

## The main file: `articles.jsonl`

One JSON record per article (54,764 records; 53,501 from the canonical copy of their issue):

| field | meaning |
|---|---|
| `id` | `<doc>#<issue>#<n>` — stable within a build |
| `volume`, `issue` | volume number; issue as `YYYY-MM` (quarterlies `YYYY-MM/MM`; `YYYY-MM/MM` for a bound half-volume whose issues could not be separated) |
| `part` | `main` (the journal) or `supplement` (the *Supplement to the T.A.*, which carried the *Agricultural Magazine* and *Literary Register*) |
| `section` | the department heading it falls under (e.g. `FIBRES.`, `ORIGINAL ARTICLES`), if any |
| `title`, `byline` | as printed; `(untitled)` where no title line was found |
| `kind` | `article`, or `contents` for an issue's printed contents table (1928–45; kept as one record so its department headings do not become sections of the body) |
| `canonical` | `true` for the copy to use; the corpus holds 64 issues twice (see below) |
| `split_from` | set when a run of text crossed from main journal into Supplement and was split |
| `words` | word count of `text` |
| `pages` | every page the article is on: scan page index, printed folio, `image_url` and `viewer_url` (Internet Archive) |
| `segments` | `[scan_page, char_start, char_end]` into the document's `output_v6` `.md` — exact provenance for every character of `text` |
| `text` | the article text (Chandra markdown/HTML), running heads removed |

Use `canonical == true` for counting or reading; the non-canonical records are the second copy.

## How it was built (scripts in this directory)

1. `pages.py` → `pages.tsv`: one row per scan page (63,680): text offsets, printed folio
   (read / inferred / corrected), running-head date and title, IA image links.
2. `issues.py` → `page_issue.tsv`: volume, issue and part per page, from running-head dates,
   issue mastheads, printed issue tables and the identifier; `canonical.py` → `canonical.tsv`.
3. `skeleton.py` → `skeleton.jsonl`: per issue, every line that might start an article.
4. `label_headings.py` (+ `label_headings.slurm`, Qwen3.8-27B-FP8 on a Trillium H100): labels each
   line SECTION / ARTICLE / CONT / SUB / BYLINE / OTHER. `merge_labels.py` combines runs, taking an
   issue's labels only from a run made on an identical skeleton (`skeleton_<md5>.jsonl`).
5. `merge_stubs.py` → `labels_merged.jsonl` + `stub_decisions.tsv`: a deterministic pass over the labels
   for ARTICLE lines that own no text (640 of 53,891). A signature at the foot of a letter ("W. FERGUSON.",
   "A PLANTER.", '"IGNOTUS."', the *Upcountry Planting Report*'s "PEPPERCORN.") is relabelled OTHER so it
   stays with its letter (147); a heading whose body sits under the next title on the same page
   ("BOARD OF AGRICULTURE." / "MINUTES OF THE 40TH MEETING.") makes the next line a title continuation
   (404); 89 ambiguous lines are left as they were. Every decision is in `stub_decisions.tsv`.
6. `assemble.py labels_merged.jsonl articles.jsonl`. Also detects the printed contents table that opens
   each 1928–45 issue (rows ending in non-decreasing page numbers with dotted leaders or "By author", on
   the issue's first pages): its fragments become one `kind: contents` record (128), and the department
   headings printed inside it no longer carry over as the `section` of the articles that follow (302
   corrected). The build before steps 5–6 is kept as `articles_v1.jsonl` (same words to the last one:
   42,259,237 canonical; stubs under 20 words 879 → 341).
7. `split_by_year.py` → `by_year/articles_YYYY.jsonl.gz` + `index.json` (what the repo and the viewer hold).

## How good it is

Measured against printed contents tables (174 issues, 1928–45, 2,503 articles — `gold_contents.tsv`,
`eval_contents.py`): the article's title is found as an article start for 84.3% (89.1% is the ceiling:
the rest of the titles are not in the OCR text at all), on the right page for 79.8% (+3.5% on pages
with no readable folio); 1.10 articles produced per printed contents entry. Most of the remaining gap
is one case: the contents say "Editorial" where the editorial is printed under its own subtitle, which
the parser (correctly) uses as the title under section `EDITORIAL`; counting those, 87.7% of contents
entries are found. Against the volume subject indexes (1881–1927, `gold_index.tsv`, `eval_index.py`):
88.4% of index entries that are printed as headings are article starts. A plain "every `##`/`###` is an
article" rule scores 73.6% / 65.8% / 3.25 and 40.2% on the same measures (before the two-line-title
accounting). Reports: `eval_*_final.txt`; the pre-merge build's in `eval_*_v1.txt`.
99.64% of the words on the issues' pages are inside an article (the rest: running heads, stubs <40
words). Independent check: Tesseract on the IA images of random articles' first and last pages
(`verify_articles.py`, reports in `verify/`).

Known limits: `section` is the last department heading seen, so where the body's department
heading was read as an article title (common in 1928–45: "EDITORIAL" becomes the editorial's title) the
following articles inherit the wrong or an empty section; ~10% of printed titles were never captured by
the OCR (the article then runs on from the previous one); ~90 ambiguous no-body heading lines (a pseudonym or a department heading —
"KENT.", "ANIMAL HUSBANDRY.") remain as 1-line articles; weakest heading classes are plain caps lines
and run-in titles (index recall ~80% vs 96% for `##`); Produce Sales Lists,
tea brokers' reports, advertisements and indexes are deliberately not articles (`part` in
`page_issue.tsv`); vols 24, 25, 29, 36, 46, 47 are not in the corpus.
