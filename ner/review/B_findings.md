# NER review, sample B: The Tropical Agriculturist 1914-1945

Reviewer B, 2026-10-05. All 48 sample articles in `sample_B/` were scored; per-article rows are in `B_scores.tsv`.
Judged against the SYSTEM prompt in `extract_entities.py`.

Scope: 57,532 article words and 1,401 mentions (1,210 distinct type+norm pairs per article). Errors found:
45 wrong (not an entity, or a generic word), 65 mistyped, 18 bad norms, 47 missed entities.

How the counts were made. "Wrong" covers mentions that are not entities under the prompt: unnamed office-holders, generic
substances and words, table row labels, degree qualifiers. "Mistyped" means a real thing given the wrong type. Animal
diseases typed TAXON are counted as mistyped, because the schema has no type for them. Common crop names left out of an
article ("tea", "rubber") were not counted as missed unless I list them; the "missed" count is strict (people, firms,
estates, places, publications, named species, named events). I read long articles (over 3,000 words) fully but scanned
them for misses less exhaustively than short ones, so treat recall as an upper bound.

## 1. Precision and recall by type

Mention-level. Precision is (n - wrong - mistyped) / n, counted against the type the model assigned. In recall, "found"
means correctly typed plus mentions found under another type (for example crops filed as COMMODITY count as found for
TAXON). Missed entities are counted once each, as distinct entities.

| Type | n mentions | wrong | mistyped (out) | precision | missed | recall (entity found) |
|---|---|---|---|---|---|---|
| PERSON | 196 | 12 | 0 | 93.9% | 2 | 98.9% |
| ORG | 116 | 3 | 0 | 97.4% | 11 | 91.1% |
| PLACE | 483 | 3 | 9 | 97.5% | 4 | 99.2% |
| PUBLICATION | 49 | 1 | 0 | 98.0% | 16 | 75.0% |
| TAXON | 363 | 3 | 23 | 92.8% | 9 | 97.5% |
| COMMODITY | 91 | 8 | 16 | 73.6% | 0 | ~100% |
| PRODUCT | 47 | 7 | 13 | 57.4% | 2 | 93% |
| ESTATE | 30 | 0 | 2 | 93.3% | 0 | ~100% (9 more estates were typed PLACE) |
| GROUP | 19 | 7 | 0 | 63.2% | 2 | 86% |
| EVENT | 7 | 1 | 2 | 57% | 1 | 80% |
| **All** | **1401** | **45** | **65** | **92.1%** (96.8% ignoring type) | **47** | **96.6%** |

Where the errors come from:
- PERSON wrong (12): unnamed offices (10), e.g. "Director, Imperial Institute" and "Agricultural Chemist"; author
  lists kept as one PERSON (2).
- TAXON mistyped (23): all are animal diseases from Animal Disease Returns (articles 030, 042, 046).
- COMMODITY: 16 crops discussed agronomically, which the prompt says should be TAXON; 8 generic items (sulphur, zinc oxide, oil, beans, the "cacao" in "cacao house").
- PRODUCT: 13 traded goods that should be COMMODITY (rubber grades, syrups, flours, vinegar); 7 generic chemicals or goods
  (acetic acid, diphenylguanidine, cricket bats).
- PLACE mistyped (9): tea estates acting as rain-gauge stations in the Meteorological Reports (041, 043).
- GROUP wrong (7): table row labels in 028 ("British : U.K.", "Other Native") and the adjective "Hawaiian".
- PUBLICATION missed (16): 10 are article titles inside numbered reference lists (036, 038). The rest are footnote or
  in-text citations ("T. A. for January, 1915", the "Variability" paper, "The World's Rubber Supplies").
- ORG missed (11): mostly government departments and committees inside long articles (018 alone accounts for 4).

Bad norms by type (18): TAXON 8, PLACE 3, PUBLICATION 3, ORG 2, PERSON 1, PRODUCT 1.

Duplication. 1,401 mentions collapse to 1,210 distinct (type, norm) pairs, a 14% excess. 90% of the excess (173 of 191)
comes from five long, multi-chunk articles: 036 (139 mentions, 85 distinct), 043 (110, 67), 038 (107, 65), 012 (68, 48)
and 022 (28, 14). Surface variants make true duplication higher still: "Washington Navel" / "Washington navel orange";
"Hodgson" / "Hodgson, R. W." / "Prof. R. W. Hodgson".

The role field is empty for 170 of 1,401 mentions (12%). These are concentrated in table-heavy chunks (036: 72 empty;
023: 22) and short reprints (010: all 9 empty).

## 2. Systematic error patterns

### 2.1 Bylines and author affiliations: mostly good
Bylines were captured as PERSON in every research paper with an author (14 bylines, plus 3 authors named in footnotes).
Degrees were stripped from the norm and the affiliation line went into role:
- 008: `B. J. EATON` -> norm `B. J. Eaton`, role `Agricultural Chemist, F.M.S.` (printed "B. J. EATON, F.I.C., F.C.S.")
- 023: `W. SMALL` -> `W. Small`, role `Mycologist, Department of Agriculture, Ceylon` (five post-nominals dropped)
- 045: `K. T. Achaya`, role `Retired Sericultural Expert, Madras Government, and Sericultural Expert, Ceylon`
- 047: `Major J. W. Oldfield, C.M.G., O.B.E., M.C.` -> norm `J. W. Oldfield`; `the Director of Agriculture (Mr. L. J. de S. Seneviratne, C.C.S.)` resolved to the named person, with the office as role.
- 024: the norm was enriched from a footnote: `Dr. Steinmann` -> `Dr. A. Steinmann`; translator `H. Ludowyke`, role `Librarian, Dept. of Agriculture, Peradeniya`.

Failures:
- Degree parentheticals were turned into entities in one article but not in three others. In 033, `Cantab.` became ORG
  `University of Cambridge`, and `Poona` and `Trinidad` (from "Dip. Agric. (Poona)", "A.I.C.T.A. (Trinidad)") became
  PLACE. In 036, 038 and 040 the same strings were correctly ignored.
- Honorifics are handled inconsistently in norms. Titles were kept for `Dr. Schidrowitz`, `Mr. Williams` (008),
  `Governor Raffles` (031), `Prof. Geiger` (032) and `Sir Solomon Dias Bandaranaike` (009), but stripped from
  `Sir Wilfred de Soysa` -> `Wilfred de Soysa` (035).
- Roles for footnote authors are generic: 029 `W. L. Fielding` has role "author of discussion", although the same
  footnote names his station (Cotton Breeding Station, Barberton).
- (Not an NER error.) The segmenter's BYLINE metadata is wrong in 033 ("CHEMIST,") and 038 ("ASSISTANT HORTICULTURAL
  OFFICER"). The model worked from the text and got both right.

### 2.2 Unnamed office-holders typed PERSON (10 mentions)
- 004: `Director of Agriculture, Manila`, `Director, Imperial Institute`, `Government Agricultural Chemist`, `Director of Industries, Madras`
- 021: `Agricultural Chemist`; 031: `Economic Botanist, Peradeniya`
- 025: `Agricultural Instructor, Trincomalie`, `Vanniah` (a headman's title, "the Vanniah")
- 035: `H.E. the Governor` (norm `Governor of Ceylon`), `Hon. Minister for Agriculture and Lands`

The model is inconsistent here too. In 009 (minutes) "The Director of Agriculture (Chairman), the Botanist and
Mycologist, the Acting Entomologist" were correctly not extracted, and in 039 "the Botanist" was skipped.

### 2.3 Author lists merged into one PERSON
- 036: `McCance, Widdowson, and Shackleton` (each author is also listed separately)
- 038: `Neyman and Tokarska`
- In the same reference lists, "Surname, Initials" was correctly re-ordered: `Adriano, F. T.` -> `F. T. Adriano`; `Copeman, P. R.` -> `P. R. Copeman`.

### 2.4 Institutions: ORG, PLACE or ESTATE
No research institution was typed ESTATE. Consistent ORG: `Experiment Station, Peradeniya` / `Peradeniya Experiment
Station` (004, 009, 015, 021, 027), `Mycological Laboratory, Peradeniya` (023), `Horticultural Gardens, Peradeniya`
(045), `Tea Research Institute` (047), `Coconut Research Scheme` (035, 044), `Imperial Institute` (022). Peradeniya is
also listed separately as a PLACE, which is fine.

Problems:
- The norm for "Department of Agriculture" carries no jurisdiction. The bare `Department of Agriculture` /
  `Agricultural Department` appears in 008 (actually F.M.S.), 013 (Madras), 021, 034, 042 and 045 (Ceylon). Across the
  corpus these will merge into one false entity. Only 011 and 023 kept the jurisdiction (`... of the Federated Malay States`, `..., Ceylon`).
- The same body gets two norms in one article: 045 `Agricultural Department` and `Department of Agriculture`.
- Society and school gardens were typed ESTATE: 004 `Bandaragama Garden`, `Weragoda Garden`, `Gunnepana School Garden`.
  Parks were typed ESTATE: 032 `Royal Park`, `People's Park`.
- Experiment stations named by town were typed PLACE with role "experiment station": 033 `Paranthan`, `Minneriya`.
  The text supports this reading.
- Research-scheme estates were correctly ESTATE: 035 `Bandirippuwa Estate`, `Ratmalagara`; 048 `Dartonfield`, `Nivitigalakele`; 047 `St. Coombs Estate`.

### 2.5 The TAXON / COMMODITY / PRODUCT boundary
- Crops in field-trial reports were typed COMMODITY although the prompt says TAXON when a crop is discussed as a plant:
  - 015: section headings `Tea`, `Rubber`, `Cacao`, `Coconuts`, `Coffee`, `Paddy`, all describing plots on the station.
  - 024: `tea`, `rubber`, `coffee` as hosts of mycorrhiza.
  - 029: `maize`, `sunflower`, `groundnuts`, `sorghums` in a rotation trial.
  - 023: `tea` (from "tea seedling roots").
  - 025, 033: `paddy`.
- Traded goods were typed PRODUCT instead of COMMODITY:
  - 008: rubber grades `crepe`, `smoked sheet`, `dry block`, `virgin "slab"`. `Fine Hard Para` is PRODUCT in one chunk and COMMODITY in another.
  - 004: `arrowroot flour`, `Cassava Chips`, `Coconut Vinegar`.
  - 035: `Cane Syrup`, `Fancy Molasses`, `Coconut Toddy Vinegar`.
  - 006: `raffia fibre`.
- Generic chemicals were extracted:
  - 022: `sulphur` (x2) and `zinc oxide` (x3) as COMMODITY; `diphenylguanidine` (x2, two spellings) and `hexamethylenetetramine` as PRODUCT.
  - 008: `acetic acid` as PRODUCT.
- Fertiliser salts are inconsistent. In 002 `Sulphate of potash`, `Superphosphate`, `Basic Slag`, `Nitrate of soda` were
  all extracted as PRODUCT. In 019 the same substances (plus `kainit`) were not extracted at all; 019 got 1 mention from 781 words.
- Good cases: 005 split gums cleanly (gums as COMMODITY, source trees as TAXON). The genuine brand `Revertex` (022) and
  the machine `Gardner engine` (048) are PRODUCT.

### 2.6 Animal diseases typed TAXON (23 mentions), applied inconsistently
- 030: `Rinderpest`, `Anthrax`, `Foot-and-mouth disease`, `Rabies (Dogs)`, `Piroplasmosis`, `Haemorrhagic Septicaemia`, `Black Quarter`, `Bovine Tuberculosis`.
- 042: 9 diseases, including `Contagious Abortion` and `Contagious Mange`.
- 046: 6 diseases (`C. Mange` left unexpanded).
- 043, a return of the same kind, extracted none of its diseases (Rinderpest x5, Surra, Pleuro Pneumonia (Goats)...).
- The subject of a whole research paper, "bunchy top" disease (023), has no type and was not extracted.

### 2.7 Scientific names: authority stripping good, normalisation policy unclear
Authorities were stripped correctly: 023 `Musa paradisiaca L.`, `Pentalonia nigrinervosa Coq.`, `Rhizoctonia bataticola (Taub.) Butler`; 038 `C. sinensis, Osbeck`, `C. paradiisi, Macf.`, `C. jambhiri, Lush.`.

Abbreviated genera were expanded: 005 `P. Marsupium` -> `Pterocarpus marsupium`; 013 `C. vulgaris` -> `Citrus vulgaris`; 032 `M. elengi` -> `Mimusops elengi`.
Misses: 005 `C. strictum` was left unexpanded (Canarium); 038 `C. nobilis var. Unshiu` lost its variety.

OCR-corrupted names were repaired:
- 015 `Collectrotrichum Coffeanum` -> `Colletotrichum coffeanum`
- 015 `Indigifera arrecta` -> `Indigofera arrecta`
- 032 `Pterospermum accrifolium` -> `acerifolium`
- 038 `C. paradiisi` -> `Citrus paradisi`
- 013 `C. Bigardia` -> `Citrus bigaradia`

Names worsened or left wrong (8 bad TAXON norms):
- 015 `Crotalaria Mujussi` -> `Crotalaria mjujusi` (worse)
- 015 `Elack gram` (Black gram) left unrepaired
- 036 `Perona etepantum` (OCR of Feronia elephantum, the wood apple) -> `Aegle marmelos`, which is bael, a different fruit listed in the same table
- 036 `Psidium guava` not corrected to P. guajava
- 029 `Phaseolus vulgare` not corrected to P. vulgaris
- 032 `Jaminum Augustifolium` -> `Jasminum augustifolium` (genus fixed; epithet should be angustifolium)
- 004 `Cucumis Dudain` kept as printed
- 046 `C. Mange` left unexpanded

Modernisation was applied unevenly:
- Modernised: 024 `Thea sinensis` -> `Camellia sinensis`; 036 `Acris sapota` -> `Manilkara zapota`, `Artocarpus integrifolia` -> `A. heterophyllus`; 031 `Albizzia` -> `Albizia`.
- Period names kept: 013 `C. decumana` -> `Citrus decumana` (not C. maxima), `C. vulgaris` -> `Citrus vulgaris` (not C. aurantium).
- Binomial supplied with no binomial in the text: 028 `rubber tree` -> `Hevea brasiliensis`.

The prompt's phrase "the accepted scientific name" gets read either way.

### 2.8 Tables and returns
- Toponym tables work well. In 012 (tea districts), 017 (market rates), 025 (prize-winners) and 041 (weather stations),
  the row labels are real places or people and were extracted correctly. Province row labels were normalised: 030
  `Western` -> `Western Province`; 042 `Sabara-gamuwa` -> `Sabaragamuwa Province`.
- Category row labels became GROUP in 028: `British : U.K.`, `British : Local`, `Other European`, `Other Native`,
  `Asiatic Estate`, plus the generic `natives`. A table row label also became a composite PLACE in 012: `Bengal and Behar & Orissa`.
- Monthly tables multiply mentions. 043 bundles three Meteorological Reports, so each of the 19 principal stations is
  listed 3 times and `D. T. E. Dassanayake` 3 times.
- Estates used as rain-gauge stations were typed PLACE: 041 `Westward Ho`, `Theydon Bois`, `Kenilworth`, `Abergeldie
  Group`, `Blackwater`, `Carchilmally`; 043 `Hendon` is PLACE and `Hendon estate` is ESTATE in the same article. This
  needs world knowledge: the model typed ESTATE correctly whenever the text said "estate" (10 cases in 043).

### 2.9 Page furniture and generic words
- Running head: 027 `The Tropical Agriculturist` (from "# The Tropical Agriculturist / March 1930" after a blank-page image description) extracted as PUBLICATION.
- "the Island": 041 and 043 extracted `Island` as PLACE with norm `Ceylon`. The norm is right, but the prompt excludes generic words.
- Generic words: 015 `Hybrid` (TAXON), 037 `grass` (TAXON), 029 `beans`, 044 `oil` (COMMODITY), 018 `Grain Growers' Associations`, `Co-operative Elevator Companies` (ORG, both generic class names).
- Correctly ignored: printers' job numbers ("3-J. N. 84070 (5/39)", 035, 043, 046), "Do" rows in market tables (017), and the editor's disclaimer footnote (031).

### 2.10 Things not in the text, or inferred from context
No hallucinated entities were found in 48 articles. Inferences that go beyond the text:
- 028: `Hevea brasiliensis` (see 2.7)
- 031: `Brazil` from "their Brazilian home"
- 045: role "Employer of K. T. Achaya" for `Madras Government`, a relation the text does not state that way
- 024: the enriched norm `Dr. A. Steinmann` (correct, taken from the footnote)

### 2.11 Recall falls off in long single-chunk reprints and reference lists
- 018 (2,437 words, Canadian co-operatives): firms were captured, but 4 government bodies (Saskatchewan Grain Growers'
  Association, Dominion Department of Agriculture, Dominion Poultry Division, Ontario Department of Agriculture) and the
  countries near the end (Great Britain, United States) were missed.
- 036 and 038: of 17 reference-list items, only the two book titles became PUBLICATION. Article titles are dropped while
  the journal abbreviations are kept.
- Short-paragraph names can be missed in minutes: 009 `MR. SPEYER` (an entire agenda item), 035 `Mr. S. R. K. Menon` (an italic sub-heading).

### 2.12 Schema gaps (things historians would index that have no type)
- Diseases: rinderpest, bunchy top, bark canker.
- Legislation: 013 `Pest Act` was typed EVENT; 035 `Workmen's Compensation Ordinance, No. 19 of 1934` and `Coconut Research Ordinance` were dropped.
- Honours: 047 `Order of the British Empire` was typed EVENT.
- Seasons: 025 `Pinmari` was typed EVENT.

## 3. What the OCR did to the extraction
- OCR errors passed straight into norms. The prompt says to keep the text as printed, but it also asks for a normalised
  norm, and these were not normalised:
  - 001 `Obadan` (Ibadan, printed so in the source?)
  - 010 `Andubon Park` (Audubon)
  - 009 `C. E. G. Panditeslkera`
  - 024 `Gedch` (Gedeh)
  - 015 `Elack gram`
  - 041 `Nuwaru Eliya` (the town is spelled correctly in 043)
  - 029 `Berzcellar process` (Berczeller)
  - 018 `Charlotte Town`
- OCR errors the model repaired in the norm:
  - 009 `BANDARANAIKA` -> `Bandaranaike`
  - 038 `Cope-man` -> `Copeman`
  - 042 `Sabara-gamuwa` -> `Sabaragamuwa Province`
  - 046 `Hæmorrhagic Septi-/caemic` -> `Hemorrhagic Septicemia`
  - 038 `Subtropical Horiculture Orchard` -> `Horticulture`
  - plus the taxon repairs in 2.7
- Norms the model made worse:
  - 043 `Kurunegala` -> `Kurunegeala`
  - 015 `Crotalaria mjujusi`
  - 036 `Perona etepantum` -> wrong species
  - 038 `Calif. Citrog.` -> `California Citrogapher` (sic)
  - 036 `Jl. Agr. Res.` truncated to `Jl. Agr. R.` in the text field
- HTML tables: the cell structure helped. Row labels became clean entities (012, 017, 041), and the one-mention-per-
  entity-per-chunk rule was followed even when a disease repeats in every province block (030). The costs are table
  category labels becoming entities (028) and multiplied mentions when one segment holds several monthly tables (043).
- Text generated by the OCR model leaked into mentions. The OCR inserts image descriptions and transcribed graph
  legends. In 022 the graph legend `Commercial Antioxidant` became a PRODUCT. In 016 ("lion and unicorn", "DIEU ET MON
  DROIT") and 023 (photo description) nothing leaked. In 027 the running head after a "blank white page" description was extracted.
- Article segmentation: 043 joins an Animal Disease Return with three Meteorological Reports, and 016/021/027 include
  masthead or front matter. This affects mention counts more than accuracy.

## 4. Recommendations (prioritised, each tied to the evidence)

1. **Merge mentions within each article after extraction.** Group by (type, casefold(norm)) and keep the union of roles
   with a count. Then fold surname-only PERSONs into a full name with the same surname when that surname is unique in
   the article (Hodgson -> R. W. Hodgson; Magee -> C. J. Magee). Evidence: 191 excess mentions (14%), 90% of them in 036, 043, 038, 012 and 022 (2.8, 1).

2. **Add a DISEASE type, or tell the model diseases are excluded, and back it with a rule.** Evidence: 23 mistyped
   TAXON in 030/042/046, none extracted in 043, bunchy top dropped in 023 (2.6). Post-processing rule: retype TAXON to
   DISEASE when the norm matches
   `(?i)\b(rinderpest|anthrax|foot.?and.?mouth|rabies|piroplasmosis|septic(a?emi[ac])?|tuberculosis|mange|black ?quarter|surra|pleuro.?pneumonia|abortion|canker|bunchy.?top|die.?back|leaf.?fall|rot|blight|mildew|rust)\b`.
   While at it, decide on LAW (Pest Act, Ordinances) and HONOUR (O.B.E.), which are currently mistyped as EVENT (2.12).

3. **Restrict PERSON to mentions that contain a personal name.** Prompt addition: "A job title without a personal name
   (the Director of Agriculture, the Agricultural Chemist, H.E. the Governor) is not a PERSON. If the person is named
   nearby, put the title in role." Post-filter: drop PERSON when the norm has no initial (`\b[A-Z]\.`) and every token
   is in a title lexicon `{the, Hon., H.E., Acting, Assistant, Deputy, Government, Director, Chemist, Botanist,
   Mycologist, Entomologist, Agricultural, Instructor, Economic, Agent, Governor, Minister, Secretary, Superintendent,
   Vanniah, of, and, place-name}`. Also split or drop PERSONs whose norm contains ` and ` or two or more commas, e.g.
   `McCance, Widdowson, and Shackleton`. Evidence: 12 of 12 PERSON false positives (2.2, 2.3).

4. **Tighten COMMODITY and PRODUCT, which have the lowest precision (73.6% and 57.4%).**
   Prompt changes:
   - "PRODUCT is only for proprietary or named items: brand names, patents, named machines, named processes. Grades of a
     commodity (crepe, smoked sheet), foods (flour, syrup, vinegar) and generic chemicals (sulphur, zinc oxide, acetic
     acid, sulphate of ammonia) are COMMODITY if traded, otherwise omit them."
   - "A crop under a section heading or in a field trial is TAXON."

   Post-filter: drop PRODUCT/COMMODITY whose norm matches
   `(?i)^(sulphur|zinc oxide|acetic acid|formalin|lime|potash|nitrogen|oil|water|diphenyl-?guanidine|hexamethylenetetramine|beans?)$`.
   Make one explicit decision on fertiliser salts (002 extracted them, 019 did not).
   Evidence: 2.5; 29 mistyped and 15 wrong across the two types.

5. **Separate "repaired" from "accepted" in TAXON norms and validate against a name backbone.** Ask for two fields,
   `norm` (as printed, with case, OCR and abbreviated genus repaired, authority stripped) and an optional `accepted`.
   Check both against GBIF Backbone or POWO offline, and flag any norm with no exact match: that would have caught
   `Crotalaria mjujusi`, `Jasminum augustifolium`, `Psidium guava`, `Phaseolus vulgare`, `Cucumis Dudain`. Separately,
   check that two different printed binomials in one article are not given the same accepted name: that would have
   caught `Perona etepantum` -> `Aegle marmelos`. Evidence: 8 bad TAXON norms; modernisation applied in 024/036 but not 013 (2.7).

6. **Drop degree-qualifier parentheticals.** Rule: drop ORG/PLACE mentions whose text occurs only inside
   `(?:Dip\.\s*Agric\.|B\.\s*Sc\.|M\.\s*Sc\.|Ph\.\s*D\.|M\.A\.|D\.I\.C\.|A\.I\.C\.T\.A\.|F\.I\.C\.)\s*\(\s*(?:Cantab\.|Lond\.|Poona|Trinidad|Calif\.|Edin\.)\s*\)`.
   Evidence: 033 (3 wrong); handled correctly by chance in 036, 038 and 040 (2.1).

7. **Handle reference lists separately.** For `REFERENCES` sections (numbered lines matching
   `^\d+\.\s+(?:\d+\.\s+)?[A-Z][a-z]+, [A-Z]\.`), run a citation parser (author / title / journal / volume / year) rather
   than the NER prompt, and expand journal abbreviations from a fixed table. Evidence: 10 of 16 missed PUBLICATIONs; the
   `Jl. Agr. R.` truncation; `Citrogapher` (2.11, 3).

8. **Put the jurisdiction in norms for generic government bodies.** Prompt: "For Department of Agriculture, Agricultural
   Department, Director of Agriculture and similar, add the colony or country to the norm when the text or the source
   line gives it (e.g. 'Department of Agriculture, F.M.S.')." Evidence: 6 articles with a bare, unattributed
   `Department of Agriculture`; same body under two norms in 045 (2.4).

9. **Drop table row labels as GROUP.** Rule: drop GROUP whose text contains `:` or starts with `Other ` / `Total`, and
   drop the generic `natives` / `Asiatics` unless qualified. Evidence: 028 (6 wrong) (2.8).

10. **Lower priority:**
    - Drop PUBLICATION "The Tropical Agriculturist" when it sits on a line alone next to a month-year (027).
    - Drop `Island` (041, 043).
    - Retype PLACE to ESTATE using a Ceylon estate gazetteer for rain stations (041, 043; 9 cases).
    - Have the OCR stage tag its image descriptions (e.g. wrap them in a marker) so the NER chunker can strip them (022).

## 5. Articles for a human to look at

Best (accurate, high recall, good roles):
1. `047_..._1945_10.txt` - Tea Research Institute minutes: 22 people, offices resolved to names, post-nominals stripped.
2. `009_vol050_dli_ernet_21168_1918_04_006.txt` - Committee minutes: 31 people with native and military titles moved to role.
3. `023_vol071_..._1928_09_003.txt` - Mycology paper: byline, authorities stripped, cited authors, photo credit.
4. `031_vol086_dli_ernet_229228_1936_03_001.txt` - Byline with estate, cited articles and their authors, abbreviation expansion.
5. `013_vol054_lbg_630_5_tag_v_54_1920_02_006.txt` - Citrus paper: byline split into PERSON/ESTATE/PLACE, genus expansion, cultivars.

Worst:
1. `022_vol070_dli_ernet_229220_1928_01_006.txt` - 9 of 28 mentions are generic chemicals or a graph legend.
2. `028_vol076_dli_ernet_229225_1931_03_006.txt` - table category labels as GROUP.
3. `042_vol097_iss03_..._1941_09_016.txt` (and 030, 046) - diseases as TAXON. Compare 043, where they were omitted.
4. `036_vol093_iss06_..._1939_12_007.txt` - 139 mentions for about 85 entities, a wrong species norm (wood apple -> bael), 5 reference titles missed.
5. `018_vol060_lbg_..._1923_04.txt` - recall drop in a long reprint: 7 missed (government bodies, countries).

Runners-up: `025` (offices and a season as entities in a 136-word note) and `015` (crops as COMMODITY, two taxon norms
worsened).
