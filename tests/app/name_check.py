# Your name in Persian (learnalefba.com/name): type a name, see it in Persian with each letter, its name and sound
# (tap to hear the real recording), switch to the other spelling, and save or share it as a picture for a story.
import json, sys, time
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8811/"
PAD = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/"
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
NAMES = {"Elan": {"name": "Elan", "fa": "ایلان", "alt": "الان"}, "Sara": {"name": "Sara", "fa": "سارا", "alt": None}, "Mary Jane": {"name": "Mary Jane", "fa": "مری جین", "alt": None}}
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ("light", "dark"):
        c = b.new_context(viewport={"width": 390, "height": 844}, color_scheme=scheme, accept_downloads=True)
        asked, used, sounds = [], [], []
        def name(r):
            n = json.loads(r.request.post_data)["name"]; asked.append(n)
            if n in NAMES: r.fulfill(status=200, content_type="application/json", body=json.dumps(NAMES[n]))
            else: r.fulfill(status=422, content_type="application/json", body=json.dumps({"error": "not_a_name"}))
        c.route("**/api/name", name)
        c.route("**/api/usage", lambda r: (used.extend(json.loads(r.request.post_data)["e"]), r.fulfill(status=200, body="{}")))
        pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.on("request", lambda rq: sounds.append(rq.url) if "/audio/letter_" in rq.url else None)
        pg.goto(URL + "name.html"); pg.wait_for_timeout(600)
        if scheme == "light":
            check("the page opens with a box for a name", pg.is_visible("#nameIn") and "What does your name look like in Persian?" in pg.inner_text("h1"))
            pg.fill("#nameIn", "Bananas"); pg.click("#nameGo"); pg.wait_for_timeout(500)
            check("not a name: it says so kindly", "doesn't look like a name" in pg.inner_text("#msg") and pg.is_hidden("#result"))
        pg.fill("#nameIn", "Elan"); pg.press("#nameIn", "Enter"); pg.wait_for_timeout(700)
        check(f"the name in big Persian letters ({scheme})", pg.inner_text("#big") == "ایلان" and pg.inner_text("#latin") == "Elan")
        lets = pg.locator(".lt:not(.space)")
        names = [lets.nth(i).locator(".n").inner_text() for i in range(lets.count())]
        check(f"letter by letter, right to left, with names and sounds ({names})", names == ["alef", "ye", "lâm", "alef", "nun"] and "y, i" in lets.nth(1).inner_text())
        check("and the other spelling, to switch to", pg.is_visible("#alt") and "الان" in pg.inner_text("#alt"))
        if scheme == "light":
            lets.nth(2).click(); pg.wait_for_timeout(400)
            check("tapping a letter plays its name (the real recording)", any(u.endswith("/audio/letter_laam.mp3") for u in sounds), sounds)
            pg.screenshot(path=PAD + "name_page.png", full_page=True)
            pg.click("#alt button"); pg.wait_for_timeout(300)
            check("Use this one switches the spelling", pg.inner_text("#big") == "الان" and "ایلان" in pg.inner_text("#alt"))
            with pg.expect_download() as dl:
                pg.click("#saveBtn")
            d = dl.value; path = PAD + "name_card.png"; d.save_as(path)
            check(f"Save the picture gives a PNG named for them ({d.suggested_filename})", d.suggested_filename == "my-name-in-persian-elan.png")
            from PIL import Image
            im = Image.open(path)
            check(f"sized for an Instagram story ({im.size})", im.size == (1080, 1920))
            check("the share and save are counted", "name_share" in used and "name_made" in used and "name_open" in used, used)
            pg.fill("#nameIn", "Mary Jane"); pg.click("#nameGo"); pg.wait_for_timeout(600)
            check("a two-part name keeps its space", pg.locator(".lt.space").count() == 1 and pg.inner_text("#big") == "مری جین")
            pg.goto(URL + "name.html?n=Sara"); pg.wait_for_timeout(800)
            check("a link with a name in it shows that name", pg.inner_text("#big") == "سارا")
            check("Start learning goes to the app", pg.get_attribute("#startBtn", "href") == "./")
        else:
            pg.screenshot(path=PAD + "name_page_dark.png", full_page=True)
        check(f"no page errors ({scheme})", not errs, errs); c.close()
    # the app's Library tab has the card
    c = b.new_context(viewport={"width": 390, "height": 844})
    st = {"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en"}, "log": {}, "speak": 1, "read": 0, "profile": {"name": "Sara", "goal": 2, "adult": True, "whoSet": True, "speakSelf": 1, "readSelf": 0, "reasons": []}}
    c.add_init_script("localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(st)) + ")")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"talks": True, "plans": True, "signedIn": False})))
    pg = c.new_page(); pg.goto(URL); pg.wait_for_timeout(1200); pg.evaluate("showView('alphabet'); 0"); pg.wait_for_timeout(300)
    check("the Library has a Your name in Persian card", pg.is_visible("#nameCard") and pg.get_attribute("#nameCard", "href") == "name")
    c.close(); b.close()
print(f"{sum(res)} of {len(res)} passed")
sys.exit(0 if all(res) else 1)
