#!/usr/bin/env python3
"""
Open entity extraction over articles with an OpenAI-compatible vLLM server (hybrid NER, stage 1).
Each article is split into chunks of <= CHUNK_WORDS words at paragraph boundaries; the model returns a
JSON array of mentions per chunk. Thinking is disabled (Qwen3.x reasons by default; see
label_headings.py). Output: one line per article {id, mentions:[{text,type,norm,role,chunk}], chunks,
seconds, errors}. Resumable: article ids already in --out are skipped.
Usage: extract_entities.py --base-url URL --model NAME --in articles.jsonl --out mentions.jsonl [--parallel 16]
"""
import argparse, json, re, sys, time, urllib.request, concurrent.futures as cf
CHUNK_WORDS = 2500
TYPES = ["PERSON", "GROUP", "ORG", "ESTATE", "PLACE", "PUBLICATION", "TAXON", "COMMODITY", "PRODUCT", "EVENT"]
TABLE_CHUNK_WORDS = 700          # table-heavy text yields many mentions per word; keep the JSON answer small
SYSTEM = """You extract named entities from articles in The Tropical Agriculturist (Colombo, 1881-1945), a planting and
agricultural journal that reprinted material from across the tropical world. The text is OCR of 19th/20th-century
print: capitals are common, names are often initials + surname, and OCR errors occur (keep the text as printed).
Return a JSON array, one object per distinct entity mentioned in the chunk, with these fields:
  "text": the entity as it appears (one representative surface form, as printed)
  "type": one of PERSON, GROUP, ORG, ESTATE, PLACE, PUBLICATION, TAXON, COMMODITY, PRODUCT, EVENT
  "norm": a normalised name (e.g. "W. Ferguson" for "MR. W. FERGUSON"; "Gow, Wilson & Stanton" for "Messrs. Gow Wilson & Stanton";
          the accepted scientific name for a TAXON if the text gives a Latin binomial; otherwise the common name)
  "role": a short descriptor from the text if present ("Director of the Royal Botanic Gardens, Kew", "tea planter, Dimbula",
          "tea brokers, London", "estate in Maskeliya district", "newspaper, Madras"), else ""
Types:
  PERSON       named individual people (not pseudonyms like "A PLANTER"; include "Dr. Trimen", "Sir Joseph Hooker", "Mr. J. L. Shand")
  GROUP        peoples, nationalities, castes, communities, religious groups ("Javanese", "Tamil coolies", "Sinhalese", "Moormen")
  ORG          firms, companies, agency houses, planters' associations, societies, government departments, banks, railways
  ESTATE       named plantation estates and gardens ("Loolecondera estate", "Peradeniya Gardens" is ORG if the institution, ESTATE if the plantation)
  PLACE        countries, colonies, districts, towns, rivers, mountains, provinces
  PUBLICATION  newspapers, journals, books, reports cited as sources ("Indian Agriculturist", "Kew Bulletin", "Ceylon Observer")
  TAXON        plants, animals, fungi, insects named as species or varieties (Latin or common: "Hemileia vastatrix", "Liberian coffee", "cinchona")
  COMMODITY    traded products as goods (tea, coffee, cinchona bark, quinine, rubber, copra, cardamoms) - only when discussed as a product/market, not as a plant
  PRODUCT      named manufactured goods, machines, patents, brands, fertilisers ("Smith's Patent Fibre Machine", "Jackson's Rapid Tea Drier", "Adco")
  EVENT        named exhibitions, conferences, shows, wars ("Melbourne Exhibition of 1880", "Agricultural Conference at Peradeniya")
Rules: list each distinct entity once per chunk even if mentioned many times; do not invent entities that are not in the text;
do not include generic words ("the Government", "the estate", "planters"); do include "Ceylon", "Colombo", "India".
Answer with the JSON array only, no commentary."""

def chunks(text, limit=None):
    if limit is None:        # tables (Market Rates, sales lists) produce a mention per row: smaller chunks
        rows = text.count("<tr>") + text.count("\n|")
        limit = TABLE_CHUNK_WORDS if rows > 20 else CHUNK_WORDS
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    out, cur, n = [], [], 0
    for p in paras:
        w = len(p.split())
        if cur and n + w > limit:
            out.append("\n\n".join(cur)); cur, n = [], 0
        while w > limit:                             # a single huge paragraph (tables): hard split
            words = p.split(); out.append(" ".join(words[:limit])); p = " ".join(words[limit:]); w = len(p.split())
        cur.append(p); n += w
    if cur: out.append("\n\n".join(cur))
    return out

def split_half(chunk):
    words = chunk.split(); h = len(words) // 2
    return [" ".join(words[:h]), " ".join(words[h:])]

def parse_json(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    i, j = s.find("["), s.rfind("]")
    if i < 0 or j < 0: return None
    try:
        arr = json.loads(s[i:j + 1])
    except json.JSONDecodeError:
        try: arr = json.loads(re.sub(r",\s*([\]}])", r"\1", s[i:j + 1]))      # trailing commas
        except json.JSONDecodeError: return None
    out = []
    for m in arr if isinstance(arr, list) else []:
        if not isinstance(m, dict) or not m.get("text"): continue
        t = str(m.get("type", "")).upper()
        out.append({"text": str(m["text"])[:200], "type": t if t in TYPES else "OTHER", "norm": str(m.get("norm", ""))[:200], "role": str(m.get("role", ""))[:200]})
    return out

def ask(base, model, chunk, tries=3):
    body = {"model": model, "temperature": 0, "max_tokens": 8000,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": chunk}],
            "chat_template_kwargs": {"enable_thinking": False}}
    for k in range(tries):
        try:
            req = urllib.request.Request(base + "/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=900))
            got = parse_json(r["choices"][0]["message"]["content"])
            if got is not None: return got, None
            err = "unparsable"
        except Exception as e:
            err = str(e)[:200]; time.sleep(5 * (k + 1))
    return [], err

def extract_chunk(base, model, c, depth=0):
    """Ask; on an unparsable (usually truncated) answer, split the chunk in half and ask again."""
    got, err = ask(base, model, c)
    if err == "unparsable" and depth < 2 and len(c.split()) > 150:
        out = []; errs = []
        for half in split_half(c):
            g, e = extract_chunk(base, model, half, depth + 1); out += g; errs += e
        return out, errs
    return got, ([err] if err else [])

def one(base, model, art):
    t0 = time.time(); cs = chunks(art["text"]); mentions = []; errors = []
    for i, c in enumerate(cs):
        got, errs = extract_chunk(base, model, c)
        for m in got: m["chunk"] = i
        mentions += got
        errors += [{"chunk": i, "error": e} for e in errs]
    return {"id": art["id"], "mentions": mentions, "chunks": len(cs), "words": art.get("words"), "seconds": round(time.time() - t0, 1), "errors": errors}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True); ap.add_argument("--model", required=True)
    ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--parallel", type=int, default=32)
    a = ap.parse_args()
    arts = [json.loads(l) for l in open(a.inp)]
    done = set()
    try: done = {json.loads(l)["id"] for l in open(a.out)}
    except FileNotFoundError: pass
    todo = [x for x in arts if x["id"] not in done]
    print(f"[ner] {len(todo)} articles to do ({len(done)} already done)", flush=True)
    t0 = time.time(); n = 0
    with open(a.out, "a") as out, cf.ThreadPoolExecutor(a.parallel) as ex:
        for res in ex.map(lambda x: one(a.base_url, a.model, x), todo):
            out.write(json.dumps(res, ensure_ascii=False) + "\n"); out.flush(); n += 1
            print(f"[ner] {n}/{len(todo)} {res['id'][:50]} chunks={res['chunks']} mentions={len(res['mentions'])} errors={len(res['errors'])} {res['seconds']}s elapsed {time.time() - t0:.0f}s", flush=True)

if __name__ == "__main__":
    main()
