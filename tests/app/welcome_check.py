# The welcome: a taste to tap first (nân / nun in real voices), one big button and the other ways in as small links,
# and learnalefba.com/?nostats, which leaves this device out of the usage totals.
import json, sys
from playwright.sync_api import sync_playwright
SHOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/"
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3, "prices": {"basic": "$5", "unlimited": "$6.49", "yearly": "$39"}}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def ctx(b, w=390, h=844):
    c = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if w < 500 else 1)
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    sent = []; c.route("**/api/usage*", lambda r: (sent.append(r.request.post_data or ""), r.fulfill(status=204, body=""))[1])
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    return c, pg, errs, sent
box = lambda pg, sel: pg.locator(sel).bounding_box()
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, (w, h) in {"phone": (390, 844), "small phone": (375, 667), "laptop": (1280, 800)}.items():
        c, pg, errs, sent = ctx(b, w, h); pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1400)
        foot = box(pg, "#obStart")["y"]; d = box(pg, "#obDemo"); t = box(pg, "#obDemo .two")
        check(f"the taste (nân / nun) is on the first screen, above the buttons ({name})", pg.is_visible("#obDemo") and t["y"] + t["height"] <= foot, (t, foot))
        check(f"both sides are big enough to tap ({name})", all(x["height"] >= 44 for x in (box(pg, "#obDemo .two-side.book"), box(pg, "#obDemo .two-side.said"))))
        check(f"nothing is wider than the screen ({name})", pg.evaluate("document.getElementById('obBody').scrollWidth <= document.getElementById('obBody').clientWidth + 1"))
        if name == "phone":
            check("it says what the two are", "In books" .lower() in pg.inner_text("#obDemo").lower() and "people say" in pg.inner_text("#obDemo").lower() and "bread" in pg.inner_text("#obDemo"), pg.inner_text("#obDemo"))
            pg.click("#obDemo .two-side.said"); pg.wait_for_timeout(300)
            check("tapping the everyday one plays the real recording", pg.evaluate("PLAYER.src").endswith("audio/said_nun.mp3"), pg.evaluate("PLAYER.src"))
            pg.click("#obDemo .two-side.book"); pg.wait_for_timeout(300)
            check("and the book one", pg.evaluate("PLAYER.src").endswith("audio/word_naan.mp3"), pg.evaluate("PLAYER.src"))
            check("then it says Alefba teaches both", "teaches both" in pg.inner_text("#obDemo"))
            check("one big button, and the other ways in as small links under it", pg.is_visible("#obStart") and "Start learning" in pg.inner_text("#obStart") and box(pg, "#obStart")["height"] >= 54
                  and all(pg.is_visible(x) for x in ("#obLevelBtn", "#obJoinBtn", "#obLittleBtn", "#obTeachBtn")) and not pg.is_visible("#obNext") and not pg.is_visible("#obAlt"))
            check("the button, the price line and the links all fit on the first screen", box(pg, "#obTeachBtn")["y"] + box(pg, "#obTeachBtn")["height"] <= 844 and "a plan opens all 16 levels" in pg.inner_text("#obMain"))
            pg.screenshot(path=SHOT + "welcome_phone.png")
            pg.wait_for_timeout(4500)
            check("the taps are counted once (ob_demo)", sum(s.count("ob_demo") for s in sent) == 1, sent)
            pg.click("#obStart"); pg.wait_for_timeout(300)
            check("Start learning goes to its one question", "Do you already speak some Persian?" in pg.inner_text("#obMain"))
        check(f"no page errors ({name})", not errs, errs); c.close()
    # ---- this device left out of the totals ----
    c, pg, errs, sent = ctx(b); pg.goto("http://127.0.0.1:8811/?nostats"); pg.wait_for_timeout(1400)
    check("?nostats says the device isn't counted, and tidies the address", pg.is_visible("#noticeSheet") and "isn't counted" in pg.inner_text("#noticeSheet") and "nostats" not in pg.url, pg.url)
    pg.screenshot(path=SHOT + "welcome_nostats.png")
    pg.click("#noticeOk"); pg.click("#obDemo .two-side.said"); pg.wait_for_timeout(5000)
    check("nothing is sent to the totals from this device", not sent, sent)
    pg.goto("http://127.0.0.1:8811/name.html"); pg.wait_for_timeout(1500)
    check("nor from the name page", not sent, sent)
    pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1500); pg.click("#obDemo .two-side.said"); pg.wait_for_timeout(4800)
    check("it stays that way on the next visit", not sent and not pg.is_visible("#noticeSheet"), sent)
    pg.goto("http://127.0.0.1:8811/?nostats=off"); pg.wait_for_timeout(1400)
    check("?nostats=off counts it again", pg.is_visible("#noticeSheet") and "counted again" in pg.inner_text("#noticeSheet"))
    pg.click("#noticeOk"); pg.click("#obDemo .two-side.said"); pg.wait_for_timeout(4800)
    check("and what's done here is sent again", any("ob_demo" in s for s in sent), sent)   # (the day's "opened the app" is only ever sent once)
    check("no page errors (nostats)", not errs, errs); c.close()
    b.close()
print(f"{sum(res)} of {len(res)} passed")
