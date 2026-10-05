# R2-A: frequency-ranked entity lists — PERSON, ORG, ESTATE, PUBLICATION, EVENT

Reviewer R2-A, 2026-10-05. Input: `ranked/<TYPE>.tsv`, `ranked/<TYPE>_tail_sample.tsv`, gazetteers.
Sections were written type by type; the cross-type summary, rules and thresholds are at the end.

## Classes used
(a) real entity, correct type; (b) real but a variant of another key (honorific/initials/OCR spelling/surname-only form);
(c) not a single entity: office title, generic term, pen-name or initials signature, or a list of several people/firms
in one key; (d) OCR garbage or a broken key; (e) wrong type. In the head, the most frequent (or most complete) key of
a cluster is counted (a) and the others (b). Head = top 200 keys; middle = 100 random keys with 3-10 mentions
(seed 42); tail = the 400 singletons in `<TYPE>_tail_sample.tsv`.

## PERSON (150,754 mentions, 59,371 keys, 71.9% singletons, top 100 = 9.1% of mentions)

| slice | n | a | b | c | d | e |
|---|---|---|---|---|---|---|
| head (top 200) | 200 | 151 | 39 | 10 | 0 | 0 |
| head, by mentions | 20,473 | 75.8% | 18.2% | 6.0% | 0 | 0 |
| middle (3-10) | 100 | 79 | 16 | 5 | 0 | 0 |
| tail singletons | 400 | 320 | 40 | 35 | 2 | 3 |

**Head (c), 10 keys:** "director of agriculture" (#2, 400 mentions), "the governor", "governor", "governor of ceylon",
"colonial secretary", "secretary of state", "chancellor of the exchequer", "director of public instruction",
"w. a. d. s." (initials signature of a letter-writer), "ramasamy" (generic name for a Tamil labourer: "We teach Ramasamy a
good deal in Ceylon", 1881). Office titles alone are 1,235 mentions, 6% of the head.

**Head variant clusters (28 clusters, 39 (b) keys, 18% of head mentions):**
- "dr. trimen" / "trimen" / "henry trimen" (805 mentions together; outside the head also "h. trimen", "dr. henry trimen", "mr. trimen" and OCR "h. h. trimen", "h. f. c. trimen", ... — 15+ keys)
- "c. drieberg" / "c. driberg" / "c. drieburg" / "drieberg" (464; plus "mr. drieberg", "mr. driemberg", "j. c. drieberg" outside)
- "e. e. green" / "green" / "e. ernest green" / "mr. green"
- "d. morris" / "morris" / "dr. morris" / "mr. morris"
- "m. kelway bamber" / "bamber" / "kelway bamber"
- "john ferguson" / "j. ferguson" / "ferguson"; "dr. watt" / "watt" / "george watt"; "thos. christy" / "t. christy" / "thomas christy"
- "j. c. willis" / "willis" / "dr. willis"; "dr. thwaites" / "thwaites"; "dr. king" / "king"; "t. petch" / "petch"
- "h. f. macmillan" / "macmillan"; "h. k. rutherford" / "rutherford"; "f. a. stockdale" / "stockdale"; "j. b. carruthers" / "carruthers"
- "m. cochran" / "cochran"; "n. k. jardine" / "jardine"; "j. h. hart" / "hart"; "malcolm park" / "m. park"; "wm. mackenzie" / "mackenzie"
- "nock" / "mr. nock"; "cross" / "mr. cross"; "e. elliott" / "elliott"; "john hughes" / "hughes"; "herbert wright" / "wright"
- "n. wickremaratne" / "n. wickramaratne" (spelling variant)
- "the governor" / "governor" / "governor of ceylon" (all (c))

**How names are normalised across the ranking.** The `norm` field is inconsistent in three independent ways, and
each produces a separate key: (1) honorific kept or dropped ("dr. trimen" 522 vs "trimen" 170; "mr. green" 99 vs
"green" 136; "mr. nock" 72 vs "nock" 154) — the surface "Trimen" sits under key "dr. trimen" and the surface
"Dr. Trimen" under "trimen", so the LLM decided per mention, not per surface; (2) initials vs full given name
("henry trimen" vs "dr. trimen"; "john ferguson" vs "j. ferguson"; "malcolm park" vs "m. park"; "thos." vs "thomas");
(3) surname-only keys (21 in the head, e.g. "wright", "ferguson", "cameron", "brown", "smith") which pool several
different men and cannot be merged into any one full name without article context. Example J. L. Shand: "j. l. shand"
148, "shand" 34, "mr. shand" 29 — but also "c. shand" 39, "p. r. shand" 27, "charles shand" 21 are different Shands,
so "shand" is unresolvable by string. Trimen spreads over 15+ keys, Drieberg over 15, Willis over 15 (incl. the
real J. J. Willis). OCR spellings in the head itself: "c. driberg", "c. drieburg", "n. wickramaratne".

**Gazetteer linkability (top 200).** 125 of 200 head keys carry initials or a given name (the rest are surname-only,
honorific+surname, or titles). Matching surname + exact initials against `planters_index.tsv` slugs gives 19 hits
(e.g. "h. k. rutherford", "w. d. gibbon", "c. e. a. dias", "t. y. wright", "h. l. de mel", "t. c. owen",
"e. b. creasy", "g. a. talbot", "j. n. campbell", "t. n. christie"); matching surname + initials-prefix against
the Colonial Office List gives 42, of which I judge about 30 plausible (Sturgess=GEORGE WILLIAM, Willis=JOHN
CHRISTOPHER, Stockdale=FRANK ARTHUR, Morris=DANIEL, Petch=TOM, Henry Trimen, W. A. de Silva=WALWIN ARNOLD,
A. M. Ferguson=ALASTAIR MACKENZIE, H. M. Fernando, E. Rodrigo, J. B. Carruthers, J. H. Hart, F. P. Jepson,
Blake, Gregory, Youngman, Denham, Lyne, C. H. Collins...; false hits come from full given names reduced to one
initial, e.g. "john hughes" -> HUGHES, J. D. W.; "marshall ward" -> WARD, Maurice). Either gazetteer: ~45 of 125
(~36%). The departmental scientists who dominate the head (Drieberg, Green, Macmillan, Holland, Joachim, Bamber,
Shand, Philip, Coombe, Molegode) are in neither list — they need Wikidata or a hand list. Note the key "dr. trimen"
matched nothing until the honorific was stripped: the honorific problem blocks linking directly.

**Bibliographic vs acting persons.** Using the top-3 roles: head 107 acting only (board members, officials,
planters, directors), 89 mixed (officials who also publish: Petch, Willis, Joachim), 4 purely "author/cited";
ranks 201-5,000: 2,989 acting, 1,613 mixed, 183 purely bibliographic. By hand, about 18 of the top 200 are
authorities cited rather than actors (Linnaeus, Roxburgh, de Candolle, Pliny, Liebig, Darwin, Pasteur, Voelcker,
Marshall Ward, von Mueller, Hooker, Gamble, Watt, Markham, Thwaites, Moens, Cochran, Howard). The PERSON head is
mostly journalistic: Ceylon Board of Agriculture members and department staff from the Proceedings.

**Middle (3-10).** 79 good. (b) 16: honorific forms of commoner keys ("dr. huber"/"huber" 14, "major forbes"/"forbes" 32,
"dr. simpson", "mr. templer", "mr. ritchie", "mr. shipley", "mr. böhringer", "mr. dickenson", "dr. livingstone",
"sir a. d. hall"/"a. d. hall" 39), spellings ("e. j. russel"/"e. j. russell" 43, "d. t. e. dissanayake"/"d. t. e.
dassanayake" 83, "mr. driemberg", "humphry davy"/"davy"), initials ("g. massee"/"massee", "h. rider haggard"/
"rider haggard"). (c) 5: "kandyan king", "governor general of netherlands india", "x.", "vedda" (pen-name), "h. j. e.".

**Tail singletons (400).** (a) 320 = 80% genuine rare people — show prize-winners, students, teachers, foreign
authors, consuls, company directors, and correctly written-out bibliographic names ("Ittner, Franciscus Georgius
Ignotius"). (b) 40 = 10%: 21 honorific-only variants of an existing key ("prof. harvey"->"harvey" 21, "dr. mackenzie",
"dr. lye"->"lye" 11, "mr. obeyesekere", "m. muntz"->"muntz" 14, "mrs. thomas mackie"->"thomas mackie" 14 — though some
"mrs." are different people), and 19 OCR/spelling corruptions: dropped/added/changed letter ("firninger" -> "firminger",
"bertand" -> "bertrand", "keuhn" -> "kuhn", "bacyer" -> Baeyer, "o. c. tillekeratna" -> "o. c. tillekeratne", "c. a.
loechman" -> "c. a. leechman", "m. trenb" -> Treub, "j. fayerer" -> Fayrer, "flammariar" -> Flammarion, "bageshawe" ->
"bagshawe", "dr. whaives" -> Thwaites, "von gogh" -> "van gogh"), abbreviation ("ed. w. keith" -> "e. w. keith" 50),
inverted order with title ("fleming c. j." = Fleming, Chief Justice). (c) 35 = 9%: 13 are lists of several people
in one key ("misses angus, hall, lucas and catton", "e. s. grigson, a. orchard, j. forbes, ...", "chapman and
glaser", "paine and williams"), 22 are titles/pen-names/initials ("financial secretary to the treasury", "rubber
visiting agent", "chairman, ceylon planters' association", "distracted", "f.s.e.", "a native proprietor",
"canganie", "shylock"). (d) 2: "carl peter thunberg (or georg wilhelm steller, likely osbeck)" (model commentary
written into the key) and "sbang-hai". (e) 3: a bull ("mr. hawkins"), a pony ("chorister"), a song ("annie lawrie").

**PERSON tail verdict: keep.** 80% of singletons are real, distinct people, and most of them occur once because they
really were mentioned once (a prize list, one letter). Only 10% are variants and half of those are fixed by honorific
stripping, not fuzzy matching. Do not cut by frequency; cut by pattern (titles, " and "/"&"/commas = lists, initials-only).

## ORG (88,690 mentions, 32,564 keys, 75.6% singletons, top 100 = 22.4%)

| slice | n | a | b | c | d | e |
|---|---|---|---|---|---|---|
| head (top 200) | 200 | 163 | 33 | 2 | 0 | 2 |
| head, by mentions | 25,930 | 76.9% | 21.0% | 1.5% | 0 | 0.5% |
| middle (3-10) | 100 | 84 | 10 | 6 | 0 | 0 |
| tail singletons | 400 | 282 | 77 | 28 | 1 | 12 |

**Head (c)/(e):** (c) "government" (#16, 348 mentions; referent varies), "the society"; (e) "surveyor-general" and
"secretary of state for the colonies" (offices/persons). The head is clean of non-entities; its problem is
fragmentation. Composition of the top 200: 80 firms/companies, 46 government bodies, 40 associations/committees/funds,
34 institutions (gardens, museums, stations, schools). 51 of the 80 companies ("kelani tea garden co., ltd.",
"colombo hotels company", "kandy hotels co., ltd.", ...) have ~70 mentions in ~70 articles, almost all 1898-1906:
they are rows of the Colombo share list repeated in every issue, so their rank measures a table, not prominence.

**Head variant clusters (24 clusters, 33 (b) keys, 21% of head mentions):**
- "department of agriculture" (1,193) / "agricultural department" (450) / "department of agriculture, ceylon" (224) — the bare key also absorbs the US, Indian and other colonial departments
- "royal botanic gardens, kew" / "kew" / "kew gardens"
- "planters' association of ceylon" / "planters' association" (751) / "ceylon planters' association"
- "royal botanic gardens, peradeniya" / "peradeniya gardens" / "royal botanic gardens, ceylon" / "peradeniya" / "royal botanic gardens" / "botanic gardens" / "botanical gardens" (7 keys, 1,486 mentions; the three generic ones are ambiguous with Kew/Singapore)
- "experiment station, peradeniya" / "peradeniya experiment station" / "experiment station"
- "government of india" / "indian government"; "madras government" / "government of madras"; "ceylon government" / "government of ceylon"; "government of bengal" / "bengal government"
- "ceylon agricultural society" / "agricultural society"; "ceylon chamber of commerce" / "chamber of commerce"; "board of agriculture" / "central board of agriculture"
- "school of agriculture" / "agricultural school"; "united states department of agriculture" / "u.s. department of agriculture"
- "rubber research scheme" / "rubber research scheme (ceylon)"; "tea research institute of ceylon" / "tea research institute"
- "ceylon association in london" / "ceylon association"; "ceylon tea fund" / "tea fund"; "estate products committee" / "estates products committee"
- "rothamsted experimental station" / "rothamsted"; "j. p. william & brothers" / "william brothers"; "colombo observatory" / "observatory"; "survey department, ceylon" / "survey department"
- "ceylon tea plantations company" / "ceylon tea plantation co., ltd."

**Company-name variants go far beyond the head.** The Ceylon Tea Plantations Company appears under at least 21
keys: "ceylon tea plantation co., ltd." 67, "ceylon tea plantations company" 65, "... company, limited" 31,
"ceylon tea plantations" 26, "... co." 20, "... co., ltd." 17, "ceylon tea plantation company" 11, "... co." 8,
"... company, ltd." 7, "the ceylon tea plantations company, limited" 5, plus 4 more spellings and 7 abbreviations
("c. t. p. co." 16, "c t p co.", "c.t.p. co.", "c. t. plantations company"...). Gow, Wilson & Stanton: 11 keys
("gow, wilson & stanton" 302, "... ltd." 18, "gow, wilson & co." 8, "gow, wilson and stanton" 3, "gow, wilson &
slanton" 1). Lewis & Peat: 5 keys ("lewis and peat" 22, "lewis & peat's ltd." 11, "lewis & peatt"). The Planters'
Association has 3 head keys plus "planters' associations" (34) and many district PAs that are correctly separate.
Abbreviations ("C.T.P. Co.", "P. A.", "R.R.S.", "C. E. P. A.", "U. P. A. S.") are sometimes expanded by the LLM
(they appear as surface forms under the full key) and sometimes kept as their own key.

**Middle (3-10).** 84 good, mostly firms, foreign departments, district associations, schools. (b) 10: suffix/article
variants ("the new dimbula company, limited", "scottish ceylon tea co.", "nahavilla estates company, limited",
"lipton limited", "lewis & peat's, ltd.", "j. p. william bros.", "p & o", "bureau of plant industry, u.s.a.",
"auerbach quinine factory"/"auerbach factory", "london ceylon association"). (c) 6: "tea industry", "railways",
"research scheme", "botanical garden", "trincomalee branch", "italian and american works" (a class of buyers).
Several companies are keyed by their estate/place name only ("neboda", "udugama", "galaha", "darjeeling" with role
"tea company") — correct in the share lists but they will collide with ESTATE/PLACE keys of the same string.

**Tail singletons (400).** (a) 282 = 70.5%: genuine rare firms, foreign institutions, village schools ("wakada b.v.s.",
"polpitigama school"), proposed syndicates. (b) 77 = 19%, the highest variant share of my five types. Of these,
about 60 differ from another key only by "the"/"Messrs."/"and" vs "&"/"Co." vs "Company" vs "Coy."/"Ltd."/"Limited"/
punctuation ("the high forests estates company limited" vs "high forests estates co., ltd." 48; "geo. stewart &
company" vs "geo. stewart & co." 24; "the scottish ceylon tea company, limited" vs "scottish ceylon tea co., ltd." 70;
"h.w. cave & co." vs "h. w. cave & co." 43; "shell transport and trading co., ltd." vs "the shell transport and
trading company, ltd." 43), and about 17 are OCR letter errors ("ruarawella" -> "ruanwella" 59, "racalla" -> "ragalla"
51, "hugh forests" -> "high forests", "agar ouyah" -> "agra ouvah", "rothampstead" -> "rothamsted", "singot" ->
"singlo", "jotai" -> "jokai", "mazawatta" -> "mazawatte", "vavassur" -> "vavasseur", "uya" -> "ouvah",
"basle mission" -> "basel mission"). (c) 28: generic plurals and classes ("ceylon rubber producing companies",
"gemming and mining companies and syndicates", "city tea companies", "savings banks", "revenue, agricultural and
irrigation departments", "german stations for agricultural experiments") and 4 lists of two or three parties
("epps, cadbury, and fry", "cosmo newbery and f. dunn"). (e) 12: ships ("s. s. bawean", "clan macdonald"), persons
or offices ("evans", "drummond deane", "assistant government agent", "inspector for plant pests and diseases,
central division", "bay of tunis" = the Bey), places ("united states", "straits and federated malay states"),
estate groups ("o. b. c. estates", "looleconda group"), a building ("chamber of commerce building"). (d) 1: "cumts tea co., ltd.".

**ORG tail verdict: keep, but only after canonicalising company suffixes; then fuzzy-merge within the same
canonical head word.** One in five ORG singletons is a variant, and most of those are mechanical (suffix/article/
ampersand). After that rule the remaining singletons are ~80% genuine.

## ESTATE (31,273 mentions, 12,984 keys, 70.4% singletons, top 100 = 10.5%)

| slice | n | a | b | c | d | e |
|---|---|---|---|---|---|---|
| head (top 200) | 200 | 174 | 16 | 0 | 0 | 10 |
| head, by mentions | 5,232 | 88.1% | 6.9% | 0 | 0 | 5.0% |
| middle (3-10) | 100 | 62 | 35 | 0 | 0 | 3 |
| tail singletons | 400 | ~187 | ~140 | 25 | 5 | 43 |

**Head.** The ESTATE head is the cleanest of my five types: real Ceylon (and some Indian, Malayan, Trinidad, Fiji,
Nyasaland) estates, almost all with role "estate"/"tea estate". It is flat (the top key "abbotsford" has 149 mentions)
because estate mentions are spread over thousands of properties. (e) 10: botanic and government gardens and farms
typed ESTATE — "hakgala gardens", "hakgala garden", "peradeniya gardens", "peradeniya", "henaratgoda gardens",
"henaratgoda garden", "badulla garden", "castleton gardens" (Jamaica), "saidapet farm" (Madras government farm),
"cinnamon gardens" (a Colombo district). The same gardens also appear as ORG ("peradeniya gardens" 227, "hakgala
gardens" 57 in ORG), so they are split across types.

**Head variant clusters (18 clusters, 16 (b) keys):** bare name vs name + "estate": "abbotsford"/"abbotsford estate",
"mariawatte"/"mariawatte estate", "culloden"/"culloden estate", "new peradeniya"/"new peradeniya estate",
"dartonfield"/"dartonfield estate", "dunedin"/"dunedin estate", "blackwater"/"blackwater estate", "st. coombs estate"/
"st. coombs", "kintyre"/"kintyre estate", "holmwood"/"holmwood estate", "blackstone"/"blackstone estate",
"franklands"/"franklands estate", "hope"/"hope estate", "yarrow estate"/"yarrow", "lauderdale"/"lauderdale estate"
(but this one mixes Lauderdale, Ceylon with Lauderdale, Mlanje); spelling: "loolecondera"/"loolecondura" (plus
"loolecondara" in the tail; Taylor's Loolecondera is under 4+ keys); gardens: "hakgala gardens"/"hakgala garden",
"henaratgoda gardens"/"henaratgoda garden". Homonym risk: 15 head estates share their string with a place
("glasgow", "aberdeen", "edinburgh", "queensland", "kelani", "gampaha", "caledonia", "mocha", "delta", "norwood",
...) and several companies are keyed by the same estate name in ORG ("galaha", "neboda"); the "estate" suffix rule
must not be applied blindly across countries ("fairfield" Ceylon vs "fairfield estate" Travancore).

**Gazetteer match (estates_index.tsv, 4,771 names).** Head: 136/200 exact on the top surface form, 133 case-insensitive
key, 140 case/space/punctuation-insensitive, **155 after stripping a trailing "estate"/"estates"/"group"**, and
about 165 when a 0.85 fuzzy match is allowed (Yattawatte->Yattewatte, Sembawatte->Sembawattie, Tallagalla->Talagalla,
Loolecondura->Loolecondera, Labookellie->Labookelle, Tangakelly->Tangakelle, Glen Alpin->Glenalpine; the index itself
has OCR-ish forms like "Chesterlord" and suffixes like "Carolina No02", "Bambragalla No 1 Midlands"). The ~35 head
keys not in the index are the 10 gardens/places above, the research estates of the 1930s ("bandirippuwa estate",
"nivitigalakele", "ratmalagara estate", "dartonfield" matched only partly), non-Ceylon estates ("river estate"
Trinidad, "alpha estate" Fiji, "stagbrook" Peermade) and some Ceylon estates missing from the index ("dessford",
"rillamulle", "kelburne", "invery", "moray", "scrubs", "glenloch"). Across all keys, 2,263 of 12,984 match after
suffix stripping (17%); middle 853/1,918 (44%); singletons 694/9,145 (8%).

**Middle (3-10).** 62 good. (b) 35 — this is where the suffix problem lives: "stagbrook estate" (8) vs "stagbrook"
(21), "fairfield estate"/"fairfield", "ardross estate"/"ardross", "narangalla estate"/"narangalla", "abbotsford
plantation"/"abbotsford" (149), "passara group"/"passara", "chandpore tea estate"/"chandpore"; and OCR one-letter
spellings "xoxford"/"yoxford" (21), "peradenia"/"peradeniya", "hoolankanda"/"hoolankande", "kandapola"/"kandapolla",
"talgaswella"/"talgaswela", "coobawn"/"coolbawn", "wattakelly"/"mattakelly". (e) 3: "poona farm", "sivagiri home farm"
(government farms), "gyantse valley" (Tibet).

**Tail singletons (400).** (a) about 187 (47%) genuine rare estates and plantations, many outside Ceylon (Java
"tjikembar", Natal "riet valley", Burma "shwegyin estate", Sylhet "eraligool tea estate"). (b) about 140 (35%) — the
highest variant share of any of my types. 82 differ from a key with 3+ mentions by suffix or one letter ("warwiek
estate" -> "warwick" 25, "larapana" -> "laxapana" 30, "loolecondara" -> "loolecondera" 41, "sembanwatte" ->
"sembawatte" 27, "craigielea" -> "craigie lea" 24, "searborough" -> "scarborough", "caillander" -> "callander",
"kenakelle" -> "keenakelle", "mdamana" -> "mudamana", "wa'erloo estate" -> "waterloo", "karagas'alawa" ->
"karagastalawa", "blackstone tea estate" -> "blackstone" 41, "theberton factory", "culloden s. division");
another ~60 pair only with another rare key, which I spot-checked at ~80% true ("thothugalla"/"thotugalla",
"ambalakanda"/"amblakanda"/"ambalakande", "pittiakande"/"pitiakande", "brazennose"/"brazenose"). Patterns:
-galla/-gala/-golla, -watte/-watta/-wattie, -kande/-kanda, -tenne/-tenna, "oya" spacing ("upper kudaoya"/"upper kuda
oya"), doubled consonants, OCR c/e, r/n, h/b, rn/m ("mabacoodagalla"/"mahacoodagalla", "kebelwatte"/"kehelwatte").
(c) 25: 11 pairs/lists ("clunes & new clunes", "arangalla and arduthie", "delta and midlands estates", "hudson or
fairfield"), 7 sale-list marks ("e.b. & co.", "s.p.s.", "b.s.", "d. k. p. c. l.", "f. s." cinnamon mark), and
generic ("indian tea estates", "tobacco estate", "demonstration farm", "economic plots"). (e) 43 = 11%: gardens,
school gardens, farms, experiment stations, mines ("plumbago mine", "champion reef"), buildings ("ceylon court",
"viceroy's residence", "belliaparah bungalow", "black store", "temperate-house" at Kew), places ("dimbulla",
"kurunegala", "goode island", "tissamabarama" a tank). (d) 5: "seed", "roller fame", "maxim", "s'liall estate", "san cio".

**ESTATE tail verdict: needs fuzzy merging before anything else; do not cut by frequency.** A third of singletons
are spelling variants of other estates, so frequency is a poor proxy for reality here (many real estates are only
seen once per spelling). Merge by (1) suffix strip, (2) Sinhala-suffix-aware edit distance 1 within a gazetteer
anchor, then keep everything that links to `estates_index.tsv` or has a district context; move gardens/farms/stations
to ORG and places to PLACE.

## PUBLICATION (59,706 mentions, 15,325 keys, 77.5% singletons, top 100 = 43.9%)

| slice | n | a | b | c | d | e |
|---|---|---|---|---|---|---|
| head (top 200) | 200 | 159 | 39 | 2 | 0 | 0 |
| head, by mentions | 30,887 | 80.7% | 18.8% | 0.5% | 0 | 0 |
| middle (3-10) | 100 | 79 | 13 | 7 | 0 | 1 |
| tail singletons | 400 | 300 | 61 | 29 | 2 | 8 |

**Head.** Almost entirely periodicals (about 160 of 200 by role; 4 books: "flora of british india", "treasury of
botany", "flora of ceylon", "encyclopædia britannica", plus "british pharmacopoeia"). This is the scissors-and-paste
journal's source line ("—*Madras Mail*.", "—*H. & C. Mail*."). The journal cites itself: "the tropical agriculturist"
2,550 + "tropical agriculturist" 1,505 = 4,055 mentions, 6.8% of all PUBLICATION mentions. (c) 2: "monthly bulletin",
"bulletin". Nothing wrongly typed in the head.

**Head variant clusters (32 clusters, 39 (b) keys, 19% of head mentions):**
- "the tropical agriculturist" / "tropical agriculturist" (plus outside: "t. a.", "t.a.", "trop. agric." — which also abbreviates *Tropical Agriculture*, Trinidad —, "ceylon tropical agriculturist", "the tropical agriculturist monthly", "tropical agriculturist and magazine of the ceylon agricultural society" 21, "the supplement to the tropical agriculturist ..." 12)
- "ceylon observer" (1,058) / "observer" (561) (outside: "colombo observer" 13, "weekly observer" 14, "the ceylon observer", "weekly ceylon observer", "ceylon overland observer", "overland ceylon observer" 10; and the bare "observer" also catches the London, Adelaide and South of India *Observer*)
- "madras mail" (801) / "m. mail" (329) (+ "m mail" 17, "the madras mail"); but "M. Mail" is also a surface form of "malay mail"
- "h. and c. mail" (492) / "h. & c. mail" (317) / "home and colonial mail" (313) / "h and c mail" (38): one paper under 4 head keys, 1,160 mentions
- "london times" / "times" / "the times" (1,065 mentions; bare "times" also = *Times of Ceylon*); "times of ceylon" / "local times"
- "gardeners' chronicle" (1,357) / "gardener's chronicle" (138) / "the gardeners' chronicle" (44) (outside: "gardeners chronicle", "gardeners’ chronicle", "the gardener's chronicle", "gardens' chronicle", "gardiners' chronicle", "gardner's chronicle", "gardners' chronicle" — 10+ keys)
- "kew bulletin" (403) / "bulletin of miscellaneous information" (47) (outside: "kew bulletin of miscellaneous information" 14, "kew bull.", "the kew bulletin", "royal gardens kew bulletin", "r.b.g. kew bulletin of miscellaneous information")
- "l. & c. express" / "l. and c. express" / "london and china express"; "madras times" / "m. times"; "singapore free press" / "s. f. press"
- "englishman" / "calcutta englishman" / "the englishman"; "indian gardening and planting" / "indian planting and gardening" / "indian gardening"
- "field" / "the field"; "grocer" / "the grocer"; "lancet" / "the lancet"; "the planter" / "planter"; "india rubber world" / "the india rubber world"; "india rubber journal" / "india-rubber journal"
- "bulletin of the imperial institute" / "imperial institute bulletin"; "journal of the society of arts" / "journal of the royal society of arts"; "produce markets' review" / "produce markets review"
- "agricultural gazette of new south wales" / "agricultural gazette"; "government gazette" / "gazette"; "ceylon independent" / "independent"; "melbourne argus" / "argus"; "british north borneo herald" / "north borneo herald"
- "agricultural magazine" / "the agricultural magazine, colombo"; "ceylon handbook and directory" / "handbook and directory"; "overland mail" / "o. mail"; "overland observer" / "overland"; "indian planters' gazette" / "planters' gazette"

Abbreviation clusters are only partly expanded by the LLM: "M. Mail", "H. & C. Mail", "L. & C. Express", "S. F. Press",
"M. Times", "O. Mail" survive as keys; "C.O." and "Gard. Chron." were expanded (they appear as surface forms under
the full key). Ambiguous abbreviations need context: "M. Mail" (Madras/Malay), "Ind. Merc." (*Indian Mercury* vs
*Indische Mercuur* — the middle sample has "indische mercantiele", a wrong expansion), "Ind. Agric." (*Indian
Agriculturist* vs *Indian Agriculture*), "Trop. Agric." (*Tropical Agriculturist* vs *Tropical Agriculture*).

**Middle (3-10).** 79 good: ~62 periodicals (many foreign: "siècle", "gartenflora", "der pflanze", "apotheker zeitung")
and ~17 books ("elements of agricultural chemistry", "hortus americanus", "mahavansa", "among the indians of guiana").
No article titles in the sample. (b) 13: "the statesman"/"statesman", "colonies & india"/"colonies and india",
"produce market's review", "indigo planter's gazette", "bradstreet"/"bradstreet's", "borneo herald", "free press",
"trop. agric.", "expt. stn. record", "ind. merc." and "indische mercantiele", "agricultural bulletin of the f. m. s."
vs "... f.m.s.", "indian tea planters' gazette". (c) 7: "the magazine", "journal of the society", "society's magazine",
"tamil edition", "blue books", "american paper", "straits paper". (e) 1: "penal code".

**Tail singletons (400).** (a) 300 = 75%: by role about 35-40% periodicals, 25% books (many 17th-19th c. tea and
coffee titles: "tractaat van het excellente kruyd thee", "nützliche und vollständige abhandlung vom coffee"),
20% reports/bulletins/circulars, 5-8% article or paper titles ("some studies on tobacco diseases in ceylon—iv. the
economics...", "retaining flavour and vitamin content in fruit juices", "coffee in costa rica"). (b) 61 = 15%:
article/punctuation ("the daily mail" -> "daily mail" 48, "planter & farmer" -> "planter and farmer" 75, "the
producers' review"), OCR ("scotman" -> "scotsman" 33, "nilyiri express" -> "nilgiri express" 32, "the planters'
cronicle", "l and g express" for L. & C. Express, "m. marl" for M. Mail, "the thundal agriculturist"),
abbreviation vs full ("agric. jour. india", "bull. d. of a., jamaica", "der pfl.", "chem. zeit.", "brit. ass.
report", "empire cotton gr. rev."), word order/inversion ("druggist and chemist" for *Chemist and Druggist*,
"indian forester, records"), subtitle/edition ("ceylon weekly observer", "albany cultivator and country gentleman").
(c) 29: numbered series without a publisher ("bulletin no. 11", "bulletin no. 106", "circular 21", "report xxvii.",
"annual report for 1910-11", "special bulletin 77"), in-text citations ("park and fernando, 1937a", "cochran, 1950",
"hoblyn (1931)", "marloth 1938", "bentley and trimen"), generic ("observers", "magazines", "provincial press",
"manchester papers", "the blue book", "literary supplement"), a list of three journals. (e) 8: laws and legal
cases ("italian penal code", "plant quarantine act", "rubber restriction ordinance", "c. r. balapitiya no. 31,086",
"re van duzer's trade-mark"), a person ("heydt"). (d) 2: "d. t.", "modern mod.".

**PUBLICATION tail verdict: keep, with canonicalisation; tag sub-kind.** 75% of singletons are real and many are
the most interesting bibliographic items in the corpus (early tea literature). Variants (15%) are mostly fixed by
article/ampersand/punctuation normalisation plus an abbreviation table for ~40 source-line papers. The KG should
separate periodicals from books/reports (role field already says "newspaper"/"journal"/"book"/"report"); numbered
bulletins without a publisher and author-year citations should stay as raw mentions.

## EVENT (6,189 mentions, 3,530 keys, 81.0% singletons, top 100 = 29.0%)

| slice | n | a | b | c | d | e |
|---|---|---|---|---|---|---|
| head (top 200) | 200 | 90 | 52 | 9 | 0 | 49 |
| head, by mentions | 2,264 | 55.0% | 18.9% | 7.6% | 0 | 18.6% |
| middle (3-10) | 100 | 36 | 26 | 5 | 0 | 33 |
| tail singletons | 400 | ~187 | ~48 | ~25 | 1 | ~139 |

(Only 267 EVENT keys have 3-10 mentions, so the middle sample overlaps the lower head.)

**EVENT is a catch-all.** The prompt defines EVENT as "named exhibitions, conferences, shows, wars"; laws,
diseases, seasons and schemes had no type, and the model put them here. Head (e) 49 keys, 19% of head mentions:
cultivation seasons ("yala season", "maha season", "maha", "yala", "maha crop", "yala crop" — 108 mentions);
22 laws/bills/agreements ("merchandise marks act", "tea act", "act v of 1888", "mckinley tariff", "food and drugs
act", "plant protection ordinance", "pests ordinance", "assam labour bill", "brussels convention", "cinchona
agreement", ...); 9 diseases ("malaria", "rinderpest", "cholera", "beri-beri", "panama disease", "coffee leaf
disease", "foot-and-mouth disease", "murrain", "brown bast"); monsoons; "ceylon court" (an exhibition building);
"panama canal"; "coconut research scheme", "rubber research scheme" (ORG); "karachi scheme", "internal purchase
scheme"; "mendel's law"; "rajakariya" (a labour system); "new avenue rubber manurial experiment", "rothamsted
experiments". (c) 9: "exhibition" (69), "the exhibition", "exposition", "conference", "agricultural show",
"agricultural shows", "agri-horticultural shows", "international exhibition", "agricultural conference".

**Head variant clusters (32 clusters, 52 (b) keys).** Exhibitions are named a dozen ways. The Chicago World's
Columbian Exposition of 1893 has 11 head keys: "chicago exhibition" 137, "world's fair" 39, "world's columbian
exposition" 19, "chicago exposition" 17, "world's columbian exhibition" 13, "chicago world's fair" 6, "columbian
exposition" 6, "chicago exhibition of 1893" 5, "world's exposition at chicago in 1893" 5, "world's fair at
chicago" 5, "chicago fair" 4 (plus "world's fair in chicago in 1893", "great world's fair at chicago" in the tail).
The 1886 Colonial and Indian Exhibition has 9: "colonial and indian exhibition" 94, "indian and colonial
exhibition" 29, "colonial exhibition" 28, "colonial and indian exhibition of 1886" 11, "... , 1886" 6,
"indo-colonial exhibition" 6, "colinderies" 4, "... at south kensington" 4, "indian and colonial exhibition of
1886" 4 (tail adds "colind", "india and colonial exhibition", "indian and colonial exhibition of 1887"). Others:
Melbourne 1880-81 (5 keys), St Louis 1904 ("st. louis exhibition"/"st. louis exposition"/"louisiana purchase
exposition"), Great Exhibition 1851 (3), Atlanta 1895 (3), Kandy show (3), Nuwara Eliya show (2), World War I
("world war i"/"great war"/"world war"/"european war"), "american civil war"/"civil war", "crimean war"/"russian
war", "franco-prussian war"/"franco-german war", "paris exhibition of 1900"/"paris exposition of 1900", and
"paris exhibition" (118) which mixes 1878, 1889 and 1900. Merged, the 200 head keys become ~148 events and
non-events; the actual distinct named events in the head are about 90.

**Middle (3-10).** 36 good, 26 variants (same exhibitions under other names: "columbian exposition", "louisiana
purchase exposition", "centennial exposition", "boer war"/"south african war", "imperial agricultural research
conference, 1927"), 33 not events (laws: "abkari act", "act i of 1882", "dingley bill", "treaty of tientsin",
"soil conservation ordinance"; diseases; "stevenson scheme", "tungabhadra project", "schimmel's test", "yala
season 1929", "ceylon tea court"), 5 generic ("exposition", "agricultural exhibition", "pax britannica").

**Tail singletons (400).** (a) ~187 (47%): local shows and prize competitions ("handapangoda garden competition",
"kurunegala paddy weeding competition", "danowita village show"), conferences, expeditions ("bligh expedition",
"german loango expedition"), wars and crises ("baring crisis", "south sea bubble", "boxer rebellion"), festivals
("deepavali", "muharram", "kartighi", "posadas"). (b) ~48 (12%): more exhibition aliases (see above), "spanish
american war", "sino-japanese war"/"china-japan war", "dutch-aceh war"/"acheen war", "indian rebellion of 1857"/
"indian mutiny", "civil war in the united states", year-qualified forms ("rubber exhibition, 1914", "1906 ceylon
exhibition", "jamaica exhibition of 1891"), OCR ("nuwera eliya", "colind", "otoloual exhibition"). (c) ~25:
plural/generic ("village shows", "exhibitions", "london exhibitions", "all-island agricultural shows", "philippine
expositions"), lists ("chicago and san francisco expositions", "exhibitions of 1851 and 1862"), unresolvable
("eleventh ordinary general meeting", "exhibition of 26th october", "exhibition year"). (e) ~139 = 35%: about 57
laws, ordinances, bills, taxes and treaties ("gaming ordinance", "currency act", "act viii 1878", "lacey game act",
"ordinance no. 4 of 1882", "kerosine oil tax"), 11 legal cases ("huddart v. grimshaw", "sellers v. dickinson",
"jackson v. kerr", "citronella oil case"), 11 diseases ("leaf curl", "grey blight", "bud rot", "texas fever",
"bunchy top"), 14 seasons/months/periods ("yala 1927", "maha season 1922-23", "kuda mosama", "february",
"liang dynasty", "silurian formations"), 14 schemes/projects ("amban-ganga scheme", "hydro-electric scheme",
"tavoy siam road"), 4 ships ("telamon", "s.s. vadala", "quetta", "adee letchimy"), labour/cultivation systems
("andè", "tundu system", "attam", "hen"), buildings/markets ("cleopatra's needle", "palace of engineering",
"coronation market"), and odds ("k.m.o.", "student's method", "mineral theory", "jennings-dibbism"). (d) 1: "new south".

**EVENT tail verdict: re-type first, then keep.** A third of EVENT singletons are another kind of thing; the
legal ones (acts, ordinances, cases: ~17% of singletons, ~11% of head keys) deserve their own LAW type because
they are useful for the history the journal records. After removing those, the remainder is about 75% genuine
and small enough (≈2,300 keys) for a hand-built alias table of the ~40 big exhibitions/conferences/wars, which
covers most of the head mentions.

## Cross-type summary

| type | head a/b/c/d/e | head mentions in (b) | middle a/b/c/d/e | tail singletons a/b/c/d/e | singletons genuine |
|---|---|---|---|---|---|
| PERSON | 151/39/10/0/0 | 18.2% | 79/16/5/0/0 | 320/40/35/2/3 | 80% |
| ORG | 163/33/2/0/2 | 21.0% | 84/10/6/0/0 | 282/77/28/1/12 | 70% |
| ESTATE | 174/16/0/0/10 | 6.9% | 62/35/0/0/3 | ~187/~140/25/5/43 | ~47% |
| PUBLICATION | 159/39/2/0/0 | 18.8% | 79/13/7/0/1 | 300/61/29/2/8 | 75% |
| EVENT | 90/52/9/0/49 | 18.9% | 36/26/5/0/33 | ~187/~48/~25/1/~139 | ~47% |

The heads are clean of OCR garbage (0 of 1,000 head keys are (d)) and, except EVENT, almost free of wrong types; their
problem is that one entity is spread over several keys. The tails are mostly real entities except where the type
definition invited something else (EVENT) or where spelling varies by nature (ESTATE).

## Normalisation rules, tested on the full rankings

Numbers are distinct keys before -> after, applied cumulatively to every key of the type (python over the TSVs;
scripts in the session scratchpad). "Mentions in merged groups" = mentions whose key now shares a group with
at least one other key.

**PERSON (59,371 keys)**
| rule | exact operation | keys after | merged away | mentions in merged groups |
|---|---|---|---|---|
| P0 filters (not merges) | drop/re-type: title-only key `^(the \|his excellency \|h. e. )?(acting\|deputy\|assistant\|chief\|...)*(director\|governor\|secretary\|chairman\|president\|superintendent\|commissioner\|conservator\|minister\|chancellor\|controller\|registrar\|inspector\|consul\|editor\|curator\|viceroy\|...)( (of\|for\|to\|in\|at) .*)?$`; lists (` and `, ` & `, `, x.`); initials-only `^([a-z]\.\s?){1,5}$` | — | 593 title keys (2,618 mentions); 1,427 list keys (1,832; includes some titles and firms like "a. m. & j. ferguson"); 874 initials-only (2,047) | — |
| P1 strip honorific, only if a given name/initial remains | remove leading `(the )?(mr\|dr\|doctor\|prof\|professor\|sir\|rev\|col\|colonel\|major\|capt\|captain\|lieut\|hon\|hon'ble\|right hon\|herr\|mons\|monsieur\|signor\|senor\|baron\|count\|gate mudaliyar\|mudaliyar\|muhandiram\|consul\|governor\|commissioner\|inspector\|his excellency\|h. e.)\.?\s+` (repeat) and trailing `, esq./c.m.g./m.a./b.sc./f.l.s./f.r.s./m.r.c.v.s./c.c.s./j.p./c.i.e./m.p./bart.`; keep "mrs.", "miss", "lady" | 58,063 | 1,308 | 18,625 (12.4%) |
| P2 initials spacing | `\b([a-z])\.(?=[a-z])` -> `\1. `; bare single letters before the surname get a period | P1+P2: 57,803 | +260 | 21,222 (14.1%) |
| P3 inverted bibliographic form | `^(surname), (i. i.)$` -> `i. i. surname` | P1-P3: 57,795 | +8 | 21,356 (14.2%) |
| P4 given-name abbreviations | wm.->william, thos.->thomas, chas.->charles, geo.->george, jas.->james, jno.->john, jos.->joseph, robt.->robert, alex.->alexander, hy.->henry ... | P1-P4: 57,446 | 1,925 total | 24,240 (16.1%) |
| P5 surname-only pool (not identity!) | also strip the honorific when only a surname remains ("mr. green", "dr. trimen" -> "green", "trimen") | 53,763 | 5,608 | 56,751 (37.6%) |
| P6 initials key (candidate generation only) | reduce given names to initials ("henry trimen" -> "h. trimen") | 48,766 | 10,605 | 81,056 (53.8%) — over-merges ("w. smith" = Worthington/Wilson/William Smith) |

P1-P4 are safe string merges (1,925 keys, 16% of mentions). P5 is the single largest effect but it pools different
men: "captain brown", "dr. brown", "professor brown" all become "brown". After P0-P4 there remain 12,363
surname-only keys carrying **48,561 mentions = 32% of all PERSON mentions**; they can only be resolved by
within-article coreference to a full-name mention ("Mr. Shand" -> the "J. L. Shand" earlier in the same article)
or by role + date against the gazetteers. P6 should be used only as a blocking key for linking, never as a merge.

**ORG (32,564 keys)**
| rule | exact operation | keys after | merged away | mentions in merged groups |
|---|---|---|---|---|
| O1 company canonical form | strip leading `the`/`messrs.`; ` and ` -> ` & `; `\b(company\|coy\.?\|co)\b\.?` -> `co.`; delete `[, ]*(limited\|ltd\|ld)\.?`; `h.w.` -> `h. w.`; normalise commas/space; `'s` -> `s` | 29,646 | 2,918 (9.0%) | 23,256 (26.2%) |
| O2 government word order | `government of X` -> `X government` | 29,613 | +33 | 25,091 (28.3%) |
| O3 drop parenthetical | delete `\s*\([^)]*\)` ("rubber research scheme (ceylon)", "dunedin (ctpco.)") | 29,421 | +192 | 28,285 (31.9%) |

O1 collapses e.g. "eastern produce and estates company" / "... co., ltd." / "... & estates co. ltd." / "... company,
limited" into one key, and the Ceylon Tea Plantations Company from 21 keys to 3 ("ceylon tea plantations co." 154
mentions in 11 former keys, "ceylon tea plantation co." 96 in 8, plus share-class forms "(ordinary)"/"(preferred)").
Still needed after O1-O3: singular/plural ("plantation"/"plantations"), "X" vs "X co.", acronym table ("c. t. p. co.",
"p. a.", "c. e. p. a.", "r. r. s.", "u. p. a. s."), a hand alias table for the ~25 government/institution clusters
in the head (Department of Agriculture, Peradeniya gardens, Kew, Planters' Association), and generic-plural filter
(`(companies\|associations\|banks\|departments\|stations\|societies\|syndicates)$` with no proper name).

**ESTATE (12,984 keys)**
| rule | exact operation | keys after | merged away | mentions in merged groups |
|---|---|---|---|---|
| E1 suffix | strip leading `the`; strip trailing ` (tea\|coffee\|rubber )?estate(s)?`, ` est.`, ` plantation(s)`, ` group`, ` division` | 11,257 | 1,727 (13.3%) | 16,030 (51.3%) |
| E2 squash | remove spaces, hyphens, apostrophes ("craigie lea"/"craigielea", "kandalo-oya") | 10,892 | +365 | 17,126 (54.8%) |
| E3 Sinhala orthography (blocking key, not identity) | `-(watta\|wattie\|wattee\|watty)$` -> `-watte`; `-kanda$` -> `-kande`; `-tenna$` -> `-tenne`; `-(golla\|gala)$` -> `-galla`; collapse doubled letters | 10,297 | +595 | 18,824 (60.2%) |

E1 is the most productive single rule of all five types (13% of keys, half of all mentions touched). But E1 also
merges places with estates ("haputale"/"haputale estates"/"haputale group") and generic "cinchona plantation" with
"cinchona", so it must be applied together with a type filter (key is a PLACE head or a commodity word -> not an
estate). E3 makes good blocking keys ("warriapolla"/"wariapolla"/"warriapola"/"wariapola estate"/"waria-pola";
"udapolla"/"uda-pola estate"/"udapola") but needs a gazetteer anchor or human check before merging; it also lumps
sale-list marks ("k. a. w."/"kaw"). After E1+E2, 1,360 keys match `estates_index.tsv` and they carry 13,542 of
31,273 mentions (43%); 2,255 unmatched keys have 2+ mentions; 7,277 unmatched are singletons.

**PUBLICATION (15,325 keys)**
| rule | exact operation | keys after | merged away | mentions in merged groups |
|---|---|---|---|---|
| U1 punctuation | strip leading `the`/`a`; `&` -> `and`; remove apostrophes (`gardeners'`, `gardener's`, `gardeners’` -> `gardeners`); all other punctuation -> space | 14,377 | 948 (6.2%) | 31,742 (53.2%) |
| U2 alias table (25 entries) | `m mail`->madras mail; `h and c mail`->home and colonial mail; `l and c express`->london and china express; `s f press`->singapore free press; `m times`->madras times; `o mail`->overland mail; `t a`->tropical agriculturist; `kew bull`/`bulletin of miscellaneous information`->kew bulletin; `observer`/`colombo observer`/`c o`->ceylon observer; `london times`->times; `local times`->times of ceylon; `druggist and chemist`->chemist and druggist; `gard*s chronicle`->gardeners chronicle ... | 14,355 | +22 keys | 32,785 (54.9%) |

U1 is cheap and covers half of all PUBLICATION mentions (the source-line papers are where punctuation varies most:
"h. and c. mail"/"h. & c. mail"/"h and c mail"/"h & c mail"/"h and c. mail"/"h. & c mail" -> one). U2 adds few
keys but over 1,000 mentions; "observer" -> ceylon observer and "times" handling are judgement calls (the bare
"observer" also means London/Adelaide papers), so condition U2 on the article's place/date or accept ~10% error.
Filter: `^(bulletin\|circular\|report\|leaflet)( no\.?)? ?\d+` without a publisher, and author-year citations
`^[a-z' ]+,? \(?(1[89]\d\d)[a-z]?\)?$`, stay as raw mentions.

**EVENT (3,530 keys)**
| rule | exact operation | keys after | merged away | mentions in merged groups |
|---|---|---|---|---|
| V0 re-type (filter) | law/legal: `\b(act\|acts\|ordinance\|bill\|enactment\|ordonnantie\|regulation\|order\|ukase\|treaty\|convention\|tariff\|tax\|cess\|duty\|law\|rules\|code)\b\|\bv\. \|\bcase\b`; seasons: `^(yala\|maha\|kuda mosama\|sirupokam\|kalawellamai)\b\|monsoon`; diseases: reuse the TAXON/disease list | — | law/legal 575 keys (16%), 790 mentions; season 54 keys, 189 mentions | — |
| V1 punctuation | strip `the`; `exposition` -> `exhibition`; punctuation -> space | 3,435 | 95 | 1,080 (17.5%) |
| V2 strip trailing year | ` (of \|in )?(18\|19)\d\d` at end | 3,178 | +257 | 2,083 (33.7%) — but wrongly merges the Paris 1878/1889/1900 exhibitions; use only with a city+year alias table |

For EVENT the string rules do little; the real gain is an alias table of ~40 named events (Chicago 1893 = 13 keys,
Colonial and Indian 1886 = 12 keys, Melbourne 1880-81, Paris 1878/1889/1900, St Louis 1904, Great Exhibition 1851,
WWI, Boer War, ...), keyed by city + year, that resolves bare forms using the article year.

## Recommended thresholds: knowledge graph node vs raw mention

| type | becomes a KG node when | stays a raw mention | rough size |
|---|---|---|---|
| PERSON | after P0-P4, the key has a given name or initial(s) + surname, and (links to planters index / Colonial Office List / Wikidata, or occurs in 2+ articles, or has a non-empty role). Surname-only keys become nodes only after within-article coreference to a full name. | title-only, lists, initials-only, unresolved surname-only (32% of mentions) | 38,626 named keys (95,835 mentions); 10,255 with 2+ mentions |
| ORG | after O1-O3, any key that is not generic/plural; singletons kept (70% genuine, ~80% after O1) | generic ("government", "the society", plurals), offices, ships | ~29,400 keys before alias table |
| ESTATE | after E1-E2, links to estates_index (exact or E3/edit-distance-1 + same district), or 2+ mentions with an estate role; non-Ceylon estates kept if role gives a country | gardens/farms/stations (move to ORG), places, sale marks, pairs | 1,360 linked keys (43% of mentions) + up to 2,255 unlinked with 2+ |
| PUBLICATION | periodicals: every key after U1-U2; books/reports: title of 2+ words with a role "book"/"report"/"work" | numbered bulletins without publisher, author-year citations, generic plurals, laws | ~14,000 |
| EVENT | after V0 re-typing and the alias table: named exhibitions, conferences, shows, competitions, wars, expeditions, festivals, at any frequency | generic ("exhibition", "conference"), laws -> new LAW type, seasons, diseases -> DISEASE/TAXON | ~2,300 after re-typing |

A plain frequency threshold is the wrong tool for these five types: it would cut 70-81% of keys, of which most
are real (PERSON 80%, PUBLICATION 75%, ORG 70% genuine singletons) and the junk that does exist is pattern-shaped
(titles, lists, initials, laws, gardens) rather than rare. Where a threshold is wanted for a first KG release,
use "2+ articles OR gazetteer link" — this keeps the head and everything linkable, and leaves the rest in the
mention table for later linking.

## Notes for the extraction prompt (if re-run)
- ESTATE definition says "named plantation estates and gardens" — that is why botanic gardens land in ESTATE;
  drop "and gardens" and say government/botanic gardens are ORG.
- EVENT needs explicit exclusions (laws, legal cases, seasons, diseases, schemes) or a LAW type.
- `norm` should never contain an honorific; put it in a separate field. Should keep initials exactly as printed
  ("J. L. Shand"), and expand known source-line abbreviations ("M. Mail" -> "Madras Mail") only when unambiguous.

## Summary (15 lines)
1. 1,000 head keys classified (top 200 x 5 types): 0 OCR garbage; wrong type only in EVENT (49) and ESTATE (10 gardens/farms); ORG 2.
2. Head fragmentation is the main head problem: 39/33/16/39/52 (b) keys in PERSON/ORG/ESTATE/PUBLICATION/EVENT, 7-21% of head mentions.
3. PERSON head: 10 title-only keys ("director of agriculture" #2, 400 mentions); Trimen is spread over 15+ keys, Drieberg 15, Willis 15.
4. 32% of all PERSON mentions sit on surname-only keys (12,363 keys) — resolvable only by in-article coreference.
5. ~45 of the 125 named head persons hit the planters index (19) or Colonial Office List (~30 plausible); the department scientists are in neither.
6. Singletons genuine: PERSON 80%, PUBLICATION 75%, ORG 70%, ESTATE ~47%, EVENT ~47% — keep tails; do not cut by frequency.
7. Singleton variants: ORG 19% (mostly suffix/ampersand), ESTATE ~35% (suffix + Sinhala spelling + OCR), PUBLICATION 15%, PERSON 10%, EVENT 12%.
8. EVENT is a catch-all: 35% of singletons and 19% of head mentions are laws, legal cases, diseases, seasons, schemes or ships; 575 keys match a law regex.
9. ESTATE head: 155/200 match estates_index after suffix strip, ~165 with fuzzy; corpus-wide 1,360 linked keys = 43% of estate mentions.
10. ORG head: 51 of 80 companies are 1898-1906 Colombo share-list rows (~70 mentions each), so ORG rank partly measures a table.
11. PUBLICATION head is ~160 periodicals; the journal cites itself 4,055 times; H. & C. Mail is 4 head keys, Gardeners' Chronicle 10+ keys.
12. Rule test, keys merged: ESTATE suffix+squash 2,092 (16%); ORG company canon 2,918 (9%); PERSON safe honorific+initials 1,925 (3%); PUBLICATION punctuation 948 (6%), touching 51-55% of ESTATE/PUBLICATION mentions.
13. Top rule 1 — ESTATE: strip "the" and trailing "estate/estates/plantation/group/division", then squash spaces/hyphens, then link to estates_index (with PLACE/commodity filter).
14. Top rule 2 — ORG: the/Messrs removed, and->&, Company/Coy./Co -> "co.", drop Ltd/Limited, punctuation; then acronym + institution alias tables.
15. Top rule 3 — PERSON: honorific to a separate field and strip it only when initials/given name remain; space initials; expand Wm./Thos./Geo.; filter titles/lists/initials-only; never merge surname-only keys by string.
