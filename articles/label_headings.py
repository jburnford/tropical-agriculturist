#!/usr/bin/env python3
"""
Label skeleton candidates with an OpenAI-compatible LLM server (vLLM).

Each issue's candidates go to the model in chunks of CHUNK lines with OVERLAP
lines shared between neighbours; for an overlapped line the label from the chunk
in which it sits farther from the edge wins. The model answers one line per
candidate: "<id> <code>". Thinking is disabled (Qwen3.x reasons by default and
spends ~1,400 tokens per batch otherwise -- see tropical-markdown-structure).

Usage: label_headings.py --base-url URL --model NAME --skeleton skeleton.jsonl
                         --out labels.jsonl [--units FILE] [--parallel 8]
Output, one line per unit: {unit, labels: {id: LABEL}, missing, chunks, seconds}
Resumable: units already in --out are skipped.
"""
import argparse, json, re, sys, time, urllib.request, concurrent.futures as cf

CHUNK, OVERLAP = 150, 20
CODES = {"D": "SECTION", "A": "ARTICLE", "C": "CONT", "S": "SUB", "B": "BYLINE", "O": "OTHER"}

SYSTEM = """You segment issues of The Tropical Agriculturist (Colombo, 1881-1945), a planting and agricultural journal, into articles.

You get the heading-like lines of one issue in reading order, OCR'd from page scans. Each line shows:
  id | scan page, printed page | markup | the line's text | -> the start of the text that follows it
Markup: h1-h6 = markdown heading level (unreliable: the OCR assigned it, and levels mean different things in different years);
caps = a standalone ALL-CAPS line; bold = a standalone bold line; boldlead = bold words opening a paragraph;
short = a short standalone line; headrest = text printed on the same line as the page's running head.

Give every line exactly one code:
  D  section heading that groups several articles: departments such as "FIBRES.", "EDIBLE PRODUCTS.", "ORIGINAL ARTICLES",
     "SELECTED ARTICLES", "DEPARTMENTAL NOTES", "CORRESPONDENCE", "MEETINGS, CONFERENCES, &c.", "REVIEWS".
  A  the title of a new article: any self-contained piece that could be cited on its own -- an article, editorial,
     short news note, letter, report, review of a book, minutes of a meeting, a table or return printed as its own item.
  C  continuation of the title on the line just before (a title broken over two lines).
  S  subheading inside an article (INTRODUCTION, HISTORY, CLIMATE, "Cost of the Bark.", numbered sections, sub-topics
     of one continuous piece by one author or source).
  B  byline, author, affiliation or source line ("BY WILLIAM FAWCETT, B.SC.", "ABSTRACT BY C. DRIEBERG.", "(From the Indian Forester)").
  O  anything else: journal title, masthead, volume/number/date lines, table captions and column headings,
     figure captions, page furniture, list or price-table headings, the opening words of an ordinary paragraph.

How to decide:
- Read the text that follows each line. A title is followed by the opening of a piece; a subhead by the continuation
  of an argument already under way; a table caption by table rows or figures.
- A section heading (D) is often directly followed by an article title (A) on the next line.
- Letters to the editor each start a new article (A).
- When in doubt between A and S, ask: does the text after it change subject or source? If yes, A.

Answer with exactly one line per id, in order, formatted "<id> <code>", and nothing else."""


def fmt(c):
    f = c["folio"] or "-"
    return f'{c["id"]} | p{c["page"]},{f} | {c["kind"]} | {c["text"][:160]} | -> {c["next"][:150]}'


def ask(base, model, cands, tries=3):
    body = {
        "model": model, "temperature": 0, "max_tokens": 12 * len(cands) + 200,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": "\n".join(fmt(c) for c in cands)}],
        "chat_template_kwargs": {"enable_thinking": False},
    }
    for k in range(tries):
        try:
            req = urllib.request.Request(base + "/chat/completions", json.dumps(body).encode(),
                                         {"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=900))
            text = r["choices"][0]["message"]["content"]
            got = {}
            for m in re.finditer(r"^\s*(\d+)\s*[:|\-]?\s*([DACSBO])\b", text, re.M):
                got[int(m.group(1))] = CODES[m.group(2)]
            want = {c["id"] for c in cands}
            if len(want - set(got)) <= 0.1 * len(want) or k == tries - 1:
                return {i: v for i, v in got.items() if i in want}
        except Exception as e:
            print(f"[warn] request failed ({e}); retry {k + 1}", file=sys.stderr, flush=True)
            time.sleep(5 * (k + 1))
    return {}


def label_unit(base, model, U):
    t0 = time.time()
    cands = U["cands"]
    best = {}                                   # id -> (distance from chunk edge, label)
    step = CHUNK - OVERLAP
    starts = list(range(0, max(1, len(cands) - OVERLAP), step)) or [0]
    for s in starts:
        chunk = cands[s:s + CHUNK]
        if not chunk:
            continue
        got = ask(base, model, chunk)
        for j, c in enumerate(chunk):
            if c["id"] in got:
                d = min(j, len(chunk) - 1 - j) if len(cands) > CHUNK else 10 ** 6
                if c["id"] not in best or d > best[c["id"]][0]:
                    best[c["id"]] = (d, got[c["id"]])
    labels = {c["id"]: best[c["id"]][1] for c in cands if c["id"] in best}
    return {"unit": U["unit"], "labels": labels, "missing": len(cands) - len(labels),
            "chunks": len(starts), "seconds": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True); ap.add_argument("--model", required=True)
    ap.add_argument("--skeleton", default="skeleton.jsonl"); ap.add_argument("--out", required=True)
    ap.add_argument("--units", help="file of unit ids to run (default: all)")
    ap.add_argument("--parallel", type=int, default=8)
    a = ap.parse_args()
    units = [json.loads(l) for l in open(a.skeleton)]
    if a.units:
        keep = {l.strip() for l in open(a.units) if l.strip()}
        units = [u for u in units if u["unit"] in keep]
    done = set()
    try:
        done = {json.loads(l)["unit"] for l in open(a.out)}
    except FileNotFoundError:
        pass
    todo = [u for u in units if u["unit"] not in done]
    print(f"[label] {len(todo)} units to do ({len(done)} already done)", flush=True)
    t0 = time.time(); n = 0
    with open(a.out, "a") as out, cf.ThreadPoolExecutor(a.parallel) as ex:
        for res in ex.map(lambda U: label_unit(a.base_url, a.model, U), todo):
            out.write(json.dumps(res) + "\n"); out.flush(); n += 1
            print(f"[label] {n}/{len(todo)} {res['unit'][:60]} missing={res['missing']} "
                  f"chunks={res['chunks']} {res['seconds']}s  elapsed {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
