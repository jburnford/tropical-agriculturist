# NER review 2 — frequency-ranked entities, head to tail (2026-10-05)

Two independent Opus 5.5 reviewers over the corpus-wide rankings (`ranked/<TYPE>.tsv`): the top 200 keys
of every type classified one by one (`R2_A_head_classified.tsv`, `R2_B_head_classified.tsv`, 2,000 rows),
100 mid-frequency keys and 400 random singletons per type sampled, every proposed rule run on the full
lists with the real merge/removal counts. Details: `R2_A_findings.md` (PERSON, ORG, ESTATE, PUBLICATION,
EVENT), `R2_B_findings.md` (PLACE, TAXON, COMMODITY, PRODUCT, GROUP).

## Shape of the lists

| type | mentions | distinct keys | head: real / variant / generic / wrong type (of 200) | singletons that are real |
|---|---|---|---|---|
| PLACE | 374,553 | 41,772 | 193 / 7 / 0 / 0 | 81% |
| TAXON | 164,859 | 42,990 | 150 / 40 / 3 / 7 | 81% |
| PERSON | 150,754 | 59,371 | ~125 named / 39 variants / 10 titles | 80% |
| COMMODITY | 134,358 | 11,021 | 165 / 29 / 6 / 0 | 79% |
| ORG | 88,690 | 32,564 | — / 33 / — / 2 | 70% |
| PUBLICATION | 59,706 | 15,325 | — / 39 / — / — | 75% |
| ESTATE | 31,273 | 12,984 | — / 16 / — / 10 (gardens, farms) | ~47% |
| GROUP | 23,623 | 4,177 | 92 / 39 / 18 / 51 | ~47% |
| PRODUCT | 20,559 | 9,949 | 39 / 8 / 136 / 17 | 39% |
| EVENT | 6,189 | 3,530 | — / 52 / — / 49 (laws, cases, diseases, ships) | ~47% |

No OCR garbage in any of the 2,000 head keys. The tails are mostly genuine rare entities for the six
big types; the junk is patterned (titles, lists, adjectives, generic chemicals, laws), not rare.
**Both reviewers: do not cut by frequency.** Use evidence instead: a gazetteer/Wikidata/GBIF link
makes a node at any frequency; unlinked keys need 2+ articles (PERSON, ORG, ESTATE, PUBLICATION) or
3 mentions in 2 articles (COMMODITY, GROUP); the rest stays in the mention table.

## The real head problem: one entity under many keys
- Trimen, Drieberg, Willis each sit under 15+ PERSON keys; the Ceylon Tea Plantations Co. under 21+ ORG
  keys; Gardeners' Chronicle under 10+ PUBLICATION keys; the Chicago 1893 exhibition under 13 EVENT keys;
  coconut / coconut palm / Cocos nucifera as three TAXON keys (28 such clusters in the TAXON head).
- Variants hold 7–21% of head mentions depending on type.
- 32% of PERSON mentions are surname-only keys (12,363 keys) — resolvable only by in-article coreference,
  never by string merging ("captain brown" ≠ "dr. brown").

## Type boundaries that leak
- TAXON ∩ COMMODITY: 1,967 shared keys carrying 73% of COMMODITY and 28% of TAXON mentions (tea, coffee…).
  This is inherent to an agricultural journal: treat it as one entity with two facets, not an error.
- COMMODITY ∩ PRODUCT: 1,227 keys, mostly fertilisers. 831 "origin + commodity" composites ("CASTOR OIL,
  Calcutta") should split into commodity + place.
- 755 PLACE keys are elsewhere ESTATE (rainfall stations named after estates); botanic gardens landed
  in ESTATE because the prompt said "estates and gardens".
- Animal diseases typed TAXON: 534 keys (2.3% of TAXON). Ships: 913 PRODUCT keys. Laws/cases: 575 EVENT
  keys. All three want their own type (DISEASE, SHIP, LAW) rather than deletion.
- GROUP: 22% of mentions are adjectives before goods ("German quinine"); occupations (359 keys) and
  person/firm lists (362) are not groups.

## Gazetteer reach (what linking can expect)
- PLACE: col_matching places match 152/200 head keys (88% of head mentions) but only 6/50 Ceylon
  localities → Ceylon places need Wikidata/GeoNames directly. Fuzzy matching needs a guard
  (malabar→calabar, austria→australia).
- ESTATE: 155/200 head keys match `estates_index.tsv` after stripping "estate" (~165 fuzzy); corpus-wide
  1,360 linked keys carry 43% of estate mentions.
- PERSON: ~45 of 125 named head persons are in the planters index (19) or Colonial Office List (~30);
  the Department of Agriculture scientists who dominate (Drieberg, Green, Macmillan, Bamber, Shand) are
  in neither — they need Wikidata or a hand-built authority.
- TAXON: period names (Gliricidia maculata, Leucaena glauca) → GBIF synonymy; ~1% of rare binomials
  have the wrong genus and GBIF will accept them, so check genus against the text.

## Rules tested on the full lists (keys merged)
| rule | keys merged / removed | share of mentions touched |
|---|---|---|
| ESTATE: strip the/estate/plantation/group/division, squash spaces & hyphens | 2,092 (16%) | 55% (needs a PLACE filter: also merges "haputale") |
| ORG: the/Messrs. off, and→&, Company/Coy→co., drop Ltd/Limited, punctuation | 2,918 (9%) | — |
| PUBLICATION: punctuation + 25-entry abbreviation table | 948 + ~1,000 mentions | 53% |
| PERSON: honorific to its own field (strip only if initials/given name remain), space initials, expand Wm./Thos./Geo. | 1,925 (3%) | 16% |
| TAXON common-name→binomial crosswalk (built from the data) | 615 keys | 10.9% |
| plural/hyphen normalisation (TAXON, COMMODITY, PRODUCT, GROUP) | — | 3–13% |
| PRODUCT filter: keep named/branded/patented; ships → SHIP; generic chemicals → COMMODITY | keeps 5,164 keys (38% of mentions) | precision 42/42 head, 42/45 middle, ~75% tail |
| GROUP filter G1–G6 + alias map (Mahomedan/Mohammedan/Muhammadan → Muslim) | 68% of mentions survive, keys −12% more | — |
| EVENT: alias table of ~40 events keyed by city+year (string rules fail: Paris 1878/1889/1900) | — | — |

## What this means for the pipeline
1. Normalisation pass first (the rules above, as code with the counts as tests), then rerouting
   (DISEASE, SHIP, LAW, OCCUPATION, adjective-GROUP drop, origin split), then thresholds by evidence.
2. Linking: estates → `estates_index` (+ post towns if pulled); places → col_matching then Wikidata;
   taxa → GBIF with a genus-in-text check; persons → planters/Col. Office List with initials, plus a
   hand authority for the Department scientists; publications via the abbreviation table.
3. Surname-only persons (32% of mentions) are an in-article coreference task, deferred.
