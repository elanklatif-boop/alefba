# The Taarof pack: its card, words, the taarof game (meter, why for each answer, end card), the story and the talks.
import json, sys
from playwright.sync_api import sync_playwright
SHOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/"
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3, "prices": {"basic": "$5", "unlimited": "$6.49", "yearly": "$39"}}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def st(adult=False, order="letters"):
    return {"done": {"a1-1": True}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": order}, "log": {}, "speak": 1, "read": 1,
            "profile": {"name": "Sara", "goal": 2, "adult": adult, "speakSelf": 1, "readSelf": 1, "reasons": []}}
def page(b, state, dark=False):
    c = b.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark" if dark else "light", device_scale_factor=2)
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1300)
    return c, pg, errs
with sync_playwright() as p:
    b = p.chromium.launch()
    for dark in (False, True):
        c, pg, errs = page(b, st(), dark)
        tag = "dark" if dark else "light"
        pg.evaluate("document.getElementById('pack-taarof').scrollIntoView()"); pg.wait_for_timeout(200)
        card = pg.inner_text("#pack-taarof")
        if not dark:
            check("the Taarof card shows on the Lessons tab", "Taarof" in card and "Taarof game" in card and "persian manners" in card.lower(), card)
            check("its talks are in the card, with a lock for a free family", pg.is_visible("#pack-taarof #step-s-tea-pack.locked") and pg.evaluate("document.querySelectorAll('[id=step-s-tea]').length") == 1)
            order = pg.evaluate("[...document.querySelectorAll('#view-lessons > section')].map(s => s.id || s.className)")
            check("in November the packs come first (Yalda season), Taarof with them", order[0] == "seasonPart", order)
        pg.locator("#pack-taarof").screenshot(path=f"{SHOT}taarof_card_{tag}.png")
        pg.click("#step-taarof-game"); pg.wait_for_timeout(400)
        check("the game opens with what taarof is", "What is taarof?" in pg.inner_text("#exBox"))
        pg.click("#mainBtn"); pg.wait_for_timeout(150); pg.click("#mainBtn"); pg.wait_for_timeout(300)
        check("then the first scene, with the meter at 0 of 12", "Tea at Auntie's" in pg.inner_text("#exBox") and "0 of 12" in pg.inner_text("#taarofMeter"), pg.inner_text("#exBox"))
        pg.screenshot(path=f"{SHOT}taarof_scene_{tag}.png")
        # first turn wrong, the rest right
        wrong = pg.evaluate("current().opts.findIndex(o => !o.ok)"); pg.click(f"#opt-{wrong}"); pg.wait_for_timeout(250)
        fb = pg.inner_text("#feedback")
        check("a wrong answer says why, and shows what to say", "Not quite" in fb and "zahmat nakeshid" in fb, fb)
        pg.screenshot(path=f"{SHOT}taarof_wrong_{tag}.png")
        pg.click("#mainBtn"); pg.wait_for_timeout(200)
        for k in range(11):
            r = pg.evaluate("current().opts.findIndex(o => o.ok)"); pg.click(f"#opt-{r}"); pg.wait_for_timeout(120)
            if k == 0: check("a right answer fills the meter", "1 of 12" in pg.inner_text("#taarofMeter"))
            if k == 7 and not dark: pg.screenshot(path=f"{SHOT}taarof_taxi_{tag}.png")
            pg.click("#mainBtn"); pg.wait_for_timeout(150)
        end = pg.inner_text("#exBox")
        check("the end card: 11 of 12 is Grandma's favorite", "Grandma's favorite" in end and "11 of 12" in end and "aziz-e mâmân bozorg" in end, end)
        check("the card carries the short link, for a screenshot", "learnalefba.com/taarof" in pg.inner_text("#taarofCard") and "move up a rank" in end, end)
        ranks = pg.evaluate("[12, 11, 10, 9, 7, 6, 4, 3, 0].map(k => taarofRank(k, 12).title)")
        check("five ranks, from Tourist to Taarof master", ranks == ["Taarof master", "Grandma's favorite", "Grandma's favorite", "Good guest", "Good guest", "Hungry guest", "Hungry guest", "Tourist", "Tourist"], ranks)
        card = pg.evaluate("(() => { const c = document.getElementById('taarofCard'), r = c.getBoundingClientRect(), b = document.getElementById('lessonBody').getBoundingClientRect(); return [r.width, r.height, c.scrollWidth <= c.clientWidth + 1, r.left >= b.left - 1 && r.right <= b.right + 1]; })()")
        check("the card fits the screen's width", card[2] and card[3] and card[0] > 200, card)
        pg.screenshot(path=f"{SHOT}taarof_end_{tag}.png")
        pg.click("#mainBtn"); pg.wait_for_timeout(400)
        check("the game counts as done", pg.evaluate("!!S.done['taarof-game']"))
        check("no page errors", not errs, errs); c.close()
    # words, story, talks
    c, pg, errs = page(b, st())
    pg.evaluate("startLesson(LESSONS.find(l => l.id === 'taarof-1'))"); pg.wait_for_timeout(400)
    check("the words lesson starts", pg.is_visible("#exBox"))
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    pg.evaluate("startLesson(LESSONS.find(l => l.id === 'taarof-story'))"); pg.wait_for_timeout(500)
    t = pg.inner_text("#exBox")
    check("the story Who pays? has Uncle and Dad speaking", "Uncle" in t and "Dad" in t and "حساب با منه" in t, t[:300])
    untapped = pg.evaluate("""(() => { const st = SEASON_PACKS.find(p => p.id === 'taarof').story; const out = [];
      st.lines.forEach(l => l.fa.split(' ').forEach(tok => { const core = STORY_PUNCT.exec(tok)[2]; if (core && !storyGloss(st, core) && !['سارا','نیما'].includes(core)) out.push(core); })); return out; })()""")
    check("every word in the story can be tapped for its meaning", not untapped, untapped)
    pg.screenshot(path=f"{SHOT}taarof_story.png")
    pg.evaluate("closeLesson()")
    talks = pg.evaluate("CONVS.filter(c => ['s-tea','s-bill','s-fare'].includes(c.id)).map(c => c.id + ':' + c.level.index)")
    check("three taarof talks in Level 12", talks == ["s-tea:11", "s-bill:11", "s-fare:11"], talks)
    pg.evaluate("showView('games')"); pg.wait_for_timeout(300)
    check("the Games tab has the taarof game", "The taarof game" in pg.inner_text("#gw-taarof"))
    pg.click("#gw-taarof"); pg.wait_for_timeout(300)
    check("and it opens it", "What is taarof?" in pg.inner_text("#exBox"))
    check("no page errors (words, story, games)", not errs, errs); c.close()
    c, pg, errs = page(b, st(adult=True))
    talks = pg.evaluate("SEASON_PACKS.find(p => p.id === 'taarof').lessons.filter(l => l.packTalk).map(l => l.id)")
    check("teens and adults get their own taarof talks in the pack", talks == ["s-a-tea", "s-a-bill", "s-a-fare"], talks)
    check("no page errors (adult)", not errs, errs); c.close()
    # the English switch
    c, pg, errs = page(b, st())
    pg.evaluate("openLesson(LESSONS.find(l => l.id === 'taarof-game'))"); pg.wait_for_timeout(300); pg.click("#mainBtn"); pg.wait_for_timeout(150); pg.click("#mainBtn"); pg.wait_for_timeout(300)
    en = pg.evaluate("current().opts[0].en")
    check("the English switch is there, and off to begin with", pg.get_attribute("#togTaEn", "aria-pressed") == "false")
    check("off: no English under the answers or the line, Finglish stays", en not in pg.inner_text("#opt-0") and pg.evaluate("current().opts[0].tr") in pg.inner_text("#opt-0") and not pg.is_visible("#exBox .tl-en") and pg.is_visible("#exBox .tl-tr"), pg.inner_text("#opt-0"))
    box = pg.evaluate("(() => { const r = document.getElementById('togTaEn').getBoundingClientRect(); return [r.width, r.height]; })()")
    check("it's big enough to tap", box[1] >= 36, box)
    pg.screenshot(path=f"{SHOT}taarof_en_off.png")
    r = pg.evaluate("current().opts.findIndex(o => o.ok)"); pg.click(f"#opt-{r}"); pg.wait_for_timeout(200)
    check("after answering, the English shows what each one meant", en in pg.inner_text("#opt-0") and pg.is_visible("#exBox .tl-en"))
    pg.screenshot(path=f"{SHOT}taarof_en_after.png")
    pg.click("#mainBtn"); pg.wait_for_timeout(250)
    check("the next question is still without English", pg.get_attribute("#togTaEn", "aria-pressed") == "false" and pg.evaluate("current().opts[0].en") not in pg.inner_text("#opt-0"))
    pg.click("#togTaEn"); pg.wait_for_timeout(150)
    check("turned on: English under the answers and the line, and the choice is saved", pg.get_attribute("#togTaEn", "aria-pressed") == "true" and pg.evaluate("current().opts[0].en") in pg.inner_text("#opt-0") and pg.is_visible("#exBox .tl-en") and pg.evaluate("JSON.parse(localStorage.getItem('alefba-v3')).prefs.taEn") is True)
    pg.screenshot(path=f"{SHOT}taarof_en_on.png")
    r = pg.evaluate("current().opts.findIndex(o => o.ok)"); pg.click(f"#opt-{r}"); pg.wait_for_timeout(150); pg.click("#mainBtn"); pg.wait_for_timeout(250)
    check("and it stays on for the next question", pg.get_attribute("#togTaEn", "aria-pressed") == "true" and pg.evaluate("current().opts[0].en") in pg.inner_text("#opt-0"))
    pg.click("#togTaEn"); pg.wait_for_timeout(150)
    check("off again", pg.evaluate("current().opts[0].en") not in pg.inner_text("#opt-0") and pg.evaluate("JSON.parse(localStorage.getItem('alefba-v3')).prefs.taEn") is False)
    check("no page errors (English switch)", not errs, errs); c.close()
    # a family with a plan: the pack's talks open, and finishing the four free lessons finishes the pack
    PAID = dict(FREE, signedIn=True, kind="unlimited", plan="yearly", left=30, today=30)
    c = b.new_context(viewport={"width": 390, "height": 844})
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(dict(st(), done={"a1-1": True, "taarof-1": True, "taarof-2": True, "taarof-game": True, "taarof-night": True}))) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(PAID)))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1300)
    check("with a plan the pack's talks aren't locked", pg.evaluate("!document.querySelector('#step-s-tea-pack').classList.contains('locked')"))
    pg.evaluate("document.querySelector('#step-s-tea-pack').click()"); pg.wait_for_timeout(500)
    t = pg.evaluate("document.getElementById('talkName').innerText + ' | ' + document.getElementById('chat').innerText")
    check("and one opens: Khale Shirin, with its goals", "Khale Shirin" in t and "Politely say no the first time" in t, t[:200])
    pg.evaluate("closeTalk && closeTalk()") if pg.evaluate("typeof closeTalk === 'function'") else None
    pg.evaluate("startLesson(LESSONS.find(l => l.id === 'taarof-story'))"); pg.wait_for_timeout(400)
    for _ in range(12):
        if pg.evaluate("!R || !!R.finish"): break
        e = pg.evaluate("(() => { const e = current(); return { type: e.type, answer: e.answer }; })()")
        if e["type"] == "choice": pg.click(f"#opt-{e['answer']}"); pg.wait_for_timeout(120)
        pg.click("#mainBtn"); pg.wait_for_timeout(200)
    check("the story finishes the pack, without the talks", pg.is_visible("#levelDone") and "Taarof finished" in pg.inner_text("#levelDone"), pg.inner_text("#exBox")[:200])
    check("no page errors (plan)", not errs, errs); c.close()
    b.close()
print(f"{sum(res)} of {len(res)} passed")
