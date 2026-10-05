#!/usr/bin/env python3
"""
Independent check of article page links: fetch the IA image of an article's first and
last page, OCR it with Tesseract (not Chandra), and test
  start: >= 60% of the title's content words occur on the first page;
  end:   >= 60% of the article's last 12 content words occur on the last page.
A wrong page link or a boundary on the wrong page fails these.

Usage: verify_articles.py ARTICLES.jsonl > report.tsv
"""
import json, re, subprocess, sys, time, pathlib
CACHE = pathlib.Path("verify/ocr"); CACHE.mkdir(parents=True, exist_ok=True)
STOP = set("the and for with from into its their this that are was were has have been of on in to by at an a as or".split())


def words(s):
    return [w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in STOP]


def page_text(ia, n):
    f = CACHE / f"{ia}_{n}.txt"
    if f.exists():
        return f.read_text()
    img = CACHE / f"{ia}_{n}.jpg"
    for k in range(3):
        r = subprocess.run(["curl", "-sSfL", "-m", "90", "-o", str(img),
                            f"https://archive.org/download/{ia}/page/n{n}_w1500.jpg"], capture_output=True)
        if r.returncode == 0:
            break
        time.sleep(5)
    t = subprocess.run(["tesseract", str(img), "-", "--psm", "3"], capture_output=True, text=True).stdout
    f.write_text(t)
    return t


def share(need, have):
    need = [w for w in need if len(w) >= 3]
    return sum(w in have for w in need) / len(need) if need else None


print("id\ttitle\tfirst_page\tstart_share\tlast_page\tend_share")
for l in open(sys.argv[1]):
    a = json.loads(l)
    first, last = a["pages"][0]["page"], a["pages"][-1]["page"]
    t1 = set(words(page_text(a["ia_id"], first)))
    s = share(words(a["title"]), t1) if a["title"] != "(untitled)" else None
    body = words(re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)", " ", a["text"]))[-12:]
    t2 = set(words(page_text(a["ia_id"], last)))
    e = share(body, t2)
    print(f"{a['id']}\t{a['title'][:50]}\t{first}\t{'' if s is None else f'{s:.2f}'}\t{last}\t{'' if e is None else f'{e:.2f}'}", flush=True)
