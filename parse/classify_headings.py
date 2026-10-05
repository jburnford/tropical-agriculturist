#!/usr/bin/env python3
"""
Classify every heading as article-start / subsection / department / front-matter
using Qwen3.8-27B-FP8 served by vLLM.

Headings are sent in *ordered batches from one document*, never independently:
the sequence is the signal. "ABSTRACT", "INTRODUCTION", "CLIMATE" following a
long title are visibly its subsections; alone they are ambiguous. Heading level
is supplied but explicitly flagged as unreliable, because its meaning varies by
volume -- vol043 puts article titles at L2, vol003 puts 499 of them at L4, and
vol085 uses L2 for both a department and a mid-article subsection.

Client is plain urllib, matching eval/extract_1902.py in the canada50 repo, so
it runs inside the vLLM container with no extra packages.
"""
import argparse, json, pathlib, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

SYSTEM = """You label headings from The Tropical Agriculturist (Colombo, 1881-1945), \
an agricultural journal, so its articles can be separated.

For each heading output exactly one label:
ARTICLE - starts a new, self-contained item: an article, a note, a report, a \
correspondence letter, a review. The journal prints many short compiled notes; \
a 60-word item is still ARTICLE if it stands on its own.
SUB     - a subsection *inside* the preceding ARTICLE (e.g. ABSTRACT, \
INTRODUCTION, METHODS, CLIMATE, CONCLUSION, a numbered part, a table legend, a \
named specimen or variety continuing the same study).
DEPT    - a standing department or section header that groups items beneath it \
(EDITORIAL, ORIGINAL ARTICLES, DEPARTMENTAL AND OTHER NOTES, CORRESPONDENCE, \
REVIEWS, MARKET RATES, RETURNS, MEETINGS).
FRONT   - front or back matter: alphabetical index, contents list, \
advertisement, subscription form, masthead, price list, publisher's notice.

The heading LEVEL (L2, L3...) is NOT a reliable guide - it means different \
things in different volumes. Judge from the wording and from what the heading \
sequence is doing.

Reply with one line per heading: the seq number, a space, the label. Nothing else."""

def build_prompt(doc, year, batch):
    lines = []
    for h in batch:
        snip = h['snippet'][:180]
        lines.append(f"seq={h['seq']} L{h['level']} words={h['words']} | {h['title']}\n    text: {snip}")
    return (f"Document: {doc} (year {year or '?'})\n"
            f"Headings in order:\n\n" + "\n".join(lines) +
            f"\n\nLabel all {len(batch)} headings.")

def call(base, model, system, user, retries=3):
    # Qwen3.x thinks by default and will spend ~1,400 reasoning tokens to emit
    # 20 one-word labels -- that measured 58s per batch, ~18h for the corpus.
    # reasoning_effort/enable_thinking are honoured by this model's chat
    # template (same handling as canada50/eval/extract_1902.py).
    body = json.dumps({"model": model,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}],
                       "temperature": 0, "max_tokens": 600,
                       "reasoning_effort": "none",
                       "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request(base.rstrip('/') + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    for k in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.load(r)
            return d["choices"][0]["message"]["content"]
        except Exception as e:
            if k == retries - 1:
                return f"__ERROR__ {e}"
            time.sleep(5 * (k + 1))

LABEL = re.compile(r'^\s*(?:seq\s*=?\s*)?(\d+)\s*[:,\-]?\s*(ARTICLE|SUB|DEPT|FRONT)\b', re.I | re.M)

def parse(out, batch):
    got = {int(m.group(1)): m.group(2).upper() for m in LABEL.finditer(out or '')}
    return [{**h, 'label': got.get(h['seq'], 'UNPARSED')} for h in batch]

def year_of(tag):
    m = re.search(r'agriculturist-(\d{4})-\d{2}', tag) or re.search(r'-(\d{4})-\d+-\d+$', tag)
    if m and 1881 <= int(m.group(1)) <= 1945: return int(m.group(1))
    mv = re.match(r'vol(\d+)', tag)
    return 1880 + int(mv.group(1)) if mv else None

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--model', default='Qwen/Qwen3.8-27B-FP8')
    ap.add_argument('--headings', default='headings.jsonl')
    ap.add_argument('--out', default='labels.jsonl')
    ap.add_argument('--batch', type=int, default=20)
    ap.add_argument('--parallel', type=int, default=3)
    ap.add_argument('--limit-docs', type=int, default=0)
    a = ap.parse_args()

    docs = [json.loads(l) for l in open(a.headings)]
    if a.limit_docs: docs = docs[:a.limit_docs]

    # resume: skip documents already fully written
    done = set()
    outp = pathlib.Path(a.out)
    if outp.exists():
        for l in open(outp):
            try: done.add(json.loads(l)['document'])
            except Exception: pass
    docs = [d for d in docs if d['document'] not in done]
    print(f"{len(docs)} documents to label ({len(done)} already done)", flush=True)

    fh = open(a.out, 'a')
    for di, d in enumerate(docs, 1):
        hs, yr = d['headings'], year_of(d['document'])
        batches = [hs[i:i + a.batch] for i in range(0, len(hs), a.batch)]
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=a.parallel) as ex:
            outs = list(ex.map(lambda b: call(a.base_url, a.model, SYSTEM,
                                              build_prompt(d['document'], yr, b)), batches))
        labelled = []
        for b, o in zip(batches, outs):
            labelled.extend(parse(o, b))
        bad = sum(1 for x in labelled if x['label'] == 'UNPARSED')
        fh.write(json.dumps({'document': d['document'], 'year': yr,
                             'headings': labelled}) + '\n'); fh.flush()
        print(f"[{di}/{len(docs)}] {d['document'][:44]:<44} "
              f"{len(hs):>5} headings  {len(batches):>3} batches  "
              f"{time.time()-t0:6.1f}s  unparsed={bad}", flush=True)
    fh.close()
