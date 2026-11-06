# The microphone switched off for Alefba: say how to turn it on, for this browser, instead of just "not available".
from playwright.sync_api import sync_playwright
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
URL = "http://127.0.0.1:8811/"
SHOT = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/mic/"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, ua, vp, want in [("chrome", None, (1100, 800), "Chrome on a computer"), ("iphone", IPHONE, (390, 844), "Safari on an iPhone or iPad")]:
        kw = {"viewport": {"width": vp[0], "height": vp[1]}, "device_scale_factor": 2}
        if ua: kw["user_agent"] = ua
        c = b.new_context(**kw); c.route("**/api/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{}'))
        pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.goto(URL); pg.wait_for_timeout(1200)
        pg.evaluate("closeOnboarding()")
        t = pg.evaluate("micTrouble({ name: 'NotAllowedError' })")
        check(f"{name}: a blocked microphone says how to turn it on", t["help"] and "turn it on" in t["text"] and "available" not in t["text"])
        pg.evaluate("openMicHelp()"); pg.wait_for_timeout(300)
        txt = pg.inner_text("#micHelpSheet")
        check(f"{name}: the steps are for this browser ({want})", want in txt.split("Using a different browser?")[0] and "Allow" in txt)
        check(f"{name}: the other browsers are a tap away", pg.locator("#micHelpSheet details summary").count() == 1)
        check(f"{name}: and a reload button", pg.is_visible("#micHelpReload"))
        pg.screenshot(path=SHOT + f"{name}.png")
        pg.click("#micHelpClose"); pg.wait_for_timeout(200)
        check(f"{name}: Not now closes it", pg.locator("#micHelpSheet").count() == 0)
        check(f"{name}: no page errors", not errs, errs)
        c.close()
    b.close()
print(f"{sum(res)} of {len(res)} passed")
