# Entity mentions — full corpus (Trillium array 1032618, 2026-10-04/05, 13.7 H100-hours)

`part_NN.jsonl.gz` = the 22 array outputs (inputs: `../jobs/part_NN.jsonl`, canonical `kind=article`
articles ≥ 20 words, grouped by document). One line per article:
`{id, mentions: [{text, type, norm, role, chunk}], chunks, words, seconds, errors}`.
Extractor: `../extract_entities.py` (md5 809ec7b1), Qwen3.8-27B-FP8, 2,500-word chunks (700 for tables).

53,053 articles · 1,054,564 mentions (25.0 per 1,000 words) · 3 chunk errors · 561 articles with no mention.
By type: PLACE 374,553 · TAXON 164,859 · PERSON 150,754 · COMMODITY 134,358 · ORG 88,690 · PUBLICATION 59,706 ·
ESTATE 31,273 · GROUP 23,623 · PRODUCT 20,559 · EVENT 6,189. Distinct normalised names: PERSON 59,371 ·
PLACE 41,772 · TAXON 42,990 · ORG 32,564 · PUBLICATION 15,325 · ESTATE 12,984.
Merge with `../collect.py` after `gunzip` into `../out/` (→ `mentions.jsonl`, 111 MB, not in git).
These are raw model output, unlinked and unreviewed; linking to gazetteers/Wikidata is the next stage.
