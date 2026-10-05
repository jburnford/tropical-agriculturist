# NER quality review — synthesis (2026-10-05)

Two independent Opus 5.5 reviewers, 48 sampled articles each (A: 1881–1913, B: 1914–1945), 96 articles,
3,086 mentions, read against the OCR text. Per-article scores in `A_scores.tsv` / `B_scores.tsv`; full
findings with quoted examples in `A_findings.md` / `B_findings.md`. Single-reviewer judgements; recall is an
upper bound because repeats across chunks count as correct and long articles were checked less exhaustively.

| | A 1881–1913 | B 1914–1945 | both |
|---|---|---|---|
| articles / mentions | 48 / 1,685 | 48 / 1,401 | 96 / 3,086 |
| wrong (not an entity, or not in text) | 2.8% | 3.2% | 3.0% |
| mistyped | 0.8% | 4.6% | 2.6% |
| bad normalised name | 1.5% | 1.3% | 1.4% |
| precision, type must be right | 96.4% | 92.1% | 94.5% |
| precision, type ignored | 97.2% | 96.8% | 97.0% |
| recall (approx.) | 93.6% (97%+ without one bibliography) | 96.7% | 95.0% |
| articles with no error at all | 21 | 8 | 29 |

Neither reviewer found an invented entity: every wrong mention was something present in the text.

## Where the errors are (both eras agree)
1. **PERSON = job title or pen-name without a name.** "Director of Agriculture", "H.E. the Governor",
   "Agricultural Chemist", "Outstation", "S.W.A.N." — 18 of the 24 PERSON errors across both samples.
   Also author lists kept as one person ("McCance, Widdowson, and Shackleton").
2. **GROUP and PRODUCT are the weak types (about half wrong).** GROUP catches nationality adjectives
   ("Indian teas", "British firms"); PRODUCT catches generic chemicals, foods and rubber grades
   ("magnesium chloride", "salt soap", "Shoyu").
3. **Diseases typed TAXON** (B only): all 23 TAXON type errors are animal diseases from the Animal
   Disease Returns; one return dropped them entirely — inconsistent.
4. **Honorifics kept inconsistently in `norm`** ("Dr." kept 11 / stripped 6; "Mr." kept 5 / stripped 40),
   so "Dr. Trimen" and "Trimen" would index apart.
5. **Duplicates within an article:** 14% of mentions repeat an entity (90% of that in five long
   multi-chunk articles).
6. **Recall drops in long chunks and list-like text:** the coffee bibliography (A 020: 150 entries,
   47 captured), reference lists (B: 10 of 16 PUBLICATION misses), names in the last third of a
   2,500-word chunk.
7. **Scientific names:** authorities stripped reliably and many OCR errors repaired (Collectrotrichum →
   Colletotrichum), but 8–10 made worse or wrong: "arnatto" → *Lawsonia inermis* (henna; should be
   *Bixa orellana*), wood apple → *Aegle marmelos* (bael), "Crotalaria mjujusi".
8. **No type for ships** (3 mistyped); bylines, degrees and affiliations handled well (14/14 in B).

## Recommendations, in order
1. Post-processing (no GPU): drop PERSON rows with no personal name (title-only, pen-name pattern);
   split author lists; strip honorifics into a separate `honorific` field; merge duplicates within an
   article; nationality-adjective filter on GROUP; drop PRODUCT rows that are generic chemicals/foods.
   Patterns are in §4 of both findings files.
2. Linking stage should verify every supplied Latin name against a taxonomic list (GBIF/POWO) and check
   that the binomial — or the common name it replaces — is actually in the text.
3. If re-running extraction (another ~14 H100-hours): prose chunk 2,500 → ~1,200 words; treat list-like
   text (bibliographies, reference lists, returns) with the 700-word table chunk; add DISEASE and SHIP
   types or an explicit exclusion; tighten PERSON/GROUP/PRODUCT definitions as above.

Articles for a human to look at — best: A 006, 017, 008, 014, 035; B 047, 009, 023, 031, 013.
Worst: A 004, 020, 040, 039, 005; B 022, 028, 042, 030, 046, 036, 018.
