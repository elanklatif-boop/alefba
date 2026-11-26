# learnalefba.com/<page>?nostats leaves this device out of the stats from any page, not only the app: the name page,
# the Yalda page, the guides and the rest. ?nostats=off counts it again. Nothing is sent while it's on.
import json, sys
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:8811/"
OK = []
def check(n, ok, x=""): OK.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
with sync_playwright() as p:
    b = p.chromium.launch()
    for page in ("name.html", "yalda.html", "what-is-taarof.html", "taarof.html", "parents.html"):
        c = b.new_context(viewport={"width": 390, "height": 844}); sent = []
        c.route("**/api/usage*", lambda r: (sent.append(r.request.post_data or ""), r.fulfill(status=204, body=""))[1])
        c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body="{}"))
        pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE + page + "?nostats"); pg.wait_for_timeout(900)
        check(f"{page}?nostats: this device is left out, and it says so", pg.evaluate("localStorage.getItem('alefba-nostats')") == "1" and "left out of your stats" in pg.inner_text("#nostatsNote"), pg.evaluate("localStorage.getItem('alefba-nostats')"))
        check(f"{page}: the address loses ?nostats (so it isn't shared on)", "nostats" not in pg.url, pg.url)
        pg.reload(); pg.wait_for_timeout(1500)
        check(f"{page}: nothing is counted from this device", not sent, sent)
        pg.goto(BASE + page + "?nostats=off"); pg.wait_for_timeout(600)
        check(f"{page}?nostats=off counts it again", pg.evaluate("localStorage.getItem('alefba-nostats')") is None and "counted in your stats again" in pg.inner_text("#nostatsNote"))
        check(f"{page}: no page errors", not errs, errs); c.close()
    b.close()
print(f"{sum(OK)}/{len(OK)}")
sys.exit(0 if all(OK) else 1)
