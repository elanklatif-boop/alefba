# Where people stop in their first lesson: each card a learner reaches in their very first lesson is counted
# (first_new_3 = reached card 3 of the "I'm new" first lesson), plus finishing it or tapping Leave. Later lessons,
# packs and games aren't counted, and the stats page turns the totals into a table.
import json
from playwright.sync_api import sync_playwright
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def step(pg, wrong=False):
    e = pg.evaluate("(() => { const e = current(); return e && { type: e.type, answer: e.answer, n: (e.options || []).length }; })()")
    t = e and e["type"]
    if t == "choice": pg.click(f"#opt-{(e['answer'] + 1) % e['n'] if wrong else e['answer']}")
    elif t == "trace": pg.click("#traceSkip"); pg.wait_for_timeout(80); return
    elif pg.is_visible("#idkBtn"): pg.click("#idkBtn")
    pg.wait_for_timeout(50)
    if pg.is_visible("#mainBtn") and pg.is_enabled("#mainBtn"): pg.click("#mainBtn")
    elif pg.is_visible("#skipBtn"): pg.click("#skipBtn")
    pg.wait_for_timeout(70)
def finish(pg, wrong_first=False):
    missed = False
    for _ in range(60):
        if pg.evaluate("!R || !!R.finish"): return True
        w = wrong_first and not missed and pg.evaluate("current().type") == "choice"
        if w: missed = True
        step(pg, w)
    return pg.evaluate("!R || !!R.finish")
def ctx(b, state=None, hash=""):
    c = b.new_context(viewport={"width": 390, "height": 844}); sent = []
    if state: c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    def got(r):
        try: sent.extend(json.loads(r.request.post_data or "{}").get("e", []))
        except Exception: pass
        r.fulfill(status=200, body="{}")
    c.route("**/api/usage", got)
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto("http://127.0.0.1:8811/" + hash); pg.wait_for_timeout(1300)
    return c, pg, errs, sent
def flush(pg): pg.evaluate("sendUsage()"); pg.wait_for_timeout(300)
firsts = lambda sent: [e for e in sent if e.startswith("first_")]
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- new to Persian: plays it through ----
    c, pg, errs, sent = ctx(b)
    pg.click("#obStart"); pg.wait_for_timeout(400); pg.click("#obfirst-no"); pg.wait_for_timeout(600)
    flush(pg)
    check("card 1 is counted as soon as the first lesson opens", firsts(sent) == ["first_new_1"], firsts(sent))
    n = pg.evaluate("R.queue.length")
    check("it plays to the end", finish(pg)); flush(pg)
    want = [f"first_new_{i}" for i in range(1, n + 1)] + ["first_new_done"]
    check(f"each of its {n} cards once, then finished", firsts(sent) == want, firsts(sent))
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200); before = len(firsts(sent))
    pg.evaluate("openLesson(nextLesson())"); pg.wait_for_timeout(400); step(pg); step(pg); flush(pg)
    check("the second lesson isn't counted", len(firsts(sent)) == before, firsts(sent)[before:])
    check("no page errors", not errs, errs); c.close()

    # ---- speaks some: two cards, then Leave ----
    c, pg, errs, sent = ctx(b)
    pg.click("#obStart"); pg.wait_for_timeout(400); pg.click("#obfirst-yes"); pg.wait_for_timeout(600)
    step(pg); step(pg)
    pg.click("#quitBtn"); pg.wait_for_timeout(200); pg.click("#leaveBtn"); pg.wait_for_timeout(300); flush(pg)
    check("speaks some: cards 1 to 3, then Leave", firsts(sent) == ["first_heard_1", "first_heard_2", "first_heard_3", "first_heard_left"], firsts(sent))
    pg.evaluate("openLesson(nextLesson())"); pg.wait_for_timeout(400); flush(pg)
    check("starting it again counts it again (it still isn't done)", firsts(sent)[-1] == "first_heard_1", firsts(sent))
    check("Keep going isn't counted as leaving", (pg.click("#quitBtn"), pg.wait_for_timeout(150), pg.click("#keepBtn"), pg.wait_for_timeout(150), flush(pg), firsts(sent).count("first_heard_left"))[-1] == 1, firsts(sent))
    check("no page errors", not errs, errs); c.close()

    # ---- a wrong answer: the card comes back at the end and counts as a later card ----
    c, pg, errs, sent = ctx(b)
    pg.click("#obStart"); pg.wait_for_timeout(400); pg.click("#obfirst-no"); pg.wait_for_timeout(600)
    check("with one wrong answer it still plays to the end", finish(pg, wrong_first=True)); flush(pg)
    n, m = pg.evaluate("[R.queue.length, R.mistakes]")
    check(f"a mistake ({m}) and {n} cards: each counted once, in order, then finished", m >= 1 and firsts(sent) == [f"first_new_{i}" for i in range(1, n + 1)] + ["first_new_done"], firsts(sent))
    c.close()

    # ---- came another way (Find my level): counted as other ----
    st = {"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 0, "read": 0,
          "profile": {"name": "Sara", "goal": 2, "adult": True, "speakSelf": 0, "readSelf": 0, "reasons": []}}
    c, pg, errs, sent = ctx(b, st)
    pg.evaluate("openLesson(nextLesson())"); pg.wait_for_timeout(500); step(pg); flush(pg)
    check("after Find my level: counted as another way", firsts(sent) == ["first_other_1", "first_other_2"], firsts(sent))
    c.close()

    # ---- a taarof pack lesson first, then the path: only the path lesson counts ----
    st2 = dict(st, done={"taarof-game": True}, profile={"skipped": True, "goal": 2, "adult": False, "first": "new"})
    c, pg, errs, sent = ctx(b, st2)
    pg.evaluate("openLesson(LESSONS.find(l => l.id === 'taarof-quiz') || LESSONS.find(l => l.level && l.level.season))"); pg.wait_for_timeout(400); flush(pg)
    check("a pack lesson isn't a first lesson", firsts(sent) == [], firsts(sent))
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    pg.evaluate("openLesson(nextLesson())"); pg.wait_for_timeout(400); flush(pg)
    check("but the first path lesson after it is (a pack done before doesn't count)", firsts(sent) == ["first_new_1"], firsts(sent))
    c.close()

    # ---- someone who has done a path lesson already: nothing ----
    st3 = dict(st, done={"a1-1": True})
    c, pg, errs, sent = ctx(b, st3)
    pg.evaluate("openLesson(nextLesson())"); pg.wait_for_timeout(400); step(pg); flush(pg)
    check("a learner who has done a lesson before isn't counted", firsts(sent) == [], firsts(sent))
    c.close()

    # ---- games aren't lessons ----
    c, pg, errs, sent = ctx(b, dict(st, profile={"skipped": True, "goal": 2, "adult": False, "first": "new"}))
    pg.evaluate("startGame('memory', LEVELS[0].words, 'test')"); pg.wait_for_timeout(400); flush(pg)
    check("a game isn't counted", firsts(sent) == [], firsts(sent))
    c.close()
    b.close()
print(f"first_steps_check: {sum(res)} of {len(res)} passed")
