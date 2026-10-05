# Tropical Agriculturist — articles

*The Tropical Agriculturist* (Colombo, 1881–1945), OCR'd by Chandra 2 (`../output_v6`), split into
articles. Every article is linked to the page images it was read from.

## The main file: `articles.jsonl`

One JSON record per article (55,573 records; 54,259 from the canonical copy of their issue):

| field | meaning |
|---|---|
| `id` | `<doc>#<issue>#<n>` — stable within a build |
| `volume`, `issue` | volume number; issue as `YYYY-MM` (quarterlies `YYYY-MM/MM`; `YYYY-MM/MM` for a bound half-volume whose issues could not be separated) |
| `part` | `main` (the journal) or `supplement` (the *Supplement to the T.A.*, which carried the *Agricultural Magazine* and *Literary Register*) |
| `section` | the department heading it falls under (e.g. `FIBRES.`, `ORIGINAL ARTICLES`), if any |
| `title`, `byline` | as printed; `(untitled)` where no title line was found |
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
5. `assemble.py` → `articles.jsonl`.

## How good it is

Measured against printed contents tables (174 issues, 1928–45, 2,503 articles — `gold_contents.tsv`):
the article's title is found as an article start for 83.6% (89.1% is the ceiling: the rest of the
titles are not in the OCR text at all), on the right page for 78.9% (+3.4% on pages with no readable
folio); 1.11 articles produced per printed contents entry. Against the volume subject indexes
(1881–1927, `gold_index.tsv`): 87.3% of index entries that are printed as headings are article
starts. A plain "every `##`/`###` is an article" rule scores 73.6% / 65.8% / 3.25 and 40.2%.
99.64% of the words on the issues' pages are inside an article (the rest: running heads, stubs <40
words). Independent check: Tesseract on the IA images of random articles' first and last pages
(`verify_articles.py`, reports in `verify/`).

Known limits: ~10% of printed titles were never captured by the OCR (the article then runs on
from the previous one); signature lines occasionally become 2-word articles; Produce Sales Lists,
tea brokers' reports, advertisements and indexes are deliberately not articles (`part` in
`page_issue.tsv`); vols 24, 25, 29, 36, 46, 47 are not in the corpus.
