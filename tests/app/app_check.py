import json, re
from playwright.sync_api import sync_playwright
exec(open("rec28tools/yalda_check.py").read().split("with sync_playwright() as p:")[0].split("def page(")[0])
res=[]
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
URL="http://127.0.0.1:8811/"
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
def st(done=None, items=None):
    return {"done": done or {}, "items": items or {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 1, "read": 1,
            "profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
def page(b, state):
    c = b.new_context(viewport={"width": 390, "height": 844})
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto(URL); pg.wait_for_timeout(1300); return c, pg, errs
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---------- earlier words mixed in ----------
    c, pg, errs = page(b, st())
    words = pg.evaluate("WORDS.filter(W => W.level < 2).map(W => W.tr)")
    items = {"word:" + w: {"r": 2, "w": 0} for w in words}
    items["word:" + words[3]] = {"r": 0, "w": 3}; items["spell:" + words[5]] = {"r": 1, "w": 4}
    c.close()
    done = {}
    c, pg, errs = page(b, st(done={"a1-1": True}, items=items))
    pg.evaluate("localStorage.setItem('alefba-install', 'no')") # the home-screen card already said no to, so the calendar reminder is next
    for trial in range(5):
        r = pg.evaluate("""(() => { const l = LESSONS.find(l => l.kind === 'words' && l.level.index === 2); const seq = buildLesson(l);
          const own = new Set(l.words.map(W => W.tr));
          const old = seq.map((e, i) => [i, e]).filter(([i, e]) => { const W = (e.type === 'spell' && e.word) || (e.key ? ALL_WORDS().find(x => x.tr === e.key.split(':')[1]) : null); return e.fromBefore || (W && !own.has(W.tr) && e.type !== 'match'); });
          return { n: seq.length, old: old.map(([i, e]) => [i, e.type, e.key || (e.word && 'spell:' + e.word.tr)]), lesson: [...own] }; })()""")
        if trial == 0: print(r)
        check(f"level 3 lesson: 3 earlier words mixed in ({len(r['old'])})", len(r["old"]) == 3, r)
        check("all in the second half, not at the very end", all(i >= r["n"] // 2 and i < r["n"] - 1 for i, *_ in r["old"]), r)
        if trial == 0:
            keys = " ".join(str(o[2]) for o in r["old"])
            check(f"the missed words come first ({words[3]}, {words[5]})", words[3] in keys and words[5] in keys, keys)
    r = pg.evaluate("(() => { const l = LESSONS.find(l => l.kind === 'words' && l.level.index === 0); return buildLesson(l).filter(e => e.fromBefore).length; })()")
    check("level 1, first lesson: nothing from before", r == 0, r)
    # a whole lesson plays through with them
    pg.evaluate("openLesson(LESSONS.find(l => l.kind === 'words' && l.level.index === 2))"); pg.wait_for_timeout(500)
    seen_label = False
    for _ in range(200):
        if pg.evaluate("!R || !!R.finish"): break
        if "a word from before" in pg.inner_text("#exBox").lower(): seen_label = True
        e = pg.evaluate("(() => { const e = current(); return e && { type: e.type, answer: e.answer, n: e.pairs ? e.pairs.length : 0 }; })()")
        t = e and e["type"]
        if t == "choice": pg.click(f"#opt-{e['answer']}")
        elif t == "match":
            for i in range(e["n"]): pg.click(f"#exBox .mitem[data-side='l'][data-i='{i}']"); pg.click(f"#exBox .mitem[data-side='r'][data-i='{i}']")
        elif t == "spell":
            tiles = pg.evaluate("(() => { const e = current(); const used = []; return e.target.map(g => { const i = e.tiles.findIndex((t, k) => t === g && !used.includes(k)); used.push(i); return i; }); })()")
            for i in tiles: pg.click(f"#tile-{i}")
            pg.click("#mainBtn"); pg.wait_for_timeout(80)
        elif pg.is_visible("#idkBtn"): pg.click("#idkBtn")
        pg.wait_for_timeout(50)
        if pg.is_visible("#mainBtn") and pg.is_enabled("#mainBtn"): pg.click("#mainBtn")
        elif pg.is_visible("#skipBtn"): pg.click("#skipBtn")
        pg.wait_for_timeout(70)
    check("the lesson plays to the end", pg.evaluate("!!(R && R.finish)"))
    check("a 'word from before' question was shown", seen_label)
    # ---------- the reminder: offered once, after the second lesson ----------
    check("after the 2nd lesson the reminder card shows", pg.is_visible("#remindCard"))
    pg.screenshot(path="remind/finish_card.png", full_page=True)
    href = pg.get_attribute("#remindCal", "href"); g = pg.get_attribute("#remindGoogle", "href")
    check(f"calendar link goes to the server file ({href})", re.match(r"^/api/reminder\.ics\?t=1700&d=20\d{6}$", href or ""))
    check("Google link repeats daily at 5pm", "action=TEMPLATE" in g and "RRULE%3AFREQ%3DDAILY" in g and "T170000" in g, g)
    pg.fill("#remindTime", "19:30"); pg.dispatch_event("#remindTime", "change")
    check("changing the time changes the links", "t=1930" in pg.get_attribute("#remindCal", "href") and "T193000" in pg.get_attribute("#remindGoogle", "href"))
    pg.evaluate("document.getElementById('remindGoogle').addEventListener('click', e => e.preventDefault())"); pg.click("#remindGoogle"); pg.wait_for_timeout(500)
    check("choosing saves the time and thanks them", pg.evaluate("S.prefs.remind") == "19:30" and "Reminder set" in pg.inner_text("#remindCard"))
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    pg.evaluate("openLesson(LESSONS.find(l => l.kind === 'words' && l.level.index === 2))"); pg.wait_for_timeout(300)
    pg.evaluate("finishLesson()"); pg.wait_for_timeout(300)
    check("not offered again", not pg.is_visible("#remindCard"))
    pg.evaluate("closeLesson(); showView('review')"); pg.wait_for_timeout(300)
    check("Settings has the reminder with the chosen time", pg.is_visible("#remindRow") and "19:30" in pg.inner_text("#remindRow"), pg.inner_text("#remindRow") if pg.query_selector("#remindRow") else "")
    pg.locator("#remindRow").scroll_into_view_if_needed(); pg.screenshot(path="remind/settings.png")
    check("no page errors", not errs, errs)
    c.close()
    # 'No thanks' removes it and it isn't offered again
    c, pg, errs = page(b, st(done={"a1-1": True, "a1-2": True}))
    pg.evaluate("openLesson(LESSONS.find(l => l.kind === 'words' && l.level.index === 0))"); pg.wait_for_timeout(300); pg.evaluate("finishLesson()"); pg.wait_for_timeout(300)
    check("offered on a later lesson for someone who hasn't seen it", pg.is_visible("#remindCard"))
    pg.click("#remindNo"); pg.wait_for_timeout(200)
    check("No thanks closes it, and it's remembered", not pg.is_visible("#remindCard") and pg.evaluate("S.prefs.remindAsked") is True and not pg.evaluate("S.prefs.remind"))
    c.close()
    # the second lesson, for someone who hasn't said no to the home-screen card: that card first, the calendar later
    c, pg, errs = page(b, st(done={"a1-1": True}))
    pg.evaluate("openLesson(LESSONS.find(l => l.kind === 'words' && l.level.index === 0))"); pg.wait_for_timeout(300); pg.evaluate("finishLesson()"); pg.wait_for_timeout(300)
    check("2nd lesson: the home-screen card, not the calendar yet", pg.evaluate("!!document.querySelector('#exBox #installBanner')") and not pg.is_visible("#remindCard"))
    c.close()
    # first lesson: not offered yet
    c, pg, errs = page(b, st())
    pg.evaluate("openLesson(LESSONS.find(l => l.kind === 'words' && l.level.index === 0))"); pg.wait_for_timeout(300); pg.evaluate("finishLesson()"); pg.wait_for_timeout(300)
    check("not after the very first lesson", not pg.is_visible("#remindCard"))
    c.close(); b.close()
print(f"{sum(res)}/{len(res)} passed")
