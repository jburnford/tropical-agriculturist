# Entity extraction — working notes (started 2026-10-05)

`kwic.py TERM...` — keyword-in-context and collocation summary over the canonical article text
(reads `../articles/by_year/`). `kwic_round1.txt`: coffee, tea, Colombo, Accra, acre.
`kwic_round2.txt`: Mr., Messrs., estate, Ltd., Esq. — the surface forms names take in the journal.

Gazetteer sources (since used for person grounding: see `persons/README.md`):
- `~/col_matching` (Imperial Careers KG, CC0): 1,116 Colonial Office List officials with Ceylon postings
  (7,107 career events; 481 in land/agriculture-related posts), 205 Ceylon places grounded to Wikidata.
- historyofceylontea.com (Dilmah): planters registry (10,000+ planters, 1871–1930), estates registry
  (4,000+ estates with district; JSON endpoint `/tea-estates/estates-registry?reqType=json&`), family
  planters list. Copyright Dilmah Ceylon Tea Company PLC; robots.txt only blocks /search.html.
