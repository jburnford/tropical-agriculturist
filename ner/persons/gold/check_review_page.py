#!/usr/bin/env python3
"""Browser check of the review page (headless Chromium via Playwright). Run before publishing:
    python3 check_review_page.py [URL]      (default: the local review/index.html)
Checks: loads without script errors; answering a person updates the counts; export carries the dataset
fingerprint and stable record keys; answers survive a reload; a fresh browser can import the export; an export
from a different dataset version is refused; the layout renders at phone width. Exits non-zero on failure."""
import asyncio, pathlib, sys, tempfile, json
from playwright.async_api import async_playwright
here = pathlib.Path(__file__).resolve().parent
URL = sys.argv[1] if len(sys.argv) > 1 else (here / "review/index.html").as_uri()
DATASET = json.load(open(here / "manifest.json"))["dataset"]
fails = []
def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)

async def main():
    tmp = pathlib.Path(tempfile.mkdtemp())
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(accept_downloads=True, viewport={"width": 1200, "height": 900})
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(URL)
        check(await pg.is_visible("#help"), "instructions shown on first visit")
        check(await pg.inner_text("#dsv") == DATASET, f"page shows dataset {DATASET}")
        await pg.click("#helpClose"); await pg.fill("#student", "Test Student")
        await pg.check('input[name="one"][value="y"]')
        if await pg.query_selector('input[name="wd"][value="proposed"]'):
            await pg.check('input[name="wd"][value="proposed"]')
        else:
            await pg.check('input[name="wd"][value="none"]')
        n = len(await pg.query_selector_all('.ment'))
        for i in range(n):
            await pg.check(f'input[name="m{i}"][value="y"]')
        check(await pg.inner_text("#pDone") == "1", "person counted as complete")
        check(await pg.inner_text("#mDone") == str(n), f"{n} mentions counted")
        check(len(await pg.query_selector_all('.ment a')) >= n, "scan links present")
        await pg.click("#next")
        await pg.fill("#qid", "Qabc")
        check("invalid" in (await pg.get_attribute("#qid", "class")), "invalid Q-number flagged")
        await pg.fill("#qid", "")
        async with pg.expect_download() as dl:
            await pg.click("#exportBtn")
        d = await dl.value; path = tmp / d.suggested_filename; await d.save_as(path)
        lines = path.read_text().splitlines(); head = lines[0].split("\t")
        check(head[:2] == ["dataset", "student"] and "mention_key" in head, "export header has dataset + mention_key")
        check(all(l.split("\t")[0] == DATASET for l in lines[1:]), "every export row carries the dataset fingerprint")
        ments = [l.split("\t") for l in lines[1:] if l.split("\t")[4] == "mention"]
        check(len(ments) == 400 and all("#" in m[head.index("mention_key")] for m in ments), "400 mention rows with stable keys")
        await pg.reload()
        check(await pg.input_value("#student") == "Test Student" and await pg.inner_text("#pDone") == "1", "answers survive reload")
        ctx2 = await b.new_context(); pg2 = await ctx2.new_page()
        pg2.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg2.goto(URL)
        await pg2.set_input_files("#importFile", str(path)); await pg2.wait_for_timeout(500)
        check(await pg2.inner_text("#pDone") == "1" and await pg2.inner_text("#mDone") == str(n), "import restores answers in a fresh browser")
        other = tmp / "other.tsv"
        other.write_text("\n".join([lines[0]] + ["\t".join(["000000000000"] + l.split("\t")[1:]) for l in lines[1:]]) + "\n")
        ctx3 = await b.new_context(); pg3 = await ctx3.new_page(); msgs = []
        pg3.on("dialog", lambda d: (msgs.append(d.message), asyncio.ensure_future(d.accept())))
        await pg3.goto(URL)
        await pg3.set_input_files("#importFile", str(other)); await pg3.wait_for_timeout(500)
        check(await pg3.inner_text("#pDone") == "0" and any("different version" in m for m in msgs), "export from another dataset is refused")
        await pg.set_viewport_size({"width": 390, "height": 800})
        await pg.screenshot(path=str(tmp / "mobile.png"))
        check(not errs, f"no script errors {errs}")
        await b.close()
    print("screenshots in", tmp)

asyncio.run(main())
sys.exit(1 if fails else 0)
