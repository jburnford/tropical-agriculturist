# Grounding gazetteer for historyofceylontea.com (authority records, not content)

Purpose (Jim, 2026-10-05): "I mostly want to be able to ground to their website, not steal their
content." These files hold only identifiers — record id, name, URL — so that people and estates found
in the Tropical Agriculturist can be linked to the site's records.

| file | rows | source |
|---|---|---|
| `estates_urls.tsv`, `estates_index.tsv` | 4,771 estate ids | Wayback CDX index of captured estate pages; name derived from the URL slug (654 ids have an empty slug → no name) |
| `planters_urls.tsv`, `planters_index.tsv` | 13,460 planter ids | same, for planter pages; slug word order varies (surname first or last), so the slug is kept raw |
| `family_planters.tsv` | planters on the site's Family Planters page | Jim's saved copy of the page (display name as printed) |

Not done: the site's own listing endpoint (`estates-registry?reqType=json&page=N`, 73 pages, 7,279
entries with post town) was not captured by the Wayback Machine; pulling it live would complete the
estate names and add post towns. `harvest.py` (full page harvest) was stopped after 32 pages on Jim's
instruction and its `raw/` output is not used or committed.
