# NER review, sample A: 1881-1913 bound volumes

Scope: all 48 sample articles scored (53,194 words, 1,685 mentions). Per-article scores and notes are in
`A_scores.tsv`. I judged against the SYSTEM prompt in `extract_entities.py`. Only one person reviewed this,
so the "missed" counts are my judgement, and I was strict about them (named people, firms, estates, places,
publications, species and events only, not generic words). Where an article runs to several chunks
(2,500 words for prose, 700 for tables), repeats of an entity across chunks are allowed and were not
counted as errors.

## 1. Headline numbers

| measure | all 48 | excluding 020 (bibliography) |
|---|---|---|
| words | 53,194 | 51,132 |
| mentions | 1,685 | 1,375 |
| wrong (not an entity / not in text) | 47 (2.8%) | 41 (3.0%) |
| mistyped | 14 (0.8%) | 14 (1.0%) |
| bad norm | 25 (1.5%) | 23 (1.7%) |
| missed (strict) | 112 | 22 |
| articles with no error of any kind | 21 / 48 | |

Precision means (mentions − wrong − mistyped) / mentions. Recall means correct mentions / (correct mentions + missed).
Recall is approximate and runs high, because cross-chunk repeats inflate the correct count.

| type | mentions | wrong | mistyped | precision | missed | recall (approx.) | bad norm |
|---|---|---|---|---|---|---|---|
| PLACE | 602 | 2 | 1 | 99.5% | 6 | 99% | 1 |
| PERSON | 338 | 12 | 0 | 96.4% | 2 | 99% | 12 |
| TAXON | 233 | 3 | 4 | 97.0% | 5 | 98% | 6 |
| COMMODITY | 224 | 1 | 2 | 98.7% | 1 | 99% | 3 |
| PUBLICATION | 122 | 3 | 0 | 97.5% | 92 | 56% overall; 97% without 020 | 1 |
| ORG | 93 | 3 | 2 | 94.6% | 5 | 95% | 1 |
| GROUP | 30 | 14 | 0 | **53%** | 0 | n/a | 0 |
| PRODUCT | 24 | 7 | 5 | **50%** | 0 | n/a | 0 |
| ESTATE | 15 | 1 | 0 | 93% (small n) | 0 | n/a | 1 |
| EVENT | 4 | 1 | 0 | 3/4 (tiny n) | 1 | n/a | 0 |
| total | 1,685 | 47 | 14 | 96.4% | 112 | | 25 |

What the numbers say. The five types that carry most of the index (PLACE, PERSON, TAXON, COMMODITY, ORG) are
95-99.5% precise and miss very little in ordinary prose. Two small types fail badly. GROUP and PRODUCT are each
about half wrong. PUBLICATION recall collapses in dense list text: 020, the coffee bibliography, has about 150
entries but yielded only 47 titles, and 12 of 13 titles I spot-checked were missing. The ESTATE and EVENT
counts are too small to support any estimate (this sample has only one estate report, 023).

Other counts:
- Roles: 184 of 338 PERSON roles are stock phrases ("present at demonstration", "author"). 243 of 602 PLACE roles and 91 of 224 COMMODITY roles are empty.
- Duplicates: 134 of 1,685 rows (8%) repeat a (type, norm) pair already present in the same article. Almost all are cross-chunk repeats in table articles (040: 37 of 95; 048: 21 of 124; 043: 13 of 102).

## 2. Systematic error patterns

**2a. Titles and offices typed PERSON (8 rows, the largest PERSON error).**
- 022 `Director of the Botanic Gardens at Kew`
- 017 `Conservator of Forests for Travancore`
- 039 `Director of Agriculture` and `Deputy Director of Agriculture, Southern Division`
- 040 `Chancellor` and `Russian Ambassador`

The model did correctly skip "the Governor of Para" (037).

**2b. Pseudonyms and catalogue headings typed PERSON (6 rows).**
- 004 `Outstation` (a correspondent's pen-name)
- 041 `S.W.A.N.` (a letter signature)
- 020 `Quinquina` (from 'By "Quinquina"') and `Oud-Koopman` ("an old merchant"; also extracted as a PUBLICATION)
- 020 `Quëstion` and `Spy`, which are keyword headings in the bibliography, not people

Handling is inconsistent: "X. Y. Z." (010) and "Cosmopolite" (027) were correctly left out. Initials signatures
of real correspondents (`W. T. McK.` 030, `R. G. H.` 016) were kept. I did not count those as errors, but they
will need a flag.

**2c. Nationality adjectives typed GROUP (12 of the 14 GROUP errors).**
- 007 `Indian` ("Indian expenditure")
- 017 `Javanese` ("Javanese lauraceous plants")
- 026 `Nepalese` ("Nepalese collections")
- 042 `American` ("American brooms")
- 034 `American` and `Australian`
- 043 `British` ×2, `Indian`, `Japanese`
- 040 `Indian`

Other GROUP errors: 026 `Sanskrit` (a language) and 004 `dhoby` (an occupation). When the text really is about
people, GROUP works well: `Tamil coolies`, `Canarese coolies` (011), `Brahmins` (026), `Chinese` labourers (039).

**2d. Generic goods typed PRODUCT (7 wrong, 5 mistyped).**
- 004 `aniline dyes`, `congee`, `salt soap`, `white curd soap`
- 042 `hurl` (a fibre grade)
- 043 `magnesium chloride`, `ghani` (a type of oil-mill)
- 043 foods typed PRODUCT: `Shoyu` ×2, `Soy-bean milk`, `topo`

There is also a grey zone I did not count. The prompt lists "fertilisers" under PRODUCT, so the model typed
generic substances that way (042 `Superphosphate`, `Bonedust`, `Sulphate of Ammonia`). The genuine PRODUCTs are
good: 010 `Sirocco`, `Victoria Drier`, `Desiccator`, `Rippingille`; 042 `Planet Jr.`; 006 `Ransomes' patent tree-feller`.

**2e. Ships have no type (3 of 3 mistyped).**
- 024 `Oceana` typed ORG ("113 Packages Tea ex Oceana")
- 022 P. and O. `"Victoria"` typed ORG
- 010 P. & O. `"Britannia"` typed PRODUCT

A related case: 027 `Duke of Oxford`, a named bull, typed TAXON.

**2f. Honorifics left in norms, inconsistently.** Across all PERSON rows the model was inconsistent:

| honorific | stripped | kept |
|---|---|---|
| Mr. | 40 | 5 (`Mr. Nock`, `Mr. Kellow` 014; `Mr. Carey`, `Mr. Hall`, `Mr. White` 023) |
| Dr. | 6 | 11 (`Dr. Trimen` 014 vs `Greshoff` from "Dr. Greshoff" 017) |
| Sir | 0 | 16 |

So "Dr. Trimen" and "Trimen" will split in the index. Other problems:
- One man normed three ways in one article (026): `Linnaeus` / `Carl Linnaeus` / `Linnæus`; also `Koenig` vs `John Gerard Koenig`.
- Office titles disappear: 045 `Mudaliyar A. E. Rajapaksa` became `A. E. Rajapaksa`, and the role says only "of Negombo".

**2g. Several people in one row.**
- 006 `Messrs. A., J. S., and L. H. Ransome` (three men)
- 033 `Messrs Cumming and Bugai`
- 026 `Anderson Berry` (an OCR-dropped comma between two botanists)

**2h. Norms that are wrong or invented.**
- 004 `arnatto seeds` → `Lawsonia inermis`. That is henna; annatto is *Bixa orellana*.
- 005 `ANIMI` → `Benjamin`. Gum animi is not benzoin.
- 005 `Amrad cha` → `Amra Chai` (invented).
- 008 `Arbor-vite` → `Thuja orientalis`. No binomial is printed, so the species is a guess.
- 011 `kurakkan` → `millet` (loses specificity).
- 023 `KITOOLO-MOOLA` → `Kitooloo-Moola`, a spelling that appears nowhere in the text.
- 026 `Dr. Buchanan, Hamilton` → `Hamilton Buchanan` (order reversed; he is Buchanan-Hamilton).
- 048 `W. C. Penang` → `West Coast Penang` (W.C. means West Coast of Sumatra).
- 046 `Bulletin No. 184`, not tied to its issuer.
- 040 one company normed two ways: `East India and Ceylon` / `East Indian and Ceylon`.

Binomials supplied from the model's own knowledge are usually right (013 Black Walnut → *Juglans nigra*; 047
sisal → *Agave sisalana*), but the prompt says to do this only when the text prints one.

When a binomial is printed, the norms are excellent:
- 014 `A. dealbata` → *Acacia dealbata*; `E. marginata` → *Eucalyptus marginata*
- 008 `M. Grandiflora` → *Magnolia grandiflora*
- 017 `Laurimeæ` → *Lauraceae*; `Gemelina arborea` → *Gmelina arborea*

**2i. Running heads and self-citations.**
- 028 `TROPICAL AGRICULTURIST`, extracted from the running head "TROPICAL AGRICULTURIST.[AUG. 1 1900.]"
- 016 and 015: `T. A.` from the editorial sign-off "Ed. T. A." normed to *The Tropical Agriculturist*
- 030: the journal citing itself

**2j. Places vs estates (Ceylon).** This was less of a problem than expected in this era. ESTATE was right in all
three cases where "estate" was printed or the estate names were bold section heads:
- 023: 10 estates/divisions, including `NORTH VEDEHETTE`, `GOOROOKELLE`, `MAOUSA KELLE`
- 014 `Abbotsford`
- 024 `ROTALE ESTATE`

Errors:
- 019 `Tippuk` typed PLACE. It is a Jokai tea garden ("the tea-house at Tippuk").
- 023 `Amblamana`, typed PLACE, is probably an estate or hill.
- 044 `College Farm` typed ESTATE, but it is the generic farm of Wye College.

This sample is too thin to say much about the estate/place boundary. Sale lists and estate reports from these
years need their own check.

**2k. TAXON vs COMMODITY.** Few hard errors. Mistyped:
- 001 `cinchona` and `potatoes` typed COMMODITY although the text is about plants under cultivation ("the cinchona plants do well")
- 005 `East Indian`, `Liberian` (coffee grades in a price list) and `COÇULUS INDICUS` (a drug) typed TAXON

The real problem is the rule of one type per entity per chunk. "Tea" or "coffee" means both the plant and the
good in the same paragraph, so the type is arbitrary. Common-name norms also switch case at random, even within
one article: 048 `Nutmeg` vs `myrrh`; 035 `Corn`, `Chinch bug`; 028 `Cassia` vs lower case in prose. Generic
animal classes were also extracted as TAXON (001 `birds`, 034 `worms`, `slugs`).

**2l. Roles.**
- Prose: roles are mostly useful and taken from the text (006 `Commissioner for British North Borneo`; 017 vernacular names attached to each binomial; 043 `H. M. Consul at Newchwang`).
- Table rows: roles are grade or unit strings (005 `bright & good flavour`, `per ton`).
- Some roles are invented: 023 `employee`, `manager/agent`; 014 `red gum` for *E. robusta*; 003 `variety of Hurialee grass` for "Dube", which is the vernacular synonym.
- 020 `E. & W. Ludies` has the role `witnesses`, which is also invented.

**2m. Recall failures are concentrated, not spread out.**
1. Dense lists inside one large chunk. 020 is 2,062 words in one chunk and produced 310 rows. People and places came out nearly complete, but publications did not (47 of about 150).
2. The end of long single chunks. In 006 (2,022 words, one chunk) all 48 attendees in the first paragraph were caught, but three names that appear only in the last third were missed (`Alan Ransome`, `E. A. Cooper`, `Brinsmead`).
3. Source lines and footnotes:
   - 048 "(From Lewis & Peat's Latest Monthly Prices Current.)" gave nothing, although the same line in 005 was extracted.
   - 026: the footnote naming the British Association meeting at Dover was missed.
4. Vernacular names as the subject of an article: 017 `Pishir-puttai`.

## 3. What the OCR did to the extraction

- **Corrected in the norm (good):**
  - 013 `China peake` → Chesapeake
  - 036 `Puttalm` → Puttalam
  - 006 `Dr. Trimens` → Trimen
  - 040 `Yatty nota` → Yatiyantota
  - 011 `Canary coolies` → Canarese
  - 028 `Rhajpore` → Rajpore
  - 017 `Laurimeæ` → Lauraceae
  - 020 Latin imprint places (`Lipsiae` → Leipzig, `Wratislaviae` → Wrocław)
  - 029: "Mr. F. / Street" split across a paragraph break was rejoined
- **OCR error kept in the norm:**
  - 023 `W. Lumssen Strachan`, although the heading in the same article prints LUMSDEN
  - 017 `Hiptage madabloba`
  - 020 `Henry Alford Alford Nicholls`
  - 034 `Culicoflowers`
  - 043 `Kherq`
  - 014: a markdown asterisk inside a name (`syncarpia*s`)
- **Entity invented from an OCR error:** 020 `E. & W. Ludies` ("E. & W. Indies") became an ORG with an invented role.
- **Fused names:** 026 `Anderson Berry`, from a dropped comma.
- **Tables:**
  - The OCR scattered most price columns into unaligned lists (028), but entity recall was not hurt.
  - Table chunks of 700 words work. Their cost is many cross-chunk repeats, up to 39% of rows in 040.
- **Other OCR artefacts:**
  - 003: looping OCR ("I had a small quantity of grass..." repeated). Nothing was invented from it.
  - 044: portrait descriptions written by the OCR model were correctly ignored.
  - 048: a photo caption that bled in from another page was extracted (harmless).
  - 028: a running head was extracted (see 2i).

## 4. Recommendations, in priority order

1. **Remove title-only and pseudonymous PERSON rows (2a, 2b; 14 rows, 4% of PERSON).**
   - Prompt: add "A PERSON must contain a personal name. Offices alone ('the Director of Agriculture', 'the Chancellor', 'the Conservator of Forests') are not entities; put the office in the role of the named holder if one is given. Signatures and pen-names (in quotes, or initials that spell a word, e.g. 'S.W.A.N.', 'Outstation', 'X. Y. Z.') are not PERSON."
   - Post-filter: drop PERSON rows whose norm matches `^(the\s+)?(Deputy\s+)?(Director|Conservator|Chancellor|Governor|Ambassador|Secretary|Superintendent|President|Editor|Collector|Agent|Commissioner|Resident)\b` and contains no token matching `\b[A-Z]\.|\b[A-Z][a-z]+\b` after the office phrase.
   - Flag rows matching `^([A-Z]\.){3,}$` when the letters spell a dictionary word.
2. **Normalise honorifics in post-processing, not in the model (2f; 16 inconsistent rows, plus every "Sir").**
   - Strip `^(the\s+)?(Mr|Mrs|Messrs|Dr|Hon|Rev|Col|Colonel|Major|Capt|Captain|Professor|Prof|Mudaliyar|Lord|Sir|Bishop)\.?\s+` from the norm and keep it in a separate `title` field, so the Mudaliyar title survives.
   - Then split rows on `,? and ` / `, ` when the text starts with "Messrs." and the parts are initials plus surname (2g).
3. **Fix GROUP (53% precise).**
   - Prompt: "GROUP only when the words refer to people ('the Javanese', 'Tamil coolies'); never for an adjective modifying a thing ('Indian teas', 'American brooms', 'British firms')."
   - Post-filter: drop GROUP rows whose text is a bare nationality adjective (`^(Indian|American|British|Japanese|Javanese|Nepalese|Australian|Chinese|English|European|Dutch|Portuguese)$`) when the next word in the chunk is not one of coolies, labourers, people, natives, planters, men, women, race, settlers, or a plural noun of people.
4. **Tighten PRODUCT (50% precise).**
   - Prompt: "PRODUCT only for goods with a proper name (a brand, a patent or maker's name, a named machine). Generic substances, chemicals, fertilisers, soaps and foods are not PRODUCT (foods and traded substances are COMMODITY)."
   - Change the example list from "fertilisers" to "named fertiliser brands".
5. **Shorten chunks for list-like text and for prose generally (2m).**
   - Extend the `rows > 20` trigger in `chunks()` to bibliography and list text. For example, more than 30 lines matching `^\*?[A-ZÀ-Ž][\w'-]+,\s` or `^\d+\.\s`, or more than 40 newline-started lines per 1,000 words, should use TABLE_CHUNK_WORDS.
   - Reduce CHUNK_WORDS from 2,500 to about 1,200: the 006 misses all come late in a 2,000-word chunk.
   - Re-run 020-type articles: the bibliographies are high-value targets.
6. **Add a VESSEL type** (or ask for ships under OTHER) so that "ex Oceana" and P&O ships stop polluting ORG and PRODUCT (2e). This will matter more in sale and shipping lists than in this sample.
7. **Guard TAXON binomials (2h).**
   - Post-check: if a TAXON norm matches `^[A-Z][a-z]+ [a-z]+$` and neither word occurs in the chunk text (case-insensitive, ligatures folded), set `norm_source=model` and keep the printed common name as the primary norm.
   - Apply the same idea to COMMODITY norms that change the substance (ANIMI → Benjamin): keep the text as the norm unless it is only a case or spelling change.
8. **Strip running heads before NER.** Remove lines matching `^TROPICAL AGRICULTURIST\.?\s*\[.*\]` and drop PUBLICATION rows normed "Tropical Agriculturist" whose text is `T. A.` or which come from an editorial sign-off (2i).
9. **Dedupe and case-fold at article level after extraction.**
   - Merge rows with the same (type, folded norm) and keep a chunk list. That removes 134 rows.
   - Lower-case common-name norms for TAXON and COMMODITY (2k).
   - Index TAXON and COMMODITY rows with the same norm as one "crop/product" entity, instead of asking the model to pick one type per chunk.
10. **Expand abbreviated sources with a small lookup table:** `M. Mail` / `M Mail` → Madras Mail; `H. & C. Mail` → Home and Colonial Mail; `T. A.` → Tropical Agriculturist. In this sample these appear unexpanded in 018, 037 and 039.
11. Smaller fixes:
    - Add `Government`, `the Board`, `the Company` to an ORG stoplist (039).
    - Tell the model that a Fasli/Hijri year is not a PUBLICATION (039 `Fasli 1319`).
    - Read footnotes and source lines: "Include the source line '(From X's Y)' and footnotes."

## 5. Articles for a human to look at

Best (extraction close to what an indexer would produce):
- `006_vol006_tropicalagricult18861887colo_1886_12_144.txt`: 48 attendees and 37 timbers, honorifics stripped
- `017_vol012_tropicalagricult1218ceyl_1892_08_060.txt`: 15 binomials, OCR-corrected, vernacular names in roles
- `008_vol006_tropicalagricult18861887colo_1887_03_032.txt`: plant schedule, abbreviated binomials expanded
- `014_vol010_tropicalagricult1018ceyl_1890_12_009.txt`: acacias and eucalypts, estate correctly typed
- `035_vol031_tropicalagricul311908ceyl_1908_11_010.txt`: clean places, pests and varieties

Worst:
- `004_vol006_tropicalagricult18861887colo_1886_11_023.txt`: 6 of 11 rows wrong (pseudonym, generic PRODUCTs, occupation as GROUP), plus a hallucinated binomial
- `020_vol016_tropicalagricult1618ceyl_1896_11_002.txt`: publication recall collapses, pseudonyms and keyword headings typed PERSON, OCR-invented ORG
- `040_vol037_tropicalagricul371911ceyl_1911_07_048.txt`: titles as PERSON, "Duty"/"Budget"/"Blenders", 39% duplicate rows
- `039_vol035_tropicalagricul351910ceyl_1910_12_051.txt`: "Government", two office-only PERSONs, "Fasli 1319" as PUBLICATION
- `005_vol006_tropicalagricult18861887colo_1886_12_149.txt`: ANIMI → Benjamin, invented "Amra Chai", grades typed TAXON
