# learnalefba.com/play, the balloon game for a classroom screen: it opens on the Games tab with Balloons picked and no
# welcome in front, it's counted (play_link), the balloons are big on a big screen and unchanged on a phone, a game plays
# to the end, and a normal first visit still gets the welcome.
import json
from playwright.sync_api import sync_playwright
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
BASE = "http://127.0.0.1:8811/"
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def ctx(b, w, h):
    c = b.new_context(viewport={"width": w, "height": h}); sent = []
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    def got(r):
        try: sent.extend(json.loads(r.request.post_data or "{}").get("e", []))
        except Exception: pass
        r.fulfill(status=200, body="{}")
    c.route("**/api/usage", got)
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    return c, pg, errs, sent
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- a classroom screen ----
    c, pg, errs, sent = ctx(b, 1366, 768)
    pg.goto(BASE + "play.html"); pg.wait_for_timeout(1800)
    check("the short link lands in the app, with the link tidied away", pg.evaluate("location.pathname + location.hash") == "/", pg.url)
    check("no welcome in front of it", not pg.is_visible("#onboard"))
    check("the Games tab, with Balloons picked", pg.is_visible("#view-games") and pg.get_attribute("#gk-balloons", "aria-pressed") == "true")
    check("a note for teachers at the top", pg.is_visible("#classPlayNote") and "big screen" in pg.inner_text("#classPlayNote"))
    pg.evaluate("sendUsage()"); pg.wait_for_timeout(300)
    check("it's counted once (play_link)", sent.count("play_link") == 1, sent)
    pg.click("#gw-1"); pg.wait_for_timeout(700)
    check("Level 1 opens the balloon game", pg.is_visible("#sky") and "Pop the balloon" in pg.inner_text("#exBox"))
    bw = pg.evaluate("document.querySelector('.balloon').getBoundingClientRect().width")
    sky = pg.evaluate("(() => { const r = document.querySelector('#sky').getBoundingClientRect(); return [r.top, r.bottom, innerHeight]; })()")
    check(f"big balloons on a big screen ({round(bw)}px wide)", bw >= 140, bw)
    check("the sky fits on the screen", sky[1] <= sky[2] + 1, sky)
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/play_big.png")
    # play every round: pop the balloon whose label is the word being said
    for _ in range(20):
        if pg.evaluate("!R || R.phase === 'result'"): break
        m = pg.evaluate("(() => { const ex = current(); return ex.words[R.balloon.round].m; })()")
        pg.locator(f".balloon[aria-label=\"{m}\"]").first.click(force=True); pg.wait_for_timeout(850)
    check("the game plays to the end", pg.evaluate("R && R.phase === 'result'"))
    pg.click("#mainBtn"); pg.wait_for_timeout(600)
    if pg.evaluate("!!R"): pg.click("#mainBtn"); pg.wait_for_timeout(600)
    check("afterwards it's back on the Games tab, still with no welcome", pg.evaluate("!R") and pg.is_visible("#view-games") and not pg.is_visible("#onboard"))
    check("no page errors (classroom screen)", not errs, errs); c.close()

    # ---- the same link on a phone: balloons as they always were ----
    c, pg, errs, sent = ctx(b, 390, 844)
    pg.goto(BASE + "play.html"); pg.wait_for_timeout(1800); pg.click("#gw-1"); pg.wait_for_timeout(700)
    bw = pg.evaluate("document.querySelector('.balloon').getBoundingClientRect().width")
    check(f"on a phone the balloons are their usual size ({round(bw)}px)", bw <= 80, bw)
    check("no page errors (phone)", not errs, errs); c.close()

    # ---- a normal first visit is unchanged ----
    c, pg, errs, sent = ctx(b, 390, 844)
    pg.goto(BASE); pg.wait_for_timeout(1500)
    check("a normal first visit still opens the welcome, without the classroom styles", pg.is_visible("#onboard") and not pg.evaluate("document.body.classList.contains('class-play')"))
    c.close()
    b.close()
print(f"play_check: {sum(res)} of {len(res)} passed")
