# Person profiles (stages 1–3 of person grounding)

Turns the 150,754 PERSON mentions in `../mentions.jsonl` into **profiles**: one row per person, the unit
that gets grounded in stage 4 (Wikidata via the MCP vector search → Colonial Office List KG → planters
registry ids → minted local ids). Deterministic CPU code; `python3 build_profiles.py` rebuilds everything in
about a minute.

- `parse.py`: stage 1. A mention becomes honorific | office | given names/initials | surname | suffix | generation | gender,
  and a kind (`person`, `title`, `list`, `initials`, `empty`). `python3 parse.py` runs the test cases.
- `build_profiles.py`: stages 2–3 (see its docstring for the resolution methods).
- `out/stats.md`: counts. `out/profiles_head.tsv`: the 1,869 profiles with ≥10 mentions (spreadsheet-friendly).
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
George Watt), "Alphonso Spring Rice Riley". Norm-supplied names are accepted only when the article prints
them (2,216 verified, 840 rejected). Rejected guesses are kept per profile as `llm_guesses`, as a hint for
stage 4 and never as evidence. Surface texts themselves are reliable: 96.8% occur verbatim in the article.

## Known limits (v1)

- French "M." (Monsieur) parses as an initial ("M. Joulie"). It is right for M. Treub, wrong for Joulie.
- OCR spelling variants (Drieberg/Driberg) are flagged `possible_variant_of`, not merged.
- Different names for the same man (Sir Arthur Gordon = Lord Stanmore) are left to stage 4.
- Lists ("Messrs. Robb and H. Brown", 1,494 mentions) are not yet split into individuals.
- The corpus-level links were spot-checked by eye: about 27 of 30 right in each of the `corpus_dominant`
  and `corpus_unique` samples. Typical misses: "Rowan, wine producer" → Ellis Rowan the artist. The gold
  set will measure this properly.
- pids are build-local (rank order). Persistent ids are minted in stage 4.
