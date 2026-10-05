#!/usr/bin/env python3
"""Harvest historyofceylontea.com registry pages from the Wayback Machine.
For every record id: list its 200 captures (one CDX query per registry), fetch the newest, keep it if
the data block is present (estates: Employee History / Owners; planters: Career Details / Work List),
otherwise fall back to older captures. Raw HTML -> raw/<kind>/<id>.html (+ .meta.json). Resumable.
Usage: harvest.py estates|planters [--threads 3]"""
import json, re, sys, time, pathlib, urllib.request, urllib.error, concurrent.futures as cf, argparse
KINDS = {"estates": ("tea-estates/estates-registry", re.compile(r"Employee History|Owners|Post Town")),
         "planters": ("tea-planters/planters-registry", re.compile(r"Career Details|Work List|Planter Details"))}
UA = {"User-Agent": "tropical-agriculturist-gazetteer/0.1 (jic823@usask.ca; research, Wayback only)"}

def captures(path):
    u = f"http://web.archive.org/cdx/search/cdx?url=historyofceylontea.com/{path}/*&output=json&fl=original,timestamp,statuscode,mimetype&filter=statuscode:200&limit=200000"
    rows = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120))[1:]
    by = {}
    for orig, ts, st, mt in rows:
        m = re.search(r"--(\d+)\.html$", orig)
        if m and "html" in mt:
            by.setdefault(m.group(1), []).append((ts, orig))
    for v in by.values():
        v.sort(reverse=True)
    return by

def fetch(ts, url):
    req = urllib.request.Request(f"https://web.archive.org/web/{ts}id_/{url}", headers=UA)
    for k in range(4):
        try:
            return urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 403): return None
            time.sleep(5 * (k + 1))
        except Exception:
            time.sleep(5 * (k + 1))
    return None

def one(kind, i, caps, out, marker):
    dst = out / f"{i}.html"
    if dst.exists(): return "skip"
    tried = 0
    for ts, url in caps[:6]:
        tried += 1
        s = fetch(ts, url)
        if s and marker.search(s):
            dst.write_text(s, encoding="utf-8")
            (out / f"{i}.meta.json").write_text(json.dumps({"id": i, "timestamp": ts, "url": url, "tried": tried, "n_captures": len(caps)}))
            return "ok"
        time.sleep(0.3)
    (out / f"{i}.meta.json").write_text(json.dumps({"id": i, "failed": True, "tried": tried, "n_captures": len(caps), "captures": caps[:6]}))
    return "fail"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("kind", choices=KINDS); ap.add_argument("--threads", type=int, default=3)
    a = ap.parse_args(); path, marker = KINDS[a.kind]
    out = pathlib.Path("raw") / a.kind; out.mkdir(parents=True, exist_ok=True)
    by = captures(path); ids = sorted(by, key=int)
    print(f"[{a.kind}] {len(ids)} ids, {sum(len(v) for v in by.values())} captures", flush=True)
    t0 = time.time(); n = {"ok": 0, "fail": 0, "skip": 0}
    with cf.ThreadPoolExecutor(a.threads) as ex:
        for k, r in enumerate(ex.map(lambda i: one(a.kind, i, by[i], out, marker), ids), 1):
            n[r] += 1
            if k % 100 == 0 or k == len(ids):
                print(f"[{a.kind}] {k}/{len(ids)} {n} {time.time() - t0:.0f}s", flush=True)
    print(f"[{a.kind}] done {n}", flush=True)

if __name__ == "__main__":
    main()
