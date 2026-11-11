# learnalefba.com/taarof: straight into the taarof game, for a first-time visitor and for a returning learner.
import json, sys
from playwright.sync_api import sync_playwright
SHOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/"
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3, "prices": {"basic": "$5", "unlimited": "$6.49", "yearly": "$39"}}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def play(pg, wrong_first=False):
    for _ in range(2): pg.click("#mainBtn"); pg.wait_for_timeout(120)
    for k in range(12):
        i = pg.evaluate("w => current().opts.findIndex(o => w ? !o.ok : o.ok)", wrong_first and k == 0); pg.click(f"#opt-{i}"); pg.wait_for_timeout(100); pg.click("#mainBtn"); pg.wait_for_timeout(130)
with sync_playwright() as p:
    b = p.chromium.launch()
    # 1. someone who has never been here, from the short link
    c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    sent = []; c.route("**/api/usage*", lambda r: (sent.append(r.request.post_data or ""), r.fulfill(status=204, body=""))[1])
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto("http://127.0.0.1:8811/taarof.html"); pg.wait_for_timeout(1800)
    check("the short link lands in the app, with the link tidied", pg.url.rstrip("/") == "http://127.0.0.1:8811", pg.url)
    check("a first-time visitor is in the game straight away", pg.is_visible("#exBox") and "What is taarof?" in pg.inner_text("#exBox"), pg.inner_text("body")[:200])
    pg.screenshot(path=SHOT + "link_new.png")
    play(pg, wrong_first=True)
    end = pg.inner_text("#exBox"); check("they can play it to the end", "11 of 12" in end, end[:200])
    pg.evaluate("navigator.share = d => { window.__shared = d; return Promise.resolve(); }")
    pg.click("#taarofShare"); pg.wait_for_timeout(200); sh = pg.evaluate("window.__shared")
    check("Challenge a friend shares the score and the short link", sh and "11 of 12" in sh["text"] and sh["url"] == "https://learnalefba.com/taarof", sh)
    pg.screenshot(path=SHOT + "link_end.png")
    pg.click("#mainBtn"); pg.wait_for_timeout(600)
    fin = pg.inner_text("#lesson"); pg.screenshot(path=SHOT + "link_finish.png")
    check("the finish screen shows", pg.evaluate("!!(R && R.finish)") or "Taarof" in fin, fin[:300])
    print("  finish screen says:", " | ".join(x for x in fin.split("\n") if x.strip())[:400])
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(400)
    check("closing it leaves the welcome, with the free lesson button", pg.is_visible("text=Try a free lesson: 2 minutes"), pg.inner_text("body")[:200])
    pg.screenshot(path=SHOT + "link_after.png")
    pg.wait_for_timeout(4500)
    check("the visit is counted (taarof_link)", any("taarof_link" in s for s in sent), sent)
    check("no page errors (new visitor)", not errs, errs); c.close()
    # 2. a returning learner
    state = {"done": {"a1-1": True}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 1, "read": 1,
             "profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
    c = b.new_context(viewport={"width": 390, "height": 844})
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto("http://127.0.0.1:8811/#taarof"); pg.wait_for_timeout(1500)
    check("a returning learner is in the game too", pg.is_visible("#exBox") and "What is taarof?" in pg.inner_text("#exBox"))
    play(pg); pg.click("#mainBtn"); pg.wait_for_timeout(500); pg.evaluate("closeLesson()"); pg.wait_for_timeout(300)
    check("and it's saved as done for them", pg.evaluate("!!S.done['taarof-game']") and pg.is_visible("#view-lessons"))
    pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1000)
    check("the plain address still opens the Lessons tab, not the game", not pg.is_visible("#exBox"))
    check("no page errors (returning)", not errs, errs); c.close()
    b.close()
print(f"{sum(res)} of {len(res)} passed")
