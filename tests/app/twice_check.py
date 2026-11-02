import json
from playwright.sync_api import sync_playwright
OUT = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/v70/"
URL = "http://127.0.0.1:8811/"
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def st(done=None):
    return {"done": done or {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 1, "read": 1,
            "profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
def page(b, state):
    c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto(URL); pg.wait_for_timeout(1200); return c, pg, errs
def draw(pg, pts):
    """draw strokes through the points, in reading order of rows (good enough to cover a letter's pixels)"""
    pts = sorted(pts, key=lambda p: (round(p[1] / 6), p[0]))
    prev = None
    for x, y in pts:
        if prev is None or abs(prev[0] - x) > 10 or abs(prev[1] - y) > 10:
            if prev is not None: pg.mouse.up()
            pg.mouse.move(x, y); pg.mouse.down()
        else: pg.mouse.move(x, y)
        prev = (x, y)
    pg.mouse.up()
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---------- building a word twice ----------
    c, pg, errs = page(b, st(done={"a1-1": True}))
    q = pg.evaluate("buildLesson(LESSONS.find(l => l.id === 'w1-1')).map((e, i) => e.type === 'spell' ? { i, w: e.word.tr, stage: e.stage, again: e.again } : null).filter(Boolean)")
    first = [x for x in q if not x["again"]]; again = [x for x in q if x["again"]]
    check(f"each word built in the lesson is built twice ({q})", len(first) >= 2 and sorted(x["w"] for x in first) == sorted(x["w"] for x in again))
    check("the second time comes later in the lesson", min(x["i"] for x in again) > max(x["i"] for x in first) + 2)
    check("first time guided, second time with only the Finglish as a clue", all(x["stage"] == "guided" for x in first) and all(x["stage"] == "finglish" for x in again))
    # play it: the second build has no letter sounds on the tiles and no voice guide
    r = pg.evaluate("""(() => { const W = WORDS.find(W => W.tr === 'salâm'); const ex = exSpell(W, true);
       R = { queue: [ex], pos: 0, mistakes: 0, graded: 0, requeued: 0, phase: 'answer', built: [], missed: [], finish: false }; openOverlay('lesson'); showExercise();
       return { sounds: document.querySelectorAll('#exBox .tsound').length, guide: !!document.getElementById('guide'), sub: document.querySelector('#exBox .ex-sub') ? document.querySelector('#exBox .ex-sub').textContent : '' }; })()""")
    check(f"second build: no sounds under the tiles, no voice naming the letters, just 'Say it: salâm' ({r})", r["sounds"] == 0 and not r["guide"] and r["sub"] == "Say it: salâm")
    pg.screenshot(path=OUT + "spell_again.png")
    # once a word has been built before, the second time in a lesson is just the meaning
    r = pg.evaluate("""(() => { S.items['spell:salâm'] = { r: 1, w: 0 }; const W = WORDS.find(W => W.tr === 'salâm'); return [exSpell(W).stage, exSpell(W, true).stage]; })()""")
    check(f"next lesson: Finglish clue first, then just the meaning ({r})", r == ["finglish", "plain"])
    check("no page errors (spelling)", not errs, errs); c.close()
    # ---------- writing twice ----------
    c, pg, errs = page(b, st())
    q = pg.evaluate("buildLessonCore(LESSONS.find(l => l.id === 'a1-1')).map((e, i) => e.type === 'trace' ? { i, L: e.L[1], memory: e.memory } : null).filter(Boolean)")
    plain = [x for x in q if not x["memory"]]; mem = [x for x in q if x["memory"]]
    check(f"letters are written twice: traced, then from memory later ({q})", len(mem) == min(3, len(plain)) and min(x["i"] for x in mem) > max(x["i"] for x in plain) and set(x["L"] for x in mem) <= set(x["L"] for x in plain))
    def open_trace(memory, letter="be"):
        pg.evaluate(f"""(() => {{ const L = LETTERS.find(L => L[1] === {json.dumps(letter)}); const ex = exTrace(L, {str(memory).lower()});
           R = {{ queue: [ex, exTrace(L, false)], pos: 0, mistakes: 0, graded: 0, requeued: 0, phase: 'answer', built: [], missed: [], finish: false }}; openOverlay('lesson'); showExercise(); }})()""")
        pg.wait_for_timeout(250)
    def guide_pixels():  # grey pixels drawn on the visible canvas (the ink is turquoise; nothing drawn yet)
        return pg.evaluate("(() => { const c = document.getElementById('traceCanvas'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 16) if (d[i] > 20) n++; return n; })()")
    open_trace(False); traced = guide_pixels()
    open_trace(True); hidden = guide_pixels()
    check(f"from memory, the gray letter isn't there to copy ({traced} vs {hidden} pixels)", traced > 500 and hidden == 0)
    check("the title doesn't show the letter, only its name and sound", "Write be from memory" in pg.inner_text("#exBox h2") and "ب" not in pg.inner_text("#exBox"))
    pg.screenshot(path=OUT + "write_memory.png")
    pg.click("#tracePeek"); pg.wait_for_timeout(200); during = guide_pixels(); pg.wait_for_timeout(1600); after = guide_pixels()
    check(f"Peek shows it for a moment, then hides it again ({during}, {after})", during > 500 and after == 0)
    # write it smaller and off to one side: still counts
    pts = pg.evaluate("R.trace.points(5)")
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    small = [[cx - 40 + (x - cx) * 0.55, cy + 30 + (y - cy) * 0.55] for x, y in pts]
    draw(pg, small); pg.click("#mainBtn"); pg.wait_for_timeout(300)
    check("written smaller and off-center from memory: counts as right", "remember" in pg.inner_text("#feedback").lower() or "afarin" in pg.inner_text("#feedback").lower() or "yourself" in pg.inner_text("#feedback").lower(), pg.inner_text("#feedback"))
    check("and the letter is shown afterwards to compare", guide_pixels() > 500)
    pg.screenshot(path=OUT + "write_memory_done.png")
    # a scribble that isn't the letter: not accepted
    open_trace(True, "alef")
    r = pg.evaluate("(() => { const c = document.getElementById('traceCanvas').getBoundingClientRect(); return [c.left, c.top, c.width]; })()")
    x0, y0, w = r
    pg.mouse.move(x0 + w * 0.15, y0 + w * 0.5); pg.mouse.down(); pg.mouse.move(x0 + w * 0.85, y0 + w * 0.5, steps=12); pg.mouse.move(x0 + w * 0.85, y0 + w * 0.8, steps=6); pg.mouse.move(x0 + w * 0.15, y0 + w * 0.8, steps=12); pg.mouse.up()
    pg.click("#mainBtn"); pg.wait_for_timeout(300)
    check("a box shape for alef is not accepted", "Not quite" in pg.inner_text("#feedback"), pg.inner_text("#feedback"))
    check("and the letter is shown so you can see the difference", guide_pixels() > 200)
    # the ordinary tracing still works as before
    open_trace(False); pts = pg.evaluate("R.trace.points(5)"); draw(pg, pts); pg.click("#mainBtn"); pg.wait_for_timeout(300)
    check("ordinary tracing still works", any(s in pg.inner_text("#feedback") for s in ["Beautiful", "Lovely", "great"]), pg.inner_text("#feedback"))
    check("no page errors (writing)", not errs, errs); c.close()
    # a whole letters lesson and a whole words lesson still finish
    b.close()
print(f"{sum(res)}/{len(res)} passed")
