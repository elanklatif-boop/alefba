import json, datetime
from playwright.sync_api import sync_playwright
SHOT = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec29/"
URL = "http://127.0.0.1:8811/"
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3, "prices": {"basic": "$4.99", "unlimited": "$6.49", "yearly": "$39"}}
res = []
def check(n, ok, x=""): res.append(ok); print("PASS" if ok else "FAIL", n, "" if ok else x)
def st(lang="en", done=None, order="letters", adult=False):
    return {"done": done or {"a1-1": True}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": lang, "fing": "auto", "order": order}, "log": {}, "speak": 1, "read": 1,
            "profile": {"name": "Sara", "goal": 2, "adult": adult, "speakSelf": 1, "readSelf": 1, "reasons": []}}
def page(b, state, when=None, width=390, dark=False):
    c = b.new_context(viewport={"width": width, "height": 844}, color_scheme="dark" if dark else "light")
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x) + " " + (x.stack or "")[:600]))
    if when: pg.clock.set_fixed_time(when)
    pg.goto(URL); pg.wait_for_timeout(1300)
    return c, pg, errs
def finish(pg, n=160):
    for _ in range(n):
        if pg.evaluate("!R || !!R.finish"): return True
        e = pg.evaluate("(() => { const e = current(); return e && { type: e.type, answer: e.answer, n: e.pairs ? e.pairs.length : 0 }; })()")
        t = e and e["type"]
        if t == "choice": pg.click(f"#opt-{e['answer']}")
        elif t == "match":
            for i in range(e["n"]):
                pg.click(f"#exBox .mitem[data-side='l'][data-i='{i}']"); pg.click(f"#exBox .mitem[data-side='r'][data-i='{i}']")
        elif t == "spell":
            tiles = pg.evaluate("(() => { const e = current(); const used = []; return e.target.map(g => { const i = e.tiles.findIndex((t, k) => t === g && !used.includes(k)); used.push(i); return i; }); })()")
            for i in tiles: pg.click(f"#tile-{i}")
            pg.click("#mainBtn"); pg.wait_for_timeout(80)
        elif t == "trace": pg.click("#traceSkip"); pg.wait_for_timeout(80); continue
        elif pg.is_visible("#idkBtn"): pg.click("#idkBtn")
        pg.wait_for_timeout(60)
        if pg.is_visible("#mainBtn") and pg.is_enabled("#mainBtn"): pg.click("#mainBtn")
        elif pg.is_visible("#skipBtn"): pg.click("#skipBtn")
        pg.wait_for_timeout(80)
    return pg.evaluate("!R || !!R.finish")
with sync_playwright() as p:
    b = p.chromium.launch()
    # ----- outside the season (today, 29 October): the pack is at the end, free -----
    c, pg, errs = page(b, st(), when=datetime.datetime(2026, 10, 29, 12))
    pk = pg.evaluate("SEASON_PACKS.map(p => ({ id: p.id, words: p.words.map(W => W.tr), lessons: p.lessons.map(l => l.id) }))")
    check(f"two packs, Yalda first, with 15 words and 4 lessons ({pk})", [x["id"] for x in pk] == ["yalda", "taarof"] and len(pk[0]["words"]) == 15 and pk[0]["lessons"] == ["yalda-1", "yalda-2", "yalda-game", "yalda-story"])
    check("words shared with Level 14 are the same words, not copies", pg.evaluate("SEASON_PACKS[0].words.filter(W => WORDS.includes(W)).map(W => W.tr).sort().join()") == "anâr,fâl-e hâfez,hendevâne,shab-e yaldâ")
    check("the 252 words and 16 levels are unchanged", pg.evaluate("[WORDS.length, LEVELS.length]") == [252, 16])
    check("signed out, with no plan: every pack lesson is open, Level 5 is still locked", pg.evaluate("SEASON_PACKS[0].lessons.every(l => !lessonLocked(l)) && lessonLocked(LESSONS.find(l => l.id === 'w5-1'))"))
    order = pg.evaluate("[...document.querySelectorAll('#view-lessons > .part')].map(p => p.id || p.querySelector('h2').textContent)")
    check(f"in October the Celebrations part is last ({order})", order[-1] == "seasonPart")
    check("the card says it's free and when Yalda is", "free for everyone · around 21 december" in pg.inner_text("#pack-yalda").lower() and "0 of 4 done" in pg.inner_text("#pack-yalda"))
    check("Up next doesn't jump to the pack", not pg.evaluate("nextLesson().level && nextLesson().level.season"))
    check("the plan's estimate leaves the pack out", pg.evaluate("pathLessons().every(l => !(l.level && l.level.season))"))
    c.close()
    # ----- in season: first -----
    c, pg, errs = page(b, st(), when=datetime.datetime(2026, 12, 5, 12))
    order = pg.evaluate("[...document.querySelectorAll('#view-lessons > .part')].map(p => p.id || p.querySelector('h2').textContent)")
    check(f"in December it comes first ({order})", order[0] == "seasonPart")
    check("inSeason wraps the new year: 5 Jan yes, 11 Jan no, 1 Nov yes, 31 Oct no", pg.evaluate("[new Date(2027,0,5), new Date(2027,0,11), new Date(2026,10,1), new Date(2026,9,31)].map(d => inSeason(SEASON_PACKS[0], d))") == [True, False, True, False])
    pg.locator("#pack-yalda").scroll_into_view_if_needed(); pg.screenshot(path=SHOT + "yalda_card.png")
    # first words lesson
    pg.click("#step-yalda-1"); pg.wait_for_timeout(400)
    first = pg.evaluate("current().type + ':' + (current().W ? current().W.tr : '')")
    check(f"Words 1 opens, starting with shab-e yaldâ ({first})", pg.is_visible("#lesson") and first == "introWord:shab-e yaldâ")
    pg.screenshot(path=SHOT + "yalda_word.png")
    check("and finishes", finish(pg) and pg.evaluate("S.done['yalda-1']") is True, pg.evaluate("current() && current().type"))
    check("no 'Level 100' anywhere on the finish screen", "Level 100" not in pg.inner_text("#exBox"))
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    pg.click("#step-yalda-2"); pg.wait_for_timeout(400)
    check("Words 2 (divân-e hâfez, dur-e ham...) opens and finishes", finish(pg) and pg.evaluate("S.done['yalda-2']") is True, pg.evaluate("current() && current().type"))
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    # zemestân has its everyday form
    check("zemestân is said zemestun (book vs everyday)", pg.evaluate("ALL_WORDS().find(W => W.tr === 'zemestân').two.said.tr") == "zemestun")
    # the meaning in another language, and a sentence
    pg.evaluate("S.prefs.lang = 'de'; applyLang()")
    check("meanings in German (âjil) and its sentence", pg.evaluate("[ALL_WORDS().find(W => W.tr === 'âjil').m, ALL_WORDS().find(W => W.tr === 'âjil').sentence.m]") == ["Nüsse und Trockenfrüchte", "Gib mir bitte die Nüsse!"])
    pg.evaluate("S.prefs.lang = 'en'; applyLang()")
    # missed words come back in review, from the pack
    pg.evaluate("S.items['word:khormâlu'] = { r: 0, w: 2, wrong: 2 }; save(); renderAll()")
    ex = pg.evaluate("(() => { const e = exForKey('word:khormâlu'); return e && e.type; })()")
    check(f"a missed pack word makes a review question ({ex})", ex is not None)
    # the story
    pg.click("#tab-lessons"); pg.wait_for_timeout(200)
    pg.click("#step-yalda-story"); pg.wait_for_timeout(400)
    check("the story opens with 11 lines", pg.evaluate("current().type") == "story" and pg.evaluate("document.querySelectorAll('#exBox .story-line').length") == 11)
    pg.locator("#exBox .sw", has_text="خرمالو").first.click(); pg.wait_for_timeout(100)
    check("tapping خرمالو shows persimmon", "persimmon" in pg.inner_text("#storyGloss"))
    words = pg.evaluate("[...document.querySelectorAll('#exBox .sw')].map(e => e.textContent)")
    gl = pg.evaluate("[...document.querySelectorAll('#exBox .sw')].filter(e => !e.classList.contains('nog')).length")
    pg.screenshot(path=SHOT + "yalda_story.png")
    check("and finishes after its 3 questions", finish(pg) and pg.evaluate("S.done['yalda-story']") is True)
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    # the game
    pg.click("#step-yalda-game"); pg.wait_for_timeout(500)
    check("the game opens with the pack's pictures", pg.is_visible("#lesson") or pg.is_visible("#game"), pg.inner_text("body")[:200])
    pg.screenshot(path=SHOT + "yalda_game.png")
    pg.keyboard.press("Escape"); pg.evaluate("typeof closeLesson === 'function' && closeLesson()"); pg.wait_for_timeout(200)
    check("no page errors (in season)", not errs, errs)
    c.close()
    # ----- teacher picker -----
    c, pg, errs = page(b, st(adult=True))
    ok = pg.evaluate("(() => { try { $('teach').hidden = false; TEACH.cur = { id: 'c1', name: 'x', assigned: [] }; teachAssign(); return true } catch (e) { return String(e) } })()")
    pg.wait_for_timeout(300)
    check(f"teachers see the pack in the lesson picker ({ok})", pg.query_selector("#pickall-yalda") is not None and pg.query_selector("#pk-yalda-story") is not None)
    check("an assigned pack lesson has a clear name", pg.evaluate("lessonLabelById('yalda-story')") == "Shab-e Yalda: Story")
    check("no page errors (teacher)", not errs, errs); c.close()
    # ----- talk-first, French, dark, desktop -----
    c, pg, errs = page(b, st(lang="fr", order="talk"), when=datetime.datetime(2026, 12, 20, 12), width=1280, dark=True)
    check("talk-first path: the pack still shows, first in December", pg.evaluate("document.querySelector('#view-lessons > .part').id") == "seasonPart")
    pg.screenshot(path=SHOT + "yalda_desktop_dark.png")
    check("no sideways scrolling", not pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
    check("no page errors (desktop)", not errs, errs); c.close()
    b.close()
print(f"{sum(res)}/{len(res)} passed")
