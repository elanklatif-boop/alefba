# Mehmuni night: the evening at Auntie's, where each stop is a polite no or a yes.
import json, sys
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8811/"; SHOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/"
passed = failed = 0
def check(name, ok, info=""):
    global passed, failed
    if ok: passed += 1; print("PASS", name)
    else: failed += 1; print("FAIL", name, info)
def st(done=None): return {"done": done or {"a1-1": True}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 1, "read": 1,
    "profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
def page(b, state, hash_=""):
    c = b.new_context(viewport={"width": 390, "height": 780})
    if state: c.add_init_script("try { if (!localStorage.getItem('alefba-v3')) localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") } catch (e) {}")
    c.add_init_script("window.__shared = null; navigator.share = async d => { window.__shared = d; };")
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); sent = []
    pg.on("request", lambda r: sent.append(r.post_data or "") if "/api/usage" in r.url else None)
    pg.goto(URL + hash_); pg.wait_for_timeout(1300)
    return c, pg, errs, sent
def play(pg, plan):
    out = []
    for moves in plan:
        for m in moves: pg.click("#night-" + m); pg.wait_for_timeout(150)
        out.append(pg.inner_text("#feedback")); pg.click("#mainBtn"); pg.wait_for_timeout(250)
    return out
PERFECT = [["no", "yes"], ["no", "yes"], ["no", "no"], ["no", "yes"], ["no", "yes"], ["no", "no"], ["no", "no"]]
with sync_playwright() as p:
    b = p.chromium.launch()
    c, pg, errs, _ = page(b, st())
    ids = pg.evaluate("SEASON_PACKS.find(p => p.id === 'taarof').lessons.filter(l => !l.packTalk).map(l => l.id)")
    check("the pack has the evening after the game", ids == ["taarof-1", "taarof-2", "taarof-game", "taarof-night", "taarof-story"], ids)
    pg.evaluate("openLesson(LESSONS.find(l => l.id === 'taarof-night'))"); pg.wait_for_timeout(400)
    check("it opens on what the evening is", "Mehmuni night" in pg.inner_text("#exBox") and "only taarof" in pg.inner_text("#exBox"))
    pg.click("#mainBtn"); pg.wait_for_timeout(300)
    box = pg.inner_text("#exBox")
    check("first stop: the door, with two things to say", "At the door" in box and "befarmâyid!" in box and pg.locator("#nightOpts .night-opt").count() == 2, box)
    check("English is hidden until asked for", "After you!" not in pg.inner_text("#nightThread") and "You first" in pg.inner_text("#night-no"))
    check("no Continue until the stop is over", not pg.is_visible("#mainBtn"))
    pg.click("#togTaEn"); check("the English switch shows it", pg.is_visible("#nightThread .tl-en")); pg.click("#togTaEn")
    pg.click("#night-no"); pg.wait_for_timeout(200)
    th = pg.inner_text("#nightThread")
    check("a polite no: he insists, and there are two new things to say", "aval shomâ" in th and "shomâ befarmâyid" in th and "cheshm, mamnun" in pg.inner_text("#night-yes"), th)
    pg.click("#night-yes"); pg.wait_for_timeout(200)
    fb = pg.inner_text("#feedback")
    check("yes after he insists is just right", any(h in fb for h in ("Just right!", "Perfect!", "Well played!")) and pg.is_visible("#mainBtn") and pg.locator("#nightOpts").count() == 0, fb)
    check("the first dot turns green", pg.evaluate("document.querySelectorAll('#nightDots .nd.good').length") == 1)
    check("the English shows once a stop is over", pg.is_visible("#nightThread .tl-en"))
    pg.click("#mainBtn"); pg.wait_for_timeout(300)
    # tea: yes straight away; vase: take it; dinner: no three times; tahdig: grab it; leaving: stay; taxi: free ride
    fbs = play(pg, [["yes"], ["no", "yes"], ["no", "no", "no"], ["yes"], ["yes"], ["no", "yes"]])
    check("yes to the first offer of tea is too quick", "Too quick!" in fbs[0], fbs[0])
    check("taking the vase: it was only taarof", "only taarof" in fbs[1], fbs[1])
    check("three no's to Grandma: she fills the plate anyway", "Too many no's!" in fbs[2] and "Nobody says no to Grandma" in fbs[2], fbs[2])
    check("taking the tahdig without offering", "Too quick!" in fbs[3] and "without offering" in fbs[3], fbs[3])
    check("staying when it's time to go", "only taarof" in fbs[4] and "2 a.m." in fbs[4], fbs[4])
    check("the free taxi ride", "still pay" in fbs[5], fbs[5])
    end = pg.inner_text("#exBox")
    check("the end card: 3 of 14 is a Tourist, with what they said", "Tourist" in end and "3 of 14 points" in end and "AFTER YOU LEFT" in end.upper() and "learnalefba.com/mehmuni" in end, end)
    check("three things said, the slips first", pg.locator("#nightCard .tc-said li").count() == 3 and "tea" in pg.inner_text("#nightCard .tc-said"), pg.inner_text("#nightCard .tc-said"))
    card = pg.evaluate("(() => { const c = document.getElementById('nightCard'), r = c.getBoundingClientRect(), b = document.getElementById('lessonBody').getBoundingClientRect(); return [c.scrollWidth <= c.clientWidth + 1, r.left >= b.left - 1 && r.right <= b.right + 1]; })()")
    check("the card fits the screen's width", all(card), card)
    pg.screenshot(path=SHOT + "night_end.png")
    pg.click("#taarofShare"); pg.wait_for_timeout(200); sh = pg.evaluate("window.__shared")
    check("Challenge a friend: squares, the rank and the short link", sh and "🟩🟥🟥🟨🟥🟥🟥" in sh["text"] and "Tourist" in sh["text"] and sh["url"] == "https://learnalefba.com/mehmuni", sh)
    pg.click("#mainBtn"); pg.wait_for_timeout(500)
    check("the evening counts as done", pg.evaluate("!!S.done['taarof-night']"))
    check("no page errors", not errs, errs); c.close()
    # a perfect evening
    c, pg, errs, _ = page(b, st())
    pg.evaluate("openLesson(LESSONS.find(l => l.id === 'taarof-night'))"); pg.wait_for_timeout(400); pg.click("#mainBtn"); pg.wait_for_timeout(300)
    fbs = play(pg, PERFECT); end = pg.inner_text("#exBox")
    check("a perfect evening: every stop just right", all(any(h in f for h in ("Just right!", "Perfect!", "Well played!")) for f in fbs), fbs)
    check("14 of 14 is a Taarof master, with nothing to play again for", "Taarof master" in end and "14 of 14 points" in end and "Play again" not in end, end)
    check("every line of the evening is in the list of sounds", pg.evaluate("(() => { const all = new Set(allSounds().map(a => a.file)); return nightLines().every(t => all.has(lineAudio(t).file)); })()"))
    check("no page errors (perfect)", not errs, errs); c.close()
    # the Games tab and the short link
    c, pg, errs, _ = page(b, st())
    pg.evaluate("document.querySelector('[data-tab=games], #tab-games, #navGames')?.click()"); pg.wait_for_timeout(300)
    if not pg.locator("#gw-night").count(): pg.evaluate("typeof showTab === 'function' && showTab('games')"); pg.wait_for_timeout(300)
    check("the Games tab has a row for the evening", pg.locator("#gw-night").count() == 1)
    c.close()
    c, pg, errs, sent = page(b, None, "#mehmuni")
    check("learnalefba.com/mehmuni opens the evening for a first-time visitor", pg.is_visible("#exBox") and "Mehmuni night" in pg.inner_text("#exBox") and not pg.is_visible("#onboard"), pg.inner_text("body")[:200])
    check("the link is taken out of the address", pg.evaluate("location.hash") == "")
    pg.wait_for_timeout(2500)
    check("the link is counted", any("night_link" in s for s in sent), sent)
    check("no page errors (link)", not errs, errs); c.close()
    b.close()
print(f"{passed} of {passed + failed} passed"); sys.exit(1 if failed else 0)
