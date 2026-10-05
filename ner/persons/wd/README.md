# Stage 4, tier 1: Wikidata grounding of person profiles

`ground_wikidata.py` grounds the tranche of profiles with ≥10 mentions (1,860) through the WikidataMCP server.
It does not use the REST `wbsearchentities` API. `mcp_client.py` is a minimal JSON-RPC client for
`https://wd-mcp.wmcloud.org/mcp`. The public `/tool/search_items` HTTP endpoint returned HTTP 429 after a few
calls; the MCP endpoint runs at about 1.7 s per call, with 3 workers.

1. **Find candidates (vector search only).** Each profile gets three `search_items` queries: name + its top
   two occupation words (drawn from its roles), and name alone. For example: "J. C. Willis botanist" /
   "J. C. Willis". Long phrases with "Ceylon" pull in places and journals; initials alone fail.
2. **Read statements.** Candidates whose label contains the surname are read with SPARQL: label, aliases,
   human?, birth/death year, occupations, sex. SPARQL never finds candidates.
3. **Checks.**
   - Name: the profile's commonest printed form must fit the label or an alias. A full given name that
     contradicts it rejects the candidate. A middle-name-only match is weak.
   - Birth: no more than 10% of the profile's mentions may fall before the candidate turned 15.
   - Death: a candidate who died before most mentions stays a candidate but can't be auto-linked, unless
     the profile is mostly citations of an author. Death more than 60 years before the median mention
     rejects the candidate.
   - Sex must agree with the honorifics.
   - Occupation: the description or occupations must share a specific class with the profile's roles.
4. **Decide.** `auto` = exactly one passing candidate with a specific occupation match, a strong name
   match and known dates. `review` = candidates pass but the evidence is weaker or split. `none` = no
   candidate passes.

Outputs: `out/links.tsv` (one row per profile) and `out/candidates.jsonl` (every scored candidate).
`cache/search.jsonl` and `cache/entities_v3.jsonl` make reruns free (v1/v2 caches were mis-parsed and are
unused).

Result (2026-10-05): auto 199, review 552, none 1,109. Two random samples of 40 auto links were checked by
eye while the rules were tightened: 35/40, then 38/40. Each error class found was fixed:
- bare-surname alias;
- one stray "Capt." counted as occupation evidence;
- the journal's name read as agriculture evidence;
- "farmer" read as agriculture;
- "Veterinary Surgeon" read as physician;
- "academic administrator" read as colonial administrator;
- the Robert/Richard Cross alias;
- a dead governor rejected in favour of a namesake (Sir William Gregory).

The gold set (`../gold/`) measures precision properly.

`adjudication/`: review profiles plus "none" profiles with ≥50 mentions (690), split into two batches for
model adjudication. The model may run its own MCP searches and must verify statements before linking.
Results go to `out_A.tsv` / `out_B.tsv`.

## Tier 2: Colonial Office List KG (`../colist/match_colist.py`)

All named profiles with ≥3 mentions (6,716) are matched against `~/col_matching/data/kg/graph_stage3`
(persons + career_events). A CO List person is a candidate when:
- the surname matches and the given names are compatible, with no contradicting full name;
- the listed career overlaps the profile's core mention years (10th–90th percentile, ±5);
- there is a Ceylon posting, or a posting in a non-generic place the profile co-occurs with.

`auto` needs exactly one candidate, a shared specific role word (agriculture, botanic, analyst, government
agent…; generic words such as director/public/service don't count), and a CO record with at least as many
given names as the profile. Result: auto 314, review 167. A sample of 30 auto links had one error before the
last rule (J. F. Anderson → John Anderson, Governor). Agreement with tier 1: in all 16 profiles where both
tiers auto-link and the CO record has a QID, the QIDs are the same. The KG also supplies 48 QIDs where
tier 1 was review/none (Daniel Morris, Sir William Henry Gregory, E. B. Denham…).

## Tier 3: planters registry (`../planters/match_planters.py`)

historyofceylontea.com registry ids only (no content). The slug is the registry's only evidence, so the
rule is strict:
- same surname and the exact initials sequence;
- no contradicting full name ("James" vs slug "john");
- the profile's own roles say planter/estate/manager-of/visiting agent in ≥2 mentions (co-occurring
  estates are not evidence);
- active 1866–1935;
- exactly one id fits.

Result: link 157, review 142 (several ids fit, often duplicate registry records).

## Merge (`../combine.py`) → `../out/persons.tsv`

One row per profile:
- minted persistent id `TAP-P-nnnnnn` (registry `../ids/registry.tsv`; on rebuild a profile inherits the id
  of the registered profile with the most article overlap, Jaccard ≥ 0.5);
- Wikidata QID with its source and confidence (adjudicated > wd_auto > colist_kg);
- CO List person id, planter id/URL;
- flags for any source disagreement.
