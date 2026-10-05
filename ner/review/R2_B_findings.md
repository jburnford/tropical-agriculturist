# Round 2, reviewer B: frequency-ranked lists for PLACE, TAXON, COMMODITY, PRODUCT, GROUP

Reviewer: Opus 5.5, 2026-10-05. Source: `ranked/<TYPE>.tsv`, `ranked/<TYPE>_tail_sample.tsv`, `../mentions.jsonl`
(read-only, used for surface-form counts and cross-type overlaps). Classes: (a) real entity, right type;
(b) real but a variant of another key; (c) generic term, not an entity; (d) OCR garbage; (e) wrong type.
Head = top 200 keys; middle = 100 random keys with 3-10 mentions (seed 2026); tail = the 400 singletons in
the tail sample. Every head key is listed with its class in `R2_B_head_classified.tsv`. Scripts and
intermediate files are in the session scratchpad; the counts below come from runs on the actual TSVs.

## 1. PLACE (374,553 mentions, 41,772 keys, 70% singletons)

| slice | a | b | c | d | e | notes |
|---|---|---|---|---|---|---|
| head (200 keys, 217,651 mentions) | 193 | 7 | 0 | 0 | 0 | b = 6,265 mentions (2.9%) |
| middle (100 keys, 3-10 mentions) | 88 | 4 | 3 | 0 | 5 | |
| tail (400 singletons) | 326 (81.5%) | 21 (5.3%) | 23 (5.8%) | 0 | 30 (7.5%) | |

**Head.** This is the cleanest list of the five. Nothing generic, no OCR garbage, nothing mistyped. The LLM
has already collapsed OCR and spelling variants into the key: `calcutta` carries "Caleutta", "Culcutta";
`colombo` carries "Columbo", "Oolombo"; `henaratgoda` "Heneratgoda". Seven keys are variants of other head keys:
`america` and `united states of america` → `united states`; `britain` → `great britain`; `uva province` → `uva`;
`sabaragamuwa` → `sabaragamuwa province`; `south india` → `southern india`; `straits` → `straits settlements`.
Merging them takes 7 keys out of 200 (6,265 mentions). A softer cluster, `united kingdom` / `great britain` /
`britain`, is used interchangeably in the trade returns. Merge it only if the KG does not need to tell them apart.
Problems a linker has to handle (class a, but flagged in the TSV):
- Homonyms: `central province` (Ceylon or India), `victoria`, `manchester` (one role reads "parish in Jamaica"),
  `para` (the state, and close to "Para rubber").
- One normalisation error: `matara` has absorbed 12 "MATALE"/"Mátalé" surfaces.
- Metonyms: `mincing lane` (the market), `kew` and `peradeniya` (the Gardens).

Geographical make-up of the head:

| bucket | keys | mentions | share |
|---|---|---|---|
| Ceylon itself | 1 | 24,409 | 11% |
| Ceylon localities (provinces, districts, towns, met stations) | 43 | 39,405 | 18% |
| countries, continents, macro-regions | 58 | 76,146 | 35% |
| other colonies and their places, Indian provinces, foreign cities and ports | 98 | 77,691 | 36% |

**Demonyms as PLACE.** The model sometimes keys an adjectival surface to the country ("Indian" → `india`,
"Egyptian" → `egypt`). Across the whole type, exact demonym surfaces are 1,424 mentions (0.4%). In the head the
largest are `india` 253, `south america` 152, `egypt` 123, `america` 85. Demonym keys (`malay`, `american`,
`british`, `kandyan` and others) total 13 keys and 49 mentions. This is negligible, and the GROUP side of the
same problem is larger (§5).

**Estates and institutions typed PLACE.** Keys with an explicit marker are rare. Across all 41,772 keys:
"estate" 2 keys; "garden(s)" 77 keys/206 mentions (`covent garden`, `cinnamon gardens` are real places);
institute/college/school/observatory 37 keys/86 mentions (`colombo observatory` 38); "station" 127 keys/142
mentions; hotel/office/bank/mill/wharf 132 keys/205 mentions. None of these reach the top 200. The real leak
is hidden: Ceylon rainfall returns list estates as stations, and those estates arrive as PLACE with no
marker. 1,847 PLACE keys also exist as ESTATE keys. For 755 of them (2,030 mentions) ESTATE is the larger
count, which means they are estates. Examples from ranks 200-5000: `mariawatte`, `abbotsford`, `nivitigalakele`,
`kintyre`, `ingoya`, `st. coombs`, `culloden`, `pinehurst`, `gikiyanakanda`, `hoolankande`. In the
Ceylon-locality sample, 10 of 50 are estate names (`deanstone`, `westminster abbey`, `kenilworth`,
`sunderland`, `blackwood`, `oonoonagalla`, `geekianakanda`, `mahadova`, `mattakelle`, `st. martin's upper`).
The tail's (e) class is mostly addresses and buildings: "15, Evelyn-gardens, S.W.", "21, Mincing-lane, E. C.",
"Johore Hotel", "Freemasons' Hall, Edinburgh", "Jaffna Observatory", "R. G. A. Council Room", "Casino"
(22 of the 30). Estates make up 7 ("Dela Mindagama", "Helbakah", "St. Martins, Rangala", "Knavesmire" from
"Knavesmire Estates Co., Ltd.").

**Gazetteer coverage (`places.jsonl`, 3,207 rows).**

| set | exact surface | + case-insensitive key | + spelling variant | not found |
|---|---|---|---|---|
| top 200 keys | 152 | 152 | 154 (`north-western province`→"north-western provinces", `north-central province`) | 46 |
| 50 Ceylon-locality keys (ranks 200-5000, 3+ mentions, met/Ceylon roles) | 4 | 4 | 6 (`point de galle`, `eastern provinces`) | 44 |
| all keys, mention-weighted | | 1,345 keys = 59.0% of mentions | | |

The top-200 keys that are missing are mostly well-known places outside the Colonial Office List's scope:
`america`, `holland`, `california`, `florida`, `sweden`, `bolivia`, `guatemala`, `hamburg`, `santos`, `asia`,
`amazon`, `east indies`. Many Indian districts are also missing (`cochin`, `travancore`, `nilgiris`, `cachar`,
`sylhet`, `coorg`, `tinnevelly`, `malabar`, `mangalore`, `calicut`, `coimbatore`, `bangalore`, `ootacamund`),
and so are core Ceylon planting places: `maskeliya`, `hakgala`, `henaratgoda`, `kelani valley`, `dumbara`,
`diyatalawa`, `balangoda`, `jaffna peninsula`.

Fuzzy matching invents false links, and these would be wrong merges: `malabar`→"calabar" (86),
`austria`→"australia" (88), `east indies`→"west indies" (91), `vanni district`→"savanne district" (87),
`mannar district`→"mara district" (86). Any fuzzy step needs ratio ≥ 92 and the same first letter, or a human check.

The Ceylon portion of the gazetteer is 205 rows but only about 60 distinct places, many of them kachcheri
spellings. It covers 12% of a 50-key sample of Ceylon localities beyond the head (6/50). The gazetteer is fine
for countries and colonies. **It cannot ground Ceylon localities**: these need a Ceylon gazetteer (rainfall-station
lists, district and korale lists) or MCP lookup.

**Tail verdict: keep.** 81.5% of PLACE singletons are genuine rare places: Ceylon villages, tanks and korales
("Korgas Wewa", "Udugampola korale", "Chenakudirippu, suburb of Puttalam"), rivers, foreign towns. OCR and
spelling variants of common places are 5%. The patterns are letter swaps or drops on Ceylon names
("Maskeloya", "Triccomalee", "Hambantote", "Benaratgoda", "Kuliypitiya", "Dumbura district", "west province")
and older or foreign spellings ("Sharunpore", "Ouzco", "Assuncion", "Fohkien Province", "Tridest"=Trieste,
"Zarzikar"=Zanzibar). Generic phrases are 6% ("Government Agent's grounds", "Military cholera camp", "South",
"Spanish and Dutch territories", "the Campaigns of Rome", "Mars"), and so are compound lists that should have
been split ("Northern, North-Central and North-Western Provinces", "Hazaribagh and Lohardaga"). A fuzzy pass
against head keys at ratio ≥ 90 finds 255 non-head keys (2,404 mentions, 0.6% of PLACE). Real gains come from
long Ceylon names: `henaratgoda` gains 20 keys, `nuwara eliya` 13, `kurunegala` 13, `diyatalawa` 11,
`mincing lane` 6. False positives come from short or near-twin names: `prussia`→`russia`,
`ambalangoda`→`balangoda`, `jaffa`→`jaffna`, `australasia`→`australia`, `central provinces`→`central province`.

## 2. TAXON (164,859 mentions, 42,990 keys, 68% singletons, top 100 = 20% of mentions)

| slice | a | b | c | d | e | notes |
|---|---|---|---|---|---|---|
| head (200 keys, 44,570 mentions) | 150 | 40 | 3 | 0 | 7 | b = 11,462 mentions (26%); e = 1,728 (all animal diseases) |
| middle (100 keys) | 85 | 7 | 3 | 1 | 4 | 17 of the 85 are cultivars or varieties |
| tail (400 singletons) | 325 (81%) | 19 (5%) | 18 (4.5%) | 20 (5%) | 18 (4.5%) | 92/400 have a variety/clone/breed role |

**Head: the problem is scatter, not pollution.** The head contains no OCR garbage, and only 3 generic keys:
`palms`, `orchids`, `beans`. The 7 wrong-type keys are all animal diseases: `rinderpest` 396,
`foot-and-mouth disease` 303, `anthrax` 294, `rabies` 292, `piroplasmosis` 185, `haemorrhagic septicaemia` 150,
`black quarter` 108. But one in five head keys is a variant of another head key. The cause is the prompt's own
rule: norm = binomial "if the text gives a Latin binomial; otherwise the common name". So the same plant gets
a Latin key in one article and a common-name key in the next. There are 28 clusters (40 extra keys). The
canonical key is listed first:
- `cocos nucifera` ← `coconut`, `coconut palm`
- `hevea brasiliensis` ← `hevea`, `para rubber`, `rubber`
- `castilloa elastica` ← `castilloa`
- `manihot glaziovii` ← `ceara rubber`, `manihot`
- `coffea arabica` ← `arabian coffee`, `arabica coffee`
- `coffea liberica` ← `liberian coffee`
- `sugarcane` ← `sugar-cane`, `sugar cane` (hyphen/space only)
- `potato` ← `potatoes`
- `plantain` ← `plantains`
- `boehmeria nivea` ← `ramie`, `rhea`
- `theobroma cacao` ← `cacao`, `cocoa`
- `camellia sinensis` ← `tea`
- `erythrina lithosperma` ← `dadap`, `erythrina`
- `grevillea robusta` ← `grevillea`
- `mangifera indica` ← `mango`
- `carica papaya` ← `papaw`, `papaya`
- `manihot esculenta` ← `cassava`, `manioc`
- `erythroxylum coca` ← `coca`
- `gliricidia maculata` ← `gliricidia`
- `artocarpus integrifolia` ← `jackfruit`
- `agave sisalana` ← `sisal hemp`, `sisal`
- `cajanus cajan` ← `cajanus indicus`
- `sorghum vulgare` ← `sorghum`
- `rose` ← `roses`
- `orange` ← `oranges`
- `rice` ← `paddy`
- `maize` ← `corn`
- `grape` ← `vine`

Merging the 28 clusters turns 200 keys into 160. Twelve genus/species pairs are real hierarchy, not
duplication; keep them apart and link them as parent and child: `cinchona` (24 binomial siblings with ≥20
mentions, 542 cinchona-related keys, 7,210 mentions), `eucalyptus`, `acacia`, `ficus`, `albizia`,
`crotalaria`, `helopeltis`, `indigofera`, `citrus`, `agave`, `capsicum`, `landolphia`.

**Scientific vs common names in the head.** 54 keys are Latin binomials (11,845 mentions, 27%), 26 are
genus-only Latin (7,102, 16%), and 120 are common names (25,623, 57%). Across all keys, 23,542 have the
"two lowercase words" binomial shape (82,107 mentions), though many of those are common names like "red spider".

**Normalisation quality.**
- **Authorities.** Stripped almost perfectly: 5 keys out of 42,990 keep one (`coix lachryma-jobi linn.`).
- **Abbreviated genera.** Expanded well ("C. succirubra" → `cinchona succirubra`), and so are bare epithets
  ("succirubra", "Ledgeriana", "officinalis" go into the binomial). There are 141 bare-epithet keys
  (8,129 mentions), but nearly all are legitimate common names (`cacao`, `orange`). Context
  disambiguation of homonymous epithets works: I checked `cinchona robusta` by decade, and post-1900
  "Robusta" mentions sit in cinchona articles, not under `robusta coffee`.
- **Old synonyms instead of accepted names.** The model writes the period name: `pithecolobium saman`
  (Samanea saman), `erythrina lithosperma` (E. subumbrans), `leucaena glauca` (L. leucocephala),
  `gliricidia maculata` (G. sepium), `dolichos hosei` (Vigna hosei), `cedrela toona` (Toona ciliata),
  `sorghum vulgare` (S. bicolor), `artocarpus integrifolia` (A. heterophyllus). Sometimes it uses both:
  `cajanus cajan`/`cajanus indicus`, `castilloa elastica`/`castilla elastica`,
  `erythroxylum coca`/`erythroxylon coca`, `pithecolobium saman`/`inga saman`,
  `furcraea gigantea`/`fourcroya gigantea`. GBIF synonym resolution will collapse these. Do not try it with
  string rules.
- **Wrong binomials the LLM produced** (tail and middle). It picked the wrong genus:
  "eryodendron anfractuosum" → `erythrina anfractuosum` (kapok, Eriodendron/Ceiba);
  "Achmea fulgens" → `anthurium fulgens` (Aechmea); "Opeloxia regia" → `opuntia regia` (role "palm");
  "Phytelophas macrocarpa" → `phytolacca macrocarpa` (Phytelephas, the ivory palm);
  `ichneumon purchasi` for the fluted scale (Icerya purchasi). That is 5 in 500 sampled rare keys. Add the
  ones the first review found (arnatto → *Lawsonia inermis*) and **about 1% of rare binomials are confidently
  wrong**. GBIF will accept most of them, because they are valid names, just the wrong ones. Only a check that
  the key's genus also appears in the surface form catches them.
- **OCR-corrupted Latin kept as printed** (tail, 15 more): `indigofera cendacaphylla`, `helopellis antonii`,
  `cinchona eucirubra`, `cinchona ledigiana`, `acacia decurrens decalbata`, `cardiospermum helicacabum`,
  `sterculia coloraba`, `ovularia bixce`, `zulacca edulis`, `augrecium fragrans`, `hegonia`, `grossotarsus`,
  `cacocur coccinea`. Corruption is letter-level (c↔e, l↔t, b↔h, rn↔m, dropped letters). The epithet usually
  survives, so a genus+epithet fuzzy match against GBIF (ratio ≥ 88 on the full binomial) recovers most of them.
- **Varieties and cultivars are a large, valuable share.** 9,456 keys (22%, 30,927 mentions) have a
  variety/clone/breed role, and 23% of tail singletons do: sugar-cane clones (`b.3390`, `mauritius 55 p`,
  `barbados 3390`), rubber clones (`kobowella 41`, `gondang tapen i`), paddy varieties (`suduwi`,
  `palaisitari`, `kadippu`), named fruit cultivars (`louise bonne de jersey`, `boule de neige`, `ruby blood`),
  and livestock breeds (`border leicester sheep`, `thar-parkar cattle`, `single comb white leghorns`). GBIF
  will not find them. They need a CULTIVAR sub-type with a parent taxon, which the role text usually gives
  ("sugar-cane variety", "variety of plantain").

**TAXON/COMMODITY boundary.** The split is by design ("tea" the plant vs "tea" the good). The overlap is large:

| overlap | keys | share of TAXON | share of COMMODITY |
|---|---|---|---|
| TAXON ∩ COMMODITY, keys | 1,967 | 4.6% of keys | 17.8% of keys |
| ... mentions carried by those keys | | 45,781 (27.8%) | 98,321 (73.2%) |
| top-200 TAXON keys also in COMMODITY | 112/200 | | |
| top-200 COMMODITY keys also in TAXON | 136/200 | | |
| keys with ≥10 mentions in both | 266 | | |

Biggest double-typed keys (TAXON/COMMODITY mentions): `tea` 213/15,248, `coffee` 357/9,565, `rubber` 124/4,841,
`cinchona` 2,054/1,458, `tobacco` 210/2,487, `cacao` 632/2,044, `cocoa` 162/2,484, `cotton` 238/2,010,
`rice` 192/1,988, `coconut` 1,235/905, `paddy` 165/1,694, `cinnamon` 191/1,568. For the plantation staples
the split looks plausible. Where TAXON wins (cinchona, coconut, orange, mango, banana, maize) the journal is
writing about cultivation. Leaking errors are few and small: `plumbago` TAXON 30 (in Ceylon, plumbago is
graphite), `sugar` TAXON 7, `quinine` 1, `ceylon tea` 1, `cinchona bark` 1. **Recommendation:** do not try to
fix the split. Give the KG one concept node per crop (e.g. tea → Camellia sinensis) with two mention senses,
`as_taxon` and `as_commodity`, joined through the crosswalk below.

**Tail verdict: keep, with GBIF and crosswalk.**
- 81% of TAXON singletons are genuine rare taxa, local names or cultivars (`isonandra quercifolia`,
  `cubeba mollissima`, `kanch kola` plantain, `anjely` = Artocarpus hirsutus).
- 5% are variants of common keys: plurals (`tephrosias`, `australian parrots`), `paddy rice`, `guava tree`,
  `sunnherp`, `annattu`, `sicily lemons`.
- 5% are corrupted or wrongly normalised Latin.
- 4.5% are generic: "witch brooms", "caterpillars of a minute moth", "marine algae", "biting house flies",
  "Spinosa" (an exhibit class), "uredo-spore".
- 4.5% are the wrong type: 11 diseases ("pleuro pneumonia", "garget", "Isle of Wight disease",
  "stem-end rot", "withertip"), 4 minerals/soils/geology ("rensselaerite", "dichroite", "rendzinas",
  "ARAVALLIS"), and 3 commodities ("Peruvian gum", "Gutta Taban merah", "locust beans").

A fuzzy pass would not help much here; the merge gains come from the crosswalk (§6, rule T2).

## 3. COMMODITY (134,358 mentions, 11,021 keys, 65% singletons, top 100 = 62% of mentions)

| slice | a | b | c | d | e | notes |
|---|---|---|---|---|---|---|
| head (200 keys, 96,686 mentions) | 165 | 29 | 6 | 0 | 0 | b = 8,645 mentions (8.9%) |
| middle (100 keys) | 72 | 13 | 4 | 0 | 11 | 16 of the 72 are named grades/origins |
| tail (400 singletons) | 316 (79%) | 35 (9%) | 25 (6%) | 3 (1%) | 21 (5%) | |

**Head.** These are real traded goods, and the list reads like the journal's Market Rates column. The 6 generic
keys are `oil` 223, `fibre` 161, `fibres` 123, `spices` 107, `beans` 161 and `tannin` 114 (a chemical
constituent, not a good). 29 keys are variants. The canonical key is listed first:
- `rubber` ← `indiarubber`, `india rubber`, `india-rubber`, `caoutchouc` (1,023 mentions; worth keeping an
  era flag, since "indiarubber" is the pre-plantation wild product)
- `cocoa` ← `cacao`
- `cinchona bark` ← `cinchona`
- `coconuts` ← `coconut`
- `nutmegs` ← `nutmeg`
- `cardamoms` ← `cardamom`
- `vanilla` ← `vanilloes`
- `sugar-cane` ← `sugarcane`, `sugar cane`
- `maize` ← `corn`, `indian corn`
- `gutta-percha` ← `gutta percha`
- `sapanwood` ← `sapan wood`
- `croton seeds` ← `croton seed`
- `sandal wood` ← `sandalwood`
- `assafoetida` ← `assafetida`
- `sulphate of quinine` ← `quinine sulphate`
- `tortoiseshell` ← `tortoise shell`
- `citronella oil` ← `citronelle`, `citronella`
- `lemongrass` ← `lemongrass oil`
- `oranges` ← `orange`
- `bananas` ← `banana`
- `china tea` ← `chinese tea`
- `areca nuts` ← `arecanuts`
- `coca` ← `coca leaves`

Half of these clusters are just singular/plural or space/hyphen differences, which rule K1 (§6) handles.

**Generic goods vs named grades.** The head mixes generic goods (`tea`, `sugar`, `milk`, `timber`, `wine`) with
named grades and types. Tea: `pekoe` 331, `pekoe souchong` 199, `souchong` 184, `congou` 181,
`broken pekoe` 152, `orange pekoe` 98, `green tea` 459, `black tea` 244, `brick tea` 100, `oolong tea` 95.
Origin-qualified goods: `indian tea` 681, `ceylon tea` 628, `china tea` 273, `para rubber` 447. Across the
whole list there are 239 tea-grade keys (2,155 mentions), e.g. `broken orange pekoe`, `flowery pekoe`,
`young hyson`, `fannings`. Rubber grades are rarer than expected: 46 keys and 148 mentions (`crepe rubber`,
`smoked sheet`, `negrohead`, `blanket crepe`, `ceara scrap`), presumably because the first review saw them
going to PRODUCT. Beyond the head, origin-qualified composites from the price lists ("SANTOS coffee",
"CASTOR OIL, Calcutta", "CHILLIES, Zanzibar") make 831 keys (2,176 mentions). Model them as commodity + origin
PLACE, not as separate commodity nodes. Grades (pekoe, crepe) should stay as their own nodes with a `grade_of`
link to the parent commodity.

**Overlaps.** COMMODITY ∩ TAXON is in §2: 1,967 keys, 73% of COMMODITY mentions. COMMODITY ∩ PRODUCT is 1,227
keys, carrying 32,237 COMMODITY mentions (24%) and 7,283 PRODUCT mentions (35%). 130 of the top 200 PRODUCT
keys are also COMMODITY keys. Most are fertilisers and chemicals: `sulphate of ammonia` 348 PRODUCT/90
COMMODITY, `superphosphate` 280/63, `nitrate of soda` 243/119, `basic slag`, `kainit`, `lime`, `kerosene`,
`poonac`. Those belong in COMMODITY (§4).

**Middle.** Its wrong types are chemicals that are not traded goods (`isoprene`, `benzoic acid`,
`lauric acid`), a soil (`cabook` = laterite), and crops discussed as plants (`mangold`, `sugar-beet`,
`beet-root`, `finger millet`). There is also one normalisation error: `arabic coffee` was built from
"ARABIC E. I. & Aden", which is gum arabic in the drug list. A related merge bug: `betel nuts` absorbed a
"NUX VO IICA" surface.

**Tail verdict: keep, after a variant pass.** 79% are genuine rare goods, grades and trade names (`hoyune`,
`ponchong`, `ning chow cong`, `s.o.p.`, `mid uplands cotton`, `manitoba hard`, `santos pea berry`,
`alleppey cardamoms`, `calpenty` copra, `oscuros` cigars). Variants and OCR forms of head goods are 9%, the
highest of the five types. They come mostly from upper-case price-list OCR: `murrine` ("MURMERIC" =
turmeric), `colombo roft`, `new vomit` ("NEW VOMICA"), `chutch` (cutch), `hyrabolanes` (myrobalans),
`assaf citida`, `toitoeshell`, `acao`, `coea`, `cubobs`, `copeanut oil`, `manicoa`/`manicaba`, `pecoe`,
`congu`, `gin-gelly`, `kavok`. Inverted "X, origin" forms add more: "coconut (desiccated)",
"ceylon, mysore cardamoms". Non-entities are 6%: "areas", "shall", "leaf", "stones", "clays",
"tropical products", "country produce", "Good Ordinary" (a quality descriptor), "Amsterdam pounds" (a unit).
Wrong types are 5%: financial instruments ("Ceylon Government 3 per cent. war loan 1956/60", "Indian Bonds",
"East India and Ceylon Ordinary shares"), brands and machines ("Tiger Asahan" rubber brand, "Motor Car"),
"elephantiasis", and lab chemicals (`cineole`, `hydroquinone`, `butanediene`, `methyl salicylate`, `helium`).

## 4. PRODUCT (20,559 mentions, 9,949 keys, 79% singletons)

For PRODUCT, "a" means a legitimate named product: brand, patent, named machine or proprietary preparation.

| slice | a | b | c | d | e | notes |
|---|---|---|---|---|---|---|
| head (200 keys, 6,684 mentions) | 39 | 8 | 136 | 0 | 17 | legit a+b = 47 keys (23.5%) but only 1,119 mentions (17%) |
| middle (100 keys) | 40 | 6 | 35 | 0 | 19 | e = 12 ships + 7 commodities |
| tail (385 of 400 singletons classified) | 150 (39%) | 24 (6%) | 149 (39%) | 0 | 62 (16%) | e = 35 ships, 14 commodities, 13 other |

**The head is a fertiliser and chemicals list.** The top eight keys: `sulphate of ammonia` 348, `superphosphate`
280, `bordeaux mixture` 247, `nitrate of soda` 243, `sulphate of potash` 231, `basic slag` 186, `kainit` 161,
`paris green` 155. 136 of the top 200 are generic substances (manures, chemicals, acids, foods). 17 are wrong
type: commodities (`cigars`, `chocolate`, `margarine`, `arrack`, `coconut oil`, `castor oil`, `brick tea`,
`crepe rubber`, `candles`, `soap`, `poonac`, `petroleum`, `sulphate of quinine`, `coconut butter`), a ship
(`moyune`), a method (`indore process`) and a test (`schimmel's test`). The real named products are exactly
what the prompt intended:
- tea machinery: `sirocco` 139, `excelsior`, `davidson's sirocco`, `jackson's roller`, `clerihew`,
  `american evaporator`, `brown's desiccator`, `venesta`/`acme` tea chests
- implements: `meston plough`, `planet junior`, `fordson`
- branded fertilisers: `nitrolim`, `nicifos`, `ammophos`, `ephos phosphate`, `adco`, `nitragin`
- disinfectants and pesticides: `izal`, `jeyes' fluid`, `condy's fluid`, `brunolinum`, `sulfinette`,
  `vaporite`, `rough on rats`
- patent medicines: `tabloid`, `howard's quinine`, `wells' rough on corns`, `buchu-paiba`

Variants among these: `sirocco` ← `davidson's sirocco`, `no. 3 sirocco`; `excelsior` ← `excelsior roller`,
`jackson's excelsior`; `jeyes' fluid` ← `jeye's fluid`; `fordson` ← `fordson tractor`;
`brunolinum` ← `brunolinum plantarium`; `jackson's roller` ← `jackson's rollers`.

**Ships are a systematic leak.** 12% of the middle and 9% of the tail are ships ("Chusan", "Orinoco",
"Duke of Buckingham", "ss. Shropshire", "HMS Peacock"). This matches the first review's "no SHIP type". Named
processes ("Northway tapping system", "Frémy-Urbain process", "Ekman process", "Bessemer process",
"powellizing") are borderline. They are patented techniques; I counted them as a, but they could go to a
METHOD sub-type. The tail also contains person and firm lists and financial instruments ("Ceylon Government
War Loan 1954", "british patent no. 152387", "Lieber's codes").

**Filter P (tested).** Three steps, in order:
1. `SHIP` if the key starts with `ss |s.s. |hms |uss |rms `, or the top role matches
   `\b(ship|steamer|steamship|vessel|barque|clipper|launch|liner|destroyer|schooner|boat|s\.s\.)\b`
   without a machine word.
2. `GENERIC` if the key is in a stop-list of named generic preparations ("bordeaux mixture",
   "burgundy mixture", "paris green", "london purple", "prussian blue", "scheele's green", "portland cement",
   "epsom salts", "dover's powder", "schimmel's test", "indore process", "mamoty", "chekku", "raspador"), OR the
   key matches a chemical/fertiliser/food lexicon:
   `\b(sulphate|nitrate|phosphates?|chloride|acid|oxide|carbonate|arsenate|arsenite|cyanide|cyanamide|muriate|superphosphates?|slag|kainit|guano|manures?|meal|cake|dust|bones?|blood|lime|potash|soda|ammonia|ammonium|potassium|sodium|calcium|copper|iron|kerosene|kerosine|paraffin|tar|creosote|formalin|glycerine|alum|borax|sulphur|arsenic|gypsum|emulsion|oil|soap|salts?|wine|flour|sugar|butter|tea|coffee|cocoa|chocolate|rubber|crepe|alkaloid|quinine|caffeine|nicotine|...|gas)\b`
   with no "named" signal, OR ≥50% of its surfaces start lower-case.
3. `KEEP` if the key has a named signal (`\w's\b`, `\ws'\s`, `patent`, `no. \d`, `brand`, `model`, `system`,
   `process`), or the top role contains a machine/brand word
   (`machine|drier|dryer|roller|plough|implement|apparatus|brand|patent|proprietary|tractor|engine|pump|sprayer|press|decorticator|extractor|harrow|cultivator|drill|winch|kiln|chest|invention|label|blend|chop|process|method|system`).
   Capitalised keys with a generic-substance role go to a small `GENERIC_CAP` review bucket.

Results on the full PRODUCT.tsv:

| bucket | keys | mentions | share |
|---|---|---|---|
| KEEP (named product) | 5,164 | 7,783 | 37.9% |
| GENERIC (substance → raw mention, or COMMODITY if the key exists there) | 3,479 | 10,984 | 53.4% |
| SHIP (→ new SHIP type) | 913 | 1,254 | 6.1% |
| GENERIC_CAP (review; about half are brands) | 346 | 487 | 2.4% |
| OTHER (test, chart, loan, bonds, prize) | 47 | 51 | 0.2% |

Checked against my manual labels:
- Head: 42/42 kept are right (precision 100%). Recall is 42/46; misses are `ephos phosphate` and
  `brunolinum plantarium`, plus `victoria`/`britannia`, which are both ships and driers.
- Middle: precision 42/45 (`chulas`, `chinese indigo`, `disc-harrow` wrongly kept), recall 42/45 (`buisol`,
  `n. r. nicifos`, `black leaf 40` sent to GENERIC_CAP). Ships 12/12.
- Tail: 216/400 kept. In a 40-key spot check of the kept set, about 10 are wrong (`toxine`, `uranite`,
  `leyden jar`, `hevea para`, `cudbear`, generic "tea rolling machine"). That is roughly 75% precision, up from
  about 40% before filtering. In 40 GENERIC keys, about 4 are lost brands ("Liberty Tea", "Panto",
  "Exchequer Tea", "Hyperion tea").

## 5. GROUP (23,623 mentions, 4,177 keys, 74% singletons, top 100 = 66% of mentions)

For GROUP, "a" means a genuine people-group (ethnic, national, caste, religious, tribal).

| slice | a | b | c | d | e | notes |
|---|---|---|---|---|---|---|
| head (200 keys, 17,283 mentions) | 92 | 39 | 18 | 0 | 51 | e = 4,245 mentions (24.6%) |
| middle (100 keys) | 40 | 10 | 26 | 0 | 24 | |
| tail (400 singletons, approximate) | ~190 (47%) | ~25 (6%) | ~80 (20%) | ~5 (1%) | ~100 (25%) | e = ~50 person/firm lists and families, ~25 organisations, ~25 adjectives/places/breeds/languages |

**Head.** The head has the right entities (Sinhalese, Tamils, Chinese, Moormen, Burghers, Chetties, Kandyans,
Malays, Javanese, the Dutch), but it is badly split and polluted.
- **Singular adjective keys (51 e)**: `indian` 721, `english` 569, `british` 439, `german` 314,
  `american` 302, `european` 201, `russian` 197, `australian` 146, `west indian` 125, `brazilian` 104,
  `east indian` 89, `italian` 82, `african` 65, `persian` 59, and 37 more. I checked them with the next word
  after each mention, across the whole corpus (below). Most modify goods, markets or firms ("German quinine",
  "American market", "English apple sauce", "British capital", "Indian do" in price tables), not people.
- **Occupational classes (18 c)**: `coolies` 399, `ryots` 125, `natives` 224, `ceylon planters`,
  `indian planters`, `european planters`, `planting community`, `agricultural instructors`, `kanganies`,
  `seringueiros`, `mudaliyars`, `mandarins`. The prompt's own example "Tamil coolies" invited these.
- **Languages and concepts**: `sanskrit`, `hindustani`, `arabic`, `buddhism`; `jesuits` is an ORG.
- **Variants**: the 39 b keys. In one example, Muslims are scattered over `mahomedans`, `mohammedans`,
  `muhammadans`, `mahomedan`, `muhammadan` (plus `mussulman`, `muhammedans` in the tail). In another, Hindus
  are spread over `hindu`, `hindus`, `hindoo`, `hindoos`.

**Context test for adjectival mentions (whole corpus, 23,623 GROUP mentions).** For each mention I took the
word after the surface form in the article text:
- noun forms (plural, -men, "the Dutch"): 49%
- adjective + people noun ("Tamil labourers", "Dutch planters"): 7.3%
- adjective + verb or preposition, i.e. used as a noun ("the Chinese are"): 5.9%
- coordinations ("Indian and Ceylon"): 4.8%
- adjective + non-person noun: 22.0% (5,205 mentions; top next words `tea`, `market`, `teas`, `markets`,
  `capital`, `districts`, `bulk`, `trade`, `varieties`, `cattle`, `seed`, `coffee`, `bark`, `rubber`)
- language uses ("the Sinhalese name", "in Tamil"): 0.9%

Per key, the non-person-noun share is high: `indian` 360 of 677, `english` 287/490, `british` 245/411,
`american` 204/267, `german` 189/276, `dutch` 186/386. It is also substantial for the invariant forms:
`sinhalese` 437/1,309, `chinese` 507/1,244.

**Tail.** About half are genuine rare groups, a valuable list for a history KG: castes and communities (Vannias,
Madigas, Panchkalshas, Berawayā, Rodiyas, Badagas), tribes (Semangs, Wa-kikuyu, Kanikkars, Ackawoi, Kadayans,
Hill Shan) and period ethnonyms. The rest:
- **Person and firm lists, and families**: "Young, Welsh, Waddell and Logan", "Lawes, Gilbert, and Warington",
  "Worms and Sabonadiere", "de Soysas", "Berkeley family". There are 281 list keys in the whole list.
- **Occupations**: "milkmen of Madras", "Tamil kanganies", "rubber planters", "police officers", "quineros".
- **Organisations**: "Central Africa Rifles", "Alpine Club", "Irish party", "Planters' Associations".
- **Adjectives, places, breeds, languages**: "Angora" (goat breed), "Scind" (bull breed), "korales"
  (administrative divisions), "Prakrit", "Ayurvedic", "Yoga".

**Filter G (tested on GROUP.tsv).** Apply in order:

| step | rule | keys | mentions | share |
|---|---|---|---|---|
| G1 | key matches `(,|\band\b|&)|\b(family|families|house of|clan|brothers|bros\.?)\b` → split into PERSON/ORG, drop from GROUP | 362 | 390 | 1.7% |
| G2 | key matches an org word (`compan(y|ies)|industry|association|society|club|party|church|mission|rifles|regiment|cavalry|volunteers|team|crew|committee|council|government|estates|firms|guilds?|bank`) → ORG | 92 | 115 | 0.5% |
| G3 | key ends in an occupation word (`coolies?|cooly|labou?rers?|natives?|planters?|ryots?|kangan(y|ies|is)|seringueiros|caucheros|quineros|headmen|mudaliyars?|mandarins?|officials|traders|merchants|dealers|brokers|manufacturers|growers|consumers|buyers|doctors|zemindars|...`) → OCCUPATION sub-type (keep: coolies and kanganies matter to this history). For "Tamil/Indian/Chinese/Malabar/Telugu ... coolies", also emit the ethnic group | 359 | 1,770 | 7.5% |
| G4 | key in {sanskrit, hindustani, arabic, hindi, pali, prakrit, latin, hebrew, buddhism, islam, christianity, hinduism, yoga, ayurvedic, swadeshi} → drop | 14 | 97 | 0.4% |
| G5 | mention level: the surface is a singular adjective form (not plural, not -men/-man, not "the X"), AND the next word in the article is a lower-case word that is not a people noun, not a function word, not "and/or" → drop the mention (optionally keep it as an origin attribute) | | ~5,200 | ~22% |
| G6 | alias + plural merge on what remains (`hindoo(s)/hindus`→hindu; `mahomedan(s)/mohammedan(s)/muhammadan(s)/muhammedan(s)/mussulman/moslem`→muslim; `cingalese/singhalese/singalese`→sinhalese; `kandian(s)/kandyans`→kandyan; `goiya(s)/goyas/goyia/goyiyas`→goyigama; `chinamen`→chinese; `englishmen`→english; `burman(s)`→burmese; `chetties/chettiars`→chetty; `moormen/moors`→moor; then rule K1 below) | 3,350 → 2,952 | 4,019 moved | |

After G1-G5, about 68% of GROUP mentions survive as people-group mentions. After G6 the surviving keys
collapse by a further 12%.

## 6. Normalisation and filter rules (exact operations, counts from runs on the TSVs)

**K1, surface normalisation of the key** (TAXON, COMMODITY, PRODUCT, GROUP):
1. Replace æ→ae and œ→oe.
2. Turn hyphens and dashes into spaces.
3. Strip trailing `. " ' * _`, and a leading `the `/`a `/`an `.
4. Collapse whitespace.
5. Singularise the last word: `ies`→`y`; `oes|ches|shes|xes|sses` drop `es`; otherwise drop a final `s`.
   Skip words ending `ss|us|is|ese|ous` and a protected list (`swiss`, `chinese`, `citrus`, `molasses`,
   `species`, `indies`, `straits`, `philippines`, `seychelles`, `nilgiris`, `madras`, `barbados` ...).

Do not singularise PLACE; use only steps 1-4 there.

| type | keys before → after | mentions moved onto a larger sibling | head-internal merges |
|---|---|---|---|
| PLACE (steps 1-4 only) | 41,772 → 41,369 | 1,136 (0.3%) | 0 |
| TAXON | 42,990 → 40,921 | 8,488 (5.1%) | 5 |
| COMMODITY | 11,021 → 10,089 | 5,986 (4.5%) | 11 |
| PRODUCT | 9,947 → 9,554 | 634 (3.1%) | 6 |
| GROUP (before filter G) | 4,177 → 3,784 | 3,167 (13.4%) | 48 |

Sampled merges are all correct: `palm oil`/`palm-oil`/`palm oils`, `groundnut`/`groundnuts`, `jackson's drier`/
`jackson's driers`, `sea island cotton`/`sea-island cotton`, `kanganies`/`kangany`. For GROUP, run filter G5
first, or singular adjectives will merge into the plural people-group.

**T1, TAXON disease filter → new DISEASE type.** Two conditions:
- The key contains a disease word (`disease|fever|pox|plague|murrain|septicaemia|anthrax|rabies|glanders|surra|mange|rinderpest|tuberculosis|pleuro-?pneumonia|piroplasmosis|black ?quarter|blackleg|rot|wilt|blight|canker|die-?back|withertip|beri-?beri|malaria|cholera|garget|mastitis|anthracnose|mildew|rust|spot|mosaic|smut|...`)
  and is not a pest name (`mite|beetle|moth|bug|fly|weevil|borer`), and the top role has no
  pest/pathogen/plant word.
- Or the top role is exactly "(animal|cattle|plant|...) disease" and the key is not Latin-shaped.

Result: **534 keys, 3,771 mentions (2.3% of TAXON)**. It catches all 7 head diseases. Pathogen binomials stay
in TAXON (`hemileia vastatrix` 884, `corticium salmonicolor`, `cercospora theae`). Remaining misses are
`sereh disease`, `tetanus`, `anaplasmosis`, `roup`, `bunt`; add them to a word list.

**T2, data-driven common-name → binomial crosswalk** (TAXON, and through it the COMMODITY "as_taxon" link):
1. For every Latin-shaped key with ≥3 mentions, collect its non-Latin surface forms (lower-cased,
   hyphens to spaces).
2. A surface that points ≥70% of the time to one binomial, and occurs ≥2 times, becomes a crosswalk entry.
3. Map common-name keys (and their -s plural) onto it.

Result: **1,170 crosswalk entries; 615 common-name keys (17,973 mentions, 10.9% of TAXON) map onto a binomial**.
Examples: `coconut`→cocos nucifera, `cacao`→theobroma cacao, `maize`→zea mays, `dadap`→erythrina lithosperma,
`ramie`/`rhea`→boehmeria nivea, `cassava`/`manioc`→manihot esculenta, `teak`→tectona grandis,
`shot-hole borer`→xyleborus fornicatus. Use a stop-list for genus-level common names that the crosswalk
over-specifies: `coffee`→coffea arabica is wrong, and the same applies to `rubber`, `cotton`, `orange`,
`banana` (Musa spp.). Then resolve the binomials themselves through GBIF synonymy.

**T3, binomial sanity check.** Flag a Latin key when its genus does not appear (fuzzy ratio ≥ 80) in any of
its surface forms, and the surfaces are not a common name in the crosswalk. This catches the confidently
wrong renormalisations (`erythrina anfractuosum` from "eryodendron", `anthurium fulgens` from "Achmea",
`phytolacca macrocarpa` from "Phytelephas") that GBIF would accept as valid names.

**C1, COMMODITY composites.** Rewrite `X, origin` and `origin X` keys where X is a top-500 commodity key and
origin is a top-2000 PLACE key or demonym (831 keys, 2,176 mentions) to (commodity X, origin PLACE). Keep tea
and rubber grades (`pekoe`, `broken orange pekoe`, `crepe rubber`; 239 + 46 keys) as grade nodes with
`grade_of`. Move financial instruments (`shares|bonds|loan|stock`) out of COMMODITY.

**P1, PLACE estate leak.** For a PLACE key that also exists in ESTATE with an ESTATE count ≥ its PLACE count
(755 keys, 2,030 mentions), especially when the role is "meteorological/rainfall station", retype to ESTATE.
Retype keys matching a street number or address (`^\d+,? |\b(street|st\.|road|lane|place|crescent|terrace|e\.c\.|s\.w\.)\b`
with a role of "address"/"office") to an ADDRESS attribute, not a PLACE node.

**P2, PLACE fuzzy merge guard.** Merge a tail key into a head key only at ratio ≥ 92, with the same first
letter, and both keys ≥ 6 characters. Keep a never-merge list of near-twin pairs: australia/austria/australasia,
russia/prussia, jaffna/jaffa, balangoda/ambalangoda, central province/central provinces, west/east indies,
malabar/calabar, matale/matara. Fix `matara`, which has absorbed "MATALE".

**PR1 (PRODUCT) and G1-G6 (GROUP)** are in §4 and §5.

## 7. Overlap numbers (keys = case-folded normalised name)

| pair | shared keys | mentions in first type | mentions in second type |
|---|---|---|---|
| TAXON ∩ COMMODITY | 1,967 | 45,781 (27.8% of TAXON) | 98,321 (73.2% of COMMODITY) |
| COMMODITY ∩ PRODUCT | 1,227 | 32,237 (24.0% of COMMODITY) | 7,283 (35.4% of PRODUCT) |
| TAXON ∩ PRODUCT | 343 | 4,515 (2.7%) | 1,058 (5.1%) |
| GROUP ∩ PLACE | 174 | 2,357 (10.0% of GROUP) | 34,562 (9.2% of PLACE; these are big place keys like `india`, `malay`) |
| PLACE ∩ ESTATE | 1,847 | 53,198 | (755 keys ESTATE-dominant, 2,030 PLACE mentions) |

## 8. Recommended thresholds for the knowledge graph

"Node" means a KG entity node, linked to an authority where possible. Everything else stays as a raw mention
row (article id, surface, role), so nothing is lost and later evidence can promote it. Coverage figures are
before the filters above.

| type | node if... | coverage | rationale |
|---|---|---|---|
| PLACE | gazetteer/MCP-grounded at any count; ungrounded only if ≥2 mentions in ≥2 articles after P1/P2 | ≥2 & ≥2 art = 12,015 keys, 91.9% of mentions | Tail is 81% genuine. Grounding, not frequency, is the evidence. Singletons wait in a lookup queue (Ceylon gazetteer / MCP). |
| TAXON | GBIF-resolved (after T1-T3, including fuzzy-binomial recovery) at any count; cultivars if ≥2 mentions with a "variety/clone/breed" role and a parent taxon; unresolved common names if ≥3 mentions in ≥2 articles | ≥3 & ≥2 art = 7,854 keys, 75.0% | Tail is 81% genuine but heavy in local names and cultivars that GBIF lacks |
| COMMODITY | ≥3 mentions in ≥2 articles after K1/C1; grades and trade names at ≥2 | ≥3 & ≥2 art = 2,580 keys, 92.8% | Head is clean and concentrated. The tail is mostly price-list OCR variants and one-off goods. |
| PRODUCT | KEEP bucket of filter P only, ≥2 mentions in ≥2 articles, or 1 mention with a possessive/patent/brand key | KEEP ≥2 & ≥2 art ≈ 1,000 keys | Even filtered, 1-mention products are about 25% wrong; machines and brands recur |
| GROUP | after G1-G6, ≥3 mentions in ≥2 articles, plus any caste/tribe singleton with a people role ("tribe", "caste", "community", "people") | ≥3 & ≥2 art = 684 keys, 83.5% (before filter) | Rare castes and tribes are historically valuable. Most other singletons are lists, occupations or adjectives. |
| new: DISEASE, SHIP, OCCUPATION | ≥2 mentions | 534 / 913 / 359 keys | These are the reroutes from T1, P and G3 |

## 9. Summary

1. PLACE is clean. The head is 193 a + 7 variants, with no garbage. 82% of singletons are genuine rare places.
   Keep the tail and ground it; do not cut by frequency.
2. PLACE's real gaps are elsewhere. `places.jsonl` covers 152/200 head keys (88% of head mentions) but only
   6/50 Ceylon localities. 755 PLACE keys are really estates (rainfall stations), and addresses leak into the
   tail (7.5%).
3. TAXON's problem is scatter. 40 of 200 head keys are variants (28 clusters), because norm is binomial only
   when the text gives one. A data-driven crosswalk maps 615 common-name keys (10.9% of mentions) onto binomials.
4. TAXON pollution is small and specific: animal diseases (7 head keys; 534 keys / 2.3% corpus-wide by rule
   T1). About 1% of rare binomials are confidently wrong genus substitutions that GBIF will not catch.
5. 22% of TAXON keys are cultivars, varieties and breeds. They need a CULTIVAR sub-type with a parent taxon.
6. TAXON ∩ COMMODITY: 1,967 keys, carrying 73% of COMMODITY and 28% of TAXON mentions. 112/200 TAXON head keys
   and 136/200 COMMODITY head keys appear in both. Model one concept per crop with two mention senses.
7. COMMODITY is the healthiest list: 165/200 head keys clean, 79% of singletons genuine. Its tail has the most
   OCR variants (9%), from upper-case price lists ("MURMERIC", "NEW VOMICA", "COLOMBO ROFT").
8. PRODUCT is mostly not products. Only 47/200 head keys (17% of head mentions) are brands, patents or
   machines; the rest are fertilisers and chemicals. Ships are 6-12% of the middle and tail.
9. Filter P keeps 5,164 keys (38% of mentions) at 100%/93% precision on head/middle and about 75% on the tail.
   It moves 913 ship keys to SHIP and 3,479 generic keys out.
10. GROUP: 92/200 head keys are clean people-groups. 51 are singular adjectives; context shows 22% of all
    GROUP mentions modify goods or markets ("German quinine"). 18 are occupations, and the tail includes
    362 person/firm lists and families.
11. Filter G (G1-G6) keeps about 68% of GROUP mentions as people-group references. It moves occupations
    (7.5%) to an OCCUPATION sub-type and collapses the surviving keys by 12% through aliases
    (Mahomedan/Mohammedan/Muhammadan → Muslim, Cingalese → Sinhalese).
12. Plural/hyphen normalisation (K1) alone merges 4-13% of the mentions of TAXON, COMMODITY, PRODUCT and
    GROUP onto larger siblings, at negligible false-merge risk. For PLACE it is 0.3% (no singularising).

Top 3 rules:
- **(1)** Reroute rather than delete. TAXON diseases → DISEASE (T1); PRODUCT ships → SHIP and chemicals →
  generic/COMMODITY (filter P); GROUP lists → PERSON/ORG, occupations → OCCUPATION, and adjective-before-thing
  mentions dropped (G1-G5).
- **(2)** Normalise before counting: K1 plus the GROUP alias map, the T2 crosswalk, and C1 origin
  decomposition. Only then apply the frequency thresholds.
- **(3)** Thresholds by evidence, not frequency, for the two clean types. Any grounded PLACE or GBIF-resolved
  TAXON becomes a node, singletons included. For COMMODITY and GROUP require ≥3 mentions in ≥2 articles, and
  for filtered PRODUCT ≥2 in ≥2. Everything below threshold stays as raw mentions.
