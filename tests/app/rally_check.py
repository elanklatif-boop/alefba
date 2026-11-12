# Taarof rally: the arcade game. Auntie offers, a cup slides toward you, and you answer with a polite reply you haven't just used.
import json, sys
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8811/"; SHOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/"
passed = failed = 0
def check(name, ok, info=""):
    global passed, failed
    if ok: passed += 1; print("PASS", name)
    else: failed += 1; print("FAIL", name, info)
def st(best=None):
    s = {"done": {"a1-1": True}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 1, "read": 1,
         "profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
    if best is not None: s["prefs"]["rallyBest"] = best
    return s
def page(b, state, clocks=False):
    c = b.new_context(viewport={"width": 390, "height": 780})
    c.add_init_script("try { if (!localStorage.getItem('alefba-v3')) localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") } catch (e) {}")
    c.add_init_script("window.__shared = null; navigator.share = async d => { window.__shared = d; };")
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(1300)
    if not clocks: pg.evaluate("RALLY_AUTO = false")
    pg.evaluate("openLesson(LESSONS.find(l => l.id === 'taarof-rally'))"); pg.wait_for_timeout(400)
    return c, pg, errs
def good(pg): return pg.evaluate("R.rally.opts.findIndex(o => o.ok)")
def hit(pg, n=1):
    for _ in range(n): pg.click(f"#rally-{good(pg)}"); pg.wait_for_timeout(60); pg.evaluate("rallyHost()"); pg.wait_for_timeout(60)
with sync_playwright() as p:
    b = p.chromium.launch()
    c, pg, errs = page(b, st())
    ids = pg.evaluate("SEASON_PACKS.find(p => p.id === 'taarof').lessons.filter(l => !l.packTalk).map(l => l.id)")
    check("the pack has the rally after the quiz", ids == ["taarof-1", "taarof-2", "taarof-game", "taarof-rally", "taarof-story"], ids)
    intro = pg.inner_text("#exBox")
    check("it opens on how to play, with the six polite replies to hear", "Keep the taarof going!" in intro and pg.locator(".rally-list .rl-row").count() == 6 and pg.locator(".rally-list .rl-play").count() == 6 and "zahmat nakeshid" in intro and "please don't go to any trouble" in intro, intro[:200])
    check("in the game the meanings are a few words each", pg.evaluate("rallyPolite().concat(rallyHosts()).every(w => w.en.length <= 30 && w.en !== w.full)"))
    check("every sound in the game is a family recording", pg.evaluate("rallyPolite().concat(rallyHosts()).every(w => isReal(w.audio))"), pg.evaluate("rallyPolite().concat(rallyHosts()).filter(w => !isReal(w.audio)).map(w => w.tr)"))
    pg.click("#mainBtn"); pg.wait_for_timeout(300)
    check("the game: Auntie has spoken, four answers, no Continue", pg.locator("#rallyOpts .opt").count() == 4 and pg.inner_text("#rallyHost").strip() != "" and not pg.is_visible("#mainBtn") and pg.inner_text("#rallyScore") == "0")
    o = pg.evaluate("R.rally.opts.map(x => [!!x.ok, !!x.trap, !!x.blunt])")
    check("first turn: one polite reply and three blunt ones", sum(x[0] for x in o) == 1 and sum(x[2] for x in o) == 3, o)
    shown = pg.inner_text("#rallyOpts") + pg.inner_text("#rallyHost")
    check("no English on what's said or the answers", not any(w in shown for w in ["hurry", "I said no", "Eat it", "tasty", "Leave me", "trouble", "Enjoy", "nothing", "too kind", "shy", "impose", "Thank you"]), shown)
    pg.click("#togTaEn"); check("the English switch shows it", pg.is_visible("#rallyOpts .tl-en")); pg.click("#togTaEn"); check("and hides it again", not pg.is_visible("#rallyOpts .tl-en"))
    first = pg.evaluate("R.rally.opts.find(o => o.ok).key"); host1 = pg.evaluate("R.rally.host.key")
    pg.click(f"#rally-{good(pg)}"); pg.wait_for_timeout(100)
    check("a polite reply: 1 in a row, and it shows as what you said", pg.inner_text("#rallyScore") == "1" and pg.inner_text("#rallyYou").strip() != "" and pg.evaluate("R.rally.wait"))
    pg.evaluate("rallyHost()"); pg.wait_for_timeout(100)
    o = pg.evaluate("R.rally.opts.map(x => [x.key || '', !!x.ok, !!x.trap])")
    check("next turn: Auntie says something else, and the reply just used is there as a trap", pg.evaluate("R.rally.host.key") != host1 and any(x[0] == first and x[2] for x in o) and sum(x[1] for x in o) == 1, o)
    pg.keyboard.press(str(good(pg) + 1)); pg.wait_for_timeout(100)
    check("the number keys answer too", pg.inner_text("#rallyScore") == "2")
    pg.evaluate("rallyHost()"); pg.wait_for_timeout(100)
    trap = pg.evaluate("R.rally.opts.findIndex(o => o.trap)"); pg.click(f"#rally-{trap}"); pg.wait_for_timeout(200)
    fb = pg.inner_text("#feedback"); card = pg.inner_text("#rallyCard")
    check("repeating yourself spills the tea, and says which reply was free", "The tea spilled!" in fb and "just said" in fb and "was free" in fb, fb)
    check("the card: 2 times in a row, a rank, a new best and the link", "2" in card and "times in a row" in card and "Tourist" in card and "New best!" in card and "learnalefba.com/taarof" in card, card)
    check("the best score is kept", pg.evaluate("S.prefs.rallyBest") == 2 and pg.evaluate("JSON.parse(localStorage.getItem('alefba-v3')).prefs.rallyBest") == 2)
    check("the English shows once it's over, and Continue is there", pg.is_visible("#rallyOpts .tl-en") and pg.is_enabled("#mainBtn"))
    pg.click("#taarofShare"); pg.wait_for_timeout(150); sh = pg.evaluate("window.__shared")
    check("Challenge a friend: the score, the rank and the short link", sh and "2 times in a row" in sh["text"] and "Tourist" in sh["text"] and sh["url"] == "https://learnalefba.com/taarof", sh)
    pg.click("#rallyAgain"); pg.wait_for_timeout(300)
    check("Play again starts over, with the best score shown", pg.inner_text("#rallyScore") == "0" and "Best 2" in pg.inner_text(".rally-best") and pg.locator("#rallyEnd").count() == 0 and not pg.is_visible("#mainBtn"))
    bl = pg.evaluate("R.rally.opts.findIndex(o => o.blunt)"); word = pg.evaluate(f"R.rally.opts[{bl}].en"); pg.click(f"#rally-{bl}"); pg.wait_for_timeout(200)
    fb = pg.inner_text("#feedback"); card = pg.inner_text("#rallyCard")
    check("a blunt answer spills it and says what it meant", "blunt" in fb and word in fb, fb)
    check("0 in a row doesn't beat the best", "Best: 2" in card and "New best" not in card, card)
    pg.click("#rallyAgain"); pg.wait_for_timeout(300); hit(pg, 10)
    o = pg.evaluate("R.rally.opts.map(x => !!x.trap)")
    check("from 10 in a row the last two replies are both out", pg.inner_text("#rallyScore") == "10" and sum(o) == 2 and len(o) == 4, o)
    hit(pg, 10)
    check("from 20 there are six answers", pg.inner_text("#rallyScore") == "20" and pg.locator("#rallyOpts .opt").count() == 6)
    check("it gets faster, down to a floor", pg.evaluate("[rallyTime(0), rallyTime(5), rallyTime(60)]") == [6500, 4770, 1800], pg.evaluate("[rallyTime(0), rallyTime(5), rallyTime(60)]"))
    pg.evaluate("rallyOver('slow')"); pg.wait_for_timeout(200); card = pg.inner_text("#rallyCard")
    check("too slow ends it too; 20 is a Taarof master", "Too slow!" in pg.inner_text("#feedback") and "Taarof master" in card and "20" in card, card)
    fit = pg.evaluate("(() => { const c = document.getElementById('rallyCard'), r = c.getBoundingClientRect(), b = document.getElementById('lessonBody').getBoundingClientRect(); return [c.scrollWidth <= c.clientWidth + 1, r.left >= b.left - 1 && r.right <= b.right + 1]; })()")
    check("the card fits the screen's width", all(fit), fit); pg.screenshot(path=SHOT + "rally_end.png")
    pg.click("#mainBtn"); pg.wait_for_timeout(500)
    check("Continue finishes it, and it counts as done", pg.evaluate("!!S.done['taarof-rally']"))
    check("no page errors", not errs, errs); c.close()
    # with the clocks on: the cup arrives by itself, and a reply brings Auntie's next line by itself
    c, pg, errs = page(b, st(), clocks=True)
    pg.evaluate("RALLY_START = 900; RALLY_FLOOR = 700"); pg.click("#mainBtn"); pg.wait_for_timeout(250)
    turn = pg.evaluate("R.rally.turn"); pg.click(f"#rally-{good(pg)}"); pg.wait_for_timeout(2600)
    check("after a reply, Auntie goes again by herself", pg.evaluate("R.rally.score") == 1 and (pg.evaluate("R.rally.turn") > turn + 1 or pg.evaluate("R.rally.over")))
    pg.wait_for_timeout(1500)
    check("a cup that isn't answered spills by itself", pg.evaluate("R.rally.over") and "Too slow!" in pg.inner_text("#feedback"), pg.inner_text("#feedback"))
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(1500)
    check("no page errors (clocks, and closing mid-game)", not errs, errs); c.close()
    # the Games tab
    c, pg, errs = page(b, st(7)); pg.evaluate("closeLesson()"); pg.wait_for_timeout(300)
    pg.evaluate("document.getElementById('tab-games').click()"); pg.wait_for_timeout(400)
    row = pg.inner_text("#gw-rally") if pg.locator("#gw-rally").count() else ""
    check("the Games tab has a row for the rally, with your best", "Taarof rally" in row and "Your best: 7" in row, row)
    c.close(); b.close()
print(f"{passed} of {passed + failed} passed"); sys.exit(1 if failed else 0)
