# List pages whose transcribed body uses Chandra's table-summary phrasing. Usage: summ_pages.py CORPUS > list.tsv
import re, pathlib, sys
MARK = re.compile(r"^\d+-{48}\s*$", re.M)
PAT = re.compile(r"Table with \d+ columns|Includes (categories|items|sections|entries|data|rows)|The table (lists|contains|shows|includes)|Contains multiple rows|Various entries for", re.I)
for d in sorted(pathlib.Path(sys.argv[1]).glob("vol*")):
    pages = MARK.split(next(d.rglob("*.md")).read_text(errors="replace"))
    for i, p in enumerate(pages):
        if PAT.search(re.sub(r"!\[[^\]]*\]\([^)]*\)[^\n]*", " ", p)):
            print(f"{d.name}\t{i}")
