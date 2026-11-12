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
        if not pg.locator("#nightOpts").count(): break
        for m in moves: pg.click("#night-" + m); pg.wait_for_timeout(330)
        out.append(pg.inner_text("#feedback")); pg.click("#mainBtn"); pg.wait_for_timeout(250)
    return out
def swipe(pg, dx):
    r = pg.evaluate("(() => { const r = document.getElementById('nightScene').getBoundingClientRect(); return [r.left + r.width / 2, r.top + 40]; })()")
    pg.mouse.move(r[0], r[1]); pg.mouse.down()
    for k in range(1, 7): pg.mouse.move(r[0] + dx * k / 6, r[1])
    return r
PERFECT = [["no", "yes"], ["no", "yes"], ["no", "no"], ["no", "yes"], ["no", "yes"], ["no", "no"], ["no", "no"]]
GOOD = ("Just right!", "Perfect!", "Well played!")
ENGLISH = ["You first", "Go in", "Polite no", "After you", "No, please", "Thanks."]
with sync_playwright() as p:
    b = p.chromium.launch()
    c, pg, errs, _ = page(b, st())
    ids = pg.evaluate("SEASON_PACKS.find(p => p.id === 'taarof').lessons.filter(l => !l.packTalk).map(l => l.id)")
    check("the pack has the evening after the game", ids == ["taarof-1", "taarof-2", "taarof-game", "taarof-night", "taarof-story"], ids)
    pg.evaluate("openLesson(LESSONS.find(l => l.id === 'taarof-night'))"); pg.wait_for_timeout(400)
    check("it opens on what the evening is", "Mehmuni night" in pg.inner_text("#exBox") and "only taarof" in pg.inner_text("#exBox") and "three hearts" in pg.inner_text("#exBox"))
    pg.click("#mainBtn"); pg.wait_for_timeout(300)
    box = pg.inner_text("#exBox")
    check("first stop: one card (the neighbor and his line) and two things to say", "At the door" in box and "befarmâyid!" in pg.inner_text("#nightScene") and pg.locator("#nightOpts .night-opt").count() == 2
          and pg.locator("#nightScene").count() == 1 and pg.locator(".night-thread, .nb").count() == 0, box)
    shown = pg.evaluate("[...document.querySelectorAll('#nightScene, #nightOpts')].map(e => e.innerText).join(' | ')")
    check("no English on the card or the answers", not any(w in shown for w in ENGLISH), shown)
    check("three hearts to start", pg.inner_text("#nightHearts").count("❤️") == 3 and pg.get_attribute("#nightHearts", "aria-label") == "3 of 3 hearts left")
    check("no Continue until the stop is over", not pg.is_visible("#mainBtn"))
    pg.click("#togTaEn"); check("the English switch shows it", pg.is_visible("#nightScene .tl-en") and "After you!" in pg.inner_text("#nightScene")); pg.click("#togTaEn")
    check("and hides it again", not pg.is_visible("#nightScene .tl-en"))
    # a small drag springs back; a long one to the left is a polite no
    swipe(pg, -30); pg.mouse.up(); pg.wait_for_timeout(350)
    check("a small drag doesn't answer", "befarmâyid!" in pg.inner_text("#nightScene") and "shomâ befarmâyid" not in pg.inner_text("#nightScene"))
    swipe(pg, -170); check("dragging left shows which way it's going", pg.evaluate("document.getElementById('nightScene').classList.contains('to-no')")); pg.mouse.up(); pg.wait_for_timeout(450)
    sc = pg.inner_text("#nightScene")
    check("swipe left: he insists, on the same card, with two new things to say", "na, na, shomâ befarmâyid!" in sc and "🥺" in sc and "cheshm, mamnun" in pg.inner_text("#night-yes"), sc)
    pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(450)
    fb = pg.inner_text("#feedback")
    check("the right arrow is yes: after he insists that's just right", any(h in fb for h in GOOD) and pg.is_visible("#mainBtn") and pg.locator("#nightOpts").count() == 0 and "😍" in pg.inner_text("#nightScene"), fb)
    check("the first dot turns green, and no heart is lost", pg.evaluate("document.querySelectorAll('#nightDots .nd.good').length") == 1 and pg.inner_text("#nightHearts").count("❤️") == 3)
    check("still no English once a stop is over", not pg.is_visible("#nightScene .tl-en"))
    pg.click("#mainBtn"); pg.wait_for_timeout(300)
    # tea: yes straight away (a heart); vase: take it (a heart); dinner: no three times (no heart); tahdig: grab it (the last heart)
    fbs = play(pg, [["yes"], ["no", "yes"], ["no", "no", "no"], ["yes"], ["yes"], ["no", "yes"]])
    check("yes to the first offer of tea is too quick", "Too quick!" in fbs[0], fbs[0])
    check("taking the vase: it was only taarof", "only taarof" in fbs[1], fbs[1])
    check("three no's to Grandma: she fills the plate anyway", "Too many no's!" in fbs[2] and "Nobody says no to Grandma" in fbs[2], fbs[2])
    check("taking the tahdig without offering costs the last heart, and the evening stops there", len(fbs) == 4 and "without offering" in fbs[3] and "last heart" in fbs[3], fbs)
    end = pg.inner_text("#exBox")
    check("the end card: out of hearts, 3 of 14, a Tourist, with what they said", "Tourist" in end and "3 of 14 points" in end and "calling your mom" in end and "AFTER YOU LEFT" in end.upper() and "learnalefba.com/mehmuni" in end, end)
    check("three things said, the slips first", pg.locator("#nightCard .tc-said li").count() == 3 and "tea" in pg.inner_text("#nightCard .tc-said"), pg.inner_text("#nightCard .tc-said"))
    card = pg.evaluate("(() => { const c = document.getElementById('nightCard'), r = c.getBoundingClientRect(), b = document.getElementById('lessonBody').getBoundingClientRect(); return [c.scrollWidth <= c.clientWidth + 1, r.left >= b.left - 1 && r.right <= b.right + 1]; })()")
    check("the card fits the screen's width", all(card), card)
    pg.screenshot(path=SHOT + "night_end.png")
    pg.click("#taarofShare"); pg.wait_for_timeout(200); sh = pg.evaluate("window.__shared")
    check("Challenge a friend: squares (white for the stops not reached), the rank and the short link", sh and "🟩🟥🟥🟨🟥⬜⬜" in sh["text"] and "Tourist" in sh["text"] and sh["url"] == "https://learnalefba.com/mehmuni", sh)
    pg.click("#mainBtn"); pg.wait_for_timeout(500)
    check("the evening counts as done", pg.evaluate("!!S.done['taarof-night']"))
    check("no page errors", not errs, errs); c.close()
    # a perfect evening
    c, pg, errs, _ = page(b, st())
    pg.evaluate("openLesson(LESSONS.find(l => l.id === 'taarof-night'))"); pg.wait_for_timeout(400); pg.click("#mainBtn"); pg.wait_for_timeout(300)
    fbs = play(pg, PERFECT); end = pg.inner_text("#exBox")
    check("a perfect evening: seven stops, every one just right", len(fbs) == 7 and all(any(h in f for h in GOOD) for f in fbs), fbs)
    check("14 of 14 is a Taarof master with all three hearts, and nothing to play again for", "Taarof master" in end and "14 of 14 points" in end and "❤️❤️❤️" in end and "Play again" not in end and "calling your mom" not in end, end)
    check("every line of the evening is in the list of sounds", pg.evaluate("(() => { const all = new Set(allSounds().map(a => a.file)); return nightLines().every(t => all.has(lineAudio(t).file)); })()"))
    check("no page errors (perfect)", not errs, errs); c.close()
    # a wide screen: the card stays a card
    c = b.new_context(viewport={"width": 1280, "height": 800}); c.add_init_script("try { localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(st())) + ") } catch (e) {}")
    pg = c.new_page(); pg.goto(URL); pg.wait_for_timeout(1300)
    pg.evaluate("openLesson(LESSONS.find(l => l.id === 'taarof-night'))"); pg.wait_for_timeout(400); pg.click("#mainBtn"); pg.wait_for_timeout(300)
    w = pg.evaluate("document.getElementById('nightScene').getBoundingClientRect().width")
    check("on a computer the card isn't stretched across the screen", w <= 460, w); pg.screenshot(path=SHOT + "night_wide.png"); c.close()
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
