# Person profiles and grounding (version 2, 2026-10-06)

Turns the 150,754 PERSON records in `../mentions.jsonl` into **profiles**, the unit that gets grounded in
stage 4 (Wikidata via the MCP vector search → Colonial Office List KG → planters registry ids → minted local
ids). Deterministic CPU code; `python3 build_profiles.py` rebuilds the profiles in about a minute.

**What a "mention" is.** The extractor returns one representative record per distinct entity per text chunk
(~2,500 words), not every printed occurrence. Mention counts are therefore chunk-level extracted presence;
use article counts (`articles`) for prevalence. **What a profile is.** A proposed grouping of records, not a
verified historical individual: 38,577 profiles (30,514 named, 8,063 surname pools).

**Status.** Nothing here has been checked by a person yet. "model_adjudicated" means a model's decision.
The RA evaluation (`gold/`) measures the pipeline; its results are scored with `gold/score_gold.py` and do
not change the outputs until corrections are reviewed and applied in a new version.
Version 1 (as reviewed on 2026-10-06, `tropical-project-review-2026-10-06.md`) is git tag
`persons-v1-reviewed`. Version 2 fixes the two defects that review confirmed (see below); tests:
`python3 -m pytest ner/persons/tests -q`.

- `parse.py`: stage 1. A mention becomes honorific | office | given names/initials | surname | suffix | generation | gender,
  and a kind (`person`, `title`, `list`, `initials`, `empty`). Tests in `tests/test_persons.py`.
- `build_profiles.py`: stages 2–3 (see its docstring for the resolution methods).
- `out/stats.md`: counts. `out/profiles_head.tsv`: the 1,858 profiles with ≥10 records (spreadsheet-friendly).
  `out/profiles.tsv.gz` / `out/profiles.jsonl.gz`: all profiles. `out/mentions.tsv.gz`: every mention with its
  profile id and resolution method.

## Rules

- **Parse, don't string-match.** Honorifics go to their own field. Initials are spaced, and Wm./Thos./Geo.
  are expanded. von/van are dropped from the key ("Liebig" = "von Liebig"); de/da are kept ("de Silva").
  Identity titles stay in the key ("Lord Derby" ≠ "Mr. Derby").
- **Name compatibility.** "J. Shand" ⊂ "J. L. Shand" (prefix). "Kelway Bamber" ⊂ "M. Kelway Bamber"
  (subsequence, only when the shorter form has a matching full given name). "John" ≠ "James".
  Jr./Sr. never join an unmarked form. Female forms join only female forms.
- **In-article coreference.** A bare surname goes to the only compatible full name of that surname in the
  same article.
- **Corpus clusters.** Forms are grouped by surname and attached largest-first to the one compatible cluster.
  A rarer *more specific* form never extends a cluster (J. D. W. Hughes cannot swallow John Hughes). It is
  kept apart and flagged `possible_same_as`.
- **Bare surnames with no full name in the article** attach across the corpus only on positive evidence.
  `corpus_unique`: one compatible named profile active within ±15 years. `corpus_dominant`: one candidate
  with ≥5 named mentions within ±5 years and 5× the next. `corpus_honorific`: "Dr. Thwaites" goes to the only
  candidate printed with "Dr." in its full-name mentions. Otherwise the mention is `ambiguous` and left
  unassigned. Surnames with no named profile anywhere become `surname_pool` rows ("Liebig", "Pliny").
  These are candidates for adjudication, not identities.

## Finding: the extractor's `norm` invents given names

When the surface is bare ("Dr. Trimen", "Watt", "Professor Riley"), the extractor's `norm` often supplies
given names from world knowledge rather than the page: "H. F. C. Trimen", "James Watt" (here usually
George Watt), "Alphonso Spring Rice Riley". `parse.supported_given()` keeps only what the article prints next
to the surname, with word boundaries: a printed full name (or its abbreviation, "Wm.") keeps the name; a
printed initial keeps only the initial ("Mr. J. Watt" does not support "James Watt"); nothing printed → the
record is treated as bare. Version 2 counts: 2,150 printed in full, 17 initials only, 889 not printed. The
model's expansions are kept per profile as `llm_guesses`: a search hint, never evidence. Surface texts
themselves are reliable: 96.8% occur verbatim in the article.

**Correction (v1 → v2).** Version 1's check accepted a printed initial as support for a full name and had no
surname word boundary ("Smithson" matched "Smith"), so its "2,216 verified" overstated the verification.

## Identity gate (stage 4 merge, `identity.py`)

Model decisions MIXED, NONE and UNSURE never become an asserted QID; MIXED also withholds Colonial Office
List and planters ids (a valid QID does not make a mixed profile one person). Candidates are kept in
`candidate_qids` and flagged. Model decisions are keyed by the persistent id and applied only while the
profile's article set is unchanged (Jaccard ≥ 0.8); otherwise they are flagged stale. Version 1 let a
Colonial Office List QID override MIXED/UNSURE decisions (John Douglas, William Taylor, E. B. Denham).

## Known limits

- French "M." (Monsieur) parses as an initial ("M. Joulie"). It is right for M. Treub, wrong for Joulie.
- OCR spelling variants (Drieberg/Driberg) are flagged `possible_variant_of`, not merged.
- Different names for the same man (Sir Arthur Gordon = Lord Stanmore) are left to stage 4.
- Lists ("Messrs. Robb and H. Brown", 1,494 mentions) are not yet split into individuals.
- The corpus-level links were spot-checked by eye: about 27 of 30 right in each of the `corpus_dominant`
  and `corpus_unique` samples. Typical misses: "Rowan, wine producer" → Ellis Rowan the artist. The gold
  set will measure this properly.
- pids are build-local (rank order). Persistent ids (`TAP-P-…`) are minted in stage 4; the registry carries
  them across rebuilds by article overlap, which cannot by itself represent a split or merge. Record split/merge
  decisions explicitly before rebuilding after review. `same_qid_as` is a review flag, not a merge.
- Profile places/estates are co-occurrence in the same article: search clues, not residence or employment.
