"""Minimal client for the WikidataMCP server (https://wd-mcp.wmcloud.org/mcp, Streamable HTTP, stateless).
Vector search (search_items) is the ONLY candidate source for disambiguation; execute_sparql is used only to
read statements of candidate QIDs that search returned. Never the REST wbsearchentities API."""
import json, time, urllib.request, urllib.error
URL = "https://wd-mcp.wmcloud.org/mcp"
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
_id = [0]

def _post(body):
    r = urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps(body).encode(), headers=H, method="POST"), timeout=120)
    raw = r.read().decode()
    if "data:" in raw[:200]:
        raw = "\n".join(l[5:].strip() for l in raw.splitlines() if l.startswith("data:"))
    return json.loads(raw) if raw.strip() else None

def init():
    _post({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-03-26",
           "capabilities": {}, "clientInfo": {"name": "tropical-persons", "version": "0.1"}}})

def call(tool, **args):
    for k in range(6):
        _id[0] += 1
        try:
            r = _post({"jsonrpc": "2.0", "id": _id[0], "method": "tools/call", "params": {"name": tool, "arguments": args}})
            if "error" in r:
                raise RuntimeError(r["error"])
            res = r["result"]
            txt = res["content"][0]["text"]
            if res.get("isError"):
                raise RuntimeError(txt[:300])
            return txt
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            time.sleep(2 ** k + 1)
    raise RuntimeError(f"{tool} failed after retries: {args}")

def search(q):
    """-> [(qid, label, description)]"""
    out = []
    for line in call("search_items", query=q).splitlines():
        if ":" not in line: continue
        qid, rest = line.split(":", 1)
        label, _, desc = rest.strip().partition(" — ")
        out.append((qid.strip(), label.strip(), desc.strip()))
    return out
