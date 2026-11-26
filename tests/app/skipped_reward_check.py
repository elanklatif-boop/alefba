# After the level check skips Level 1's words (and the letters), finishing a letter lesson must not pop up
# "Elan finished Level 1: Hello!" with a share card: that level wasn't finished, it was skipped. Doing a real
# lesson in Level 1 later still gives its sticker and the share button.
import json, sys
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8811/"
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
OK = []
def check(n, ok, x=""): OK.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def st(done):
    return {"done": done, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 1, "read": 1,
            "profile": {"name": "Elan", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
def page(b, state):
    c = b.new_context(viewport={"width": 390, "height": 844})
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto(URL); pg.wait_for_timeout(1200)
    return c, pg, errs
def finish(pg):
    for _ in range(200):
        e = pg.evaluate("(() => { const e = current(); return e && { type: e.type, answer: e.answer, n: e.pairs ? e.pairs.length : 0 }; })()")
        if not e: break
        t = e["type"]
        if t == "choice": pg.click(f"#opt-{e['answer']}")
        elif t == "match":
            for i in range(e["n"]): pg.click(f"#exBox .mitem[data-side='l'][data-i='{i}']"); pg.click(f"#exBox .mitem[data-side='r'][data-i='{i}']")
        elif t == "spell":
            tiles = pg.evaluate("(() => { const e = current(); const used = []; return e.target.map(g => { const i = e.tiles.findIndex((t, k) => t === g && !used.includes(k)); used.push(i); return i; }); })()")
            for i in tiles:
                if pg.evaluate("R.phase === 'answer'"): pg.evaluate(f"tapTile({i})")
        elif t == "trace": pg.click("#traceSkip"); pg.wait_for_timeout(60); continue
        elif pg.is_visible("#idkBtn"): pg.click("#idkBtn")
        pg.wait_for_timeout(50)
        if pg.is_visible("#mainBtn") and pg.is_enabled("#mainBtn"): pg.click("#mainBtn")
        elif pg.is_visible("#skipBtn"): pg.click("#skipBtn")
        pg.wait_for_timeout(70)
    return pg.evaluate("!R || !!R.finish")
with sync_playwright() as p:
    b = p.chromium.launch()
    c, pg, errs = page(b, st({}))
    ids = pg.evaluate("""({ lv1: wordLessons(LEVELS[0]).map(l => l.id), lv2: wordLessons(LEVELS[1]).map(l => l.id),
                          letters: LESSONS.filter(l => /^a\\d+-/.test(l.id)).map(l => l.id) })""")
    c.close()
    # the level check skipped Levels 1 and 2 and every letter lesson but the first one (which Elan was a lesson into)
    done = {k: "test" for k in ids["lv1"] + ids["lv2"] + ids["letters"][2:]}; done[ids["letters"][0]] = True
    c, pg, errs = page(b, st(done))
    pg.evaluate(f"startLesson(LESSONS.find(l => l.id === {json.dumps(ids['letters'][1])}))"); pg.wait_for_timeout(300)
    check("a letter lesson finishes", finish(pg))
    txt = pg.inner_text("#exBox") if pg.is_visible("#exBox") else pg.inner_text("body")
    check("no 'Level 1 sticker' pops up for a level the check skipped", "Level 1 sticker" not in txt and "Level 2 sticker" not in txt, txt[:300])
    check("and no share card claiming Level 1 was finished", not pg.is_visible("#shareBtn"))
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(300)
    # then Elan really does a Level 1 words lesson: now the sticker (and share) comes, and it's true
    pg.evaluate(f"startLesson(LESSONS.find(l => l.id === {json.dumps(ids['lv1'][0])}))"); pg.wait_for_timeout(300)
    check("a Level 1 words lesson finishes", finish(pg))
    check("now the Level 1 sticker comes, with the share button", "Level 1 sticker" in pg.inner_text("body") and pg.is_visible("#shareBtn"))
    check("but not Level 2's, still only skipped", "Level 2 sticker" not in pg.inner_text("body"))
    check("no page errors", not errs, errs)
    b.close()
print(f"{sum(OK)}/{len(OK)}")
sys.exit(0 if all(OK) else 1)
