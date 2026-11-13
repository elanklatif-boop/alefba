import json
from playwright.sync_api import sync_playwright
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
res=[]
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def finish(pg, n=120):
    for _ in range(n):
        if pg.evaluate("!R || !!R.finish"): return True
        e = pg.evaluate("(() => { const e = current(); return e && { type: e.type, answer: e.answer, n: e.pairs ? e.pairs.length : 0 }; })()")
        t = e and e["type"]
        if t == "choice": pg.click(f"#opt-{e['answer']}")
        elif t == "match":
            for i in range(e["n"]): pg.click(f"#exBox .mitem[data-side='l'][data-i='{i}']"); pg.click(f"#exBox .mitem[data-side='r'][data-i='{i}']")
        elif t == "spell":
            tiles = pg.evaluate("(() => { const e = current(); const used = []; return e.target.map(g => { const i = e.tiles.findIndex((t, k) => t === g && !used.includes(k)); used.push(i); return i; }); })()")
            for i in tiles: pg.click(f"#tile-{i}")
            pg.click("#mainBtn"); pg.wait_for_timeout(80)
        elif t == "trace": pg.click("#traceSkip"); pg.wait_for_timeout(80); continue
        elif pg.is_visible("#idkBtn"): pg.click("#idkBtn")
        pg.wait_for_timeout(50)
        if pg.is_visible("#mainBtn") and pg.is_enabled("#mainBtn"): pg.click("#mainBtn")
        elif pg.is_visible("#skipBtn"): pg.click("#skipBtn")
        pg.wait_for_timeout(70)
    return pg.evaluate("!R || !!R.finish")
def ctx(b, state=None):
    c=b.new_context(viewport={"width":390,"height":844})
    if state: c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    c.route("**/api/usage", lambda r: r.fulfill(status=200, body="{}"))
    pg=c.new_page(); errs=[]; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1300); return c, pg, errs
with sync_playwright() as p:
    b=p.chromium.launch()
    # ---- a first visit, "Try the first lesson" ----
    c,pg,errs=ctx(b)
    pg.click("#obStart"); pg.wait_for_timeout(400)
    check("Try a free lesson asks one question first", pg.is_visible("#obfirst-yes") and pg.is_visible("#obfirst-no"))
    pg.click("#obfirst-no"); pg.wait_for_timeout(600)
    q=pg.evaluate("R.queue.map(e => e.type)")
    check(f"new to Persian: two letters, then two real words to read: {q}", q == ["introLetter","introLetter","choice","choice","tip","readWord","tip","readWord"], q)
    check("it's Meet the letters, with alef and be, without their shapes yet", pg.evaluate("R.lesson.id") == "a1-1" and pg.evaluate("R.queue.filter(e => e.type === 'introLetter').map(e => e.L[0] + (e.lite ? '' : '!')).join('')") == "اب")
    check("the words are bâbâ and âb", pg.evaluate("R.queue.filter(e => e.type === 'readWord').map(e => e.W.tr).join(',')") == "bâbâ,âb")
    check("it plays to the end", finish(pg))
    check("the finish says they read their first words", "You just read your first Persian words!" in pg.inner_text("#exBox"))
    check("the left-out letters wait for next time", pg.evaluate("JSON.stringify(S.later)") == json.dumps({"unit":0,"letters":["پ","ت","ث"]}, ensure_ascii=False, separators=(",",":")), pg.evaluate("JSON.stringify(S.later)"))
    check("the finish screen says what's next", pg.is_visible("#upNext") and "up next" in pg.inner_text("#upNext").lower())
    check("and asks who's learning first (not the email yet)", pg.is_visible("#whoCard") and not pg.is_visible("#nudgeCard"))
    pg.click("#whoChild"); pg.wait_for_timeout(300)
    check("a child: then it offers the reminder email, to a parent", pg.is_visible("#nudgeCard") and "parent or guardian" in pg.inner_text("#nudgeCard"))
    check("not the home screen or calendar yet", not pg.is_visible("#installBanner") and not pg.is_visible("#remindCard"))
    pg.screenshot(path="first/finish1.png", full_page=False)
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    nx=pg.evaluate("nextLesson().id")
    pg.evaluate("openLesson(nextLesson())"); pg.wait_for_timeout(500)
    head=pg.evaluate("R.queue.slice(0, 6).map(e => e.type + (e.L ? ':' + e.L[0] : ''))")
    check(f"the next lesson ({nx}) starts with پ and ت: {head}", head[:6] == ["introLetter:پ","choice","trace:پ","introLetter:ت","choice","trace:ت"], head)
    check("and plays to the end", finish(pg))
    check("then nothing is waiting any more", pg.evaluate("S.later === undefined"))
    check("the second lesson finish offers the home screen, not the email again", pg.evaluate("!!document.querySelector('#exBox #installBanner')") and not pg.is_visible("#nudgeCard") and not pg.is_visible("#remindCard"))
    check("no page errors", not errs, errs)
    c.close()
    # ---- a first visit by someone who already speaks some Persian ----
    c,pg,errs=ctx(b)
    pg.click("#obStart"); pg.wait_for_timeout(400); pg.click("#obfirst-yes"); pg.wait_for_timeout(600)
    q=pg.evaluate("R.queue.map(e => e.type + (e.W ? ':' + e.W.tr : ''))")
    check(f"speaks some: everyday words they may know, a letter found in each: {q}", q == ["heardWord:bâbâ","choice","heardWord:mâmân","choice","heardWord:âb","readWord:nân","introWord:bârân"], q)
    check("the word plays first, then shows written", pg.is_visible("text=Have you heard this word? bâbâ") and pg.locator("#exBox .cell.lit").count() == 4)
    check("their profile says they speak some", pg.evaluate("S.profile.first") == "heard" and pg.evaluate("speakLevel()") == 2)
    check("it plays to the end", finish(pg))
    check("and says they read 4 words", "You just read 4 Persian words!" in pg.inner_text("#exBox"))
    check("no page errors", not errs, errs)
    c.close()
    # ---- a first visit through "Find my level", talking first: words come first ----
    st={"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "talk"}, "log": {}, "speak": 0, "read": 0,
        "profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 0, "readSelf": 0, "reasons": []}}
    c,pg,errs=ctx(b, st)
    first=pg.evaluate("nextLesson().kind + ':' + nextLesson().id")
    pg.evaluate("openLesson(nextLesson())"); pg.wait_for_timeout(500)
    q=pg.evaluate("R.queue.map(e => e.type)")
    check(f"talking-first: the first lesson ({first}) is short too: {len(q)} steps", 6 <= len(q) <= 10, q)
    if first.startswith("words"):
        check("it plays to the end", finish(pg))
        later=pg.evaluate("S.later")
        check(f"two words wait for later ({later})", later and len(later["words"]) == 2)
        pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
        nxt = pg.evaluate("(() => { const l = LESSONS.find(l => l.kind === 'words' && l.level.index === S.later.level && !S.done[l.id]); return l.id; })()")
        pg.evaluate(f"openLesson(LESSONS.find(l => l.id === '{nxt}'))"); pg.wait_for_timeout(500)
        head=pg.evaluate("R.queue.slice(0,4).map(e => e.type + (e.W ? ':' + e.W.tr : e.key ? ':' + e.key.split(':')[1] : ''))")
        check(f"the next words lesson ({nxt}) starts with them: {head}", head[0] == "introWord:" + later["words"][0] and head[2] == "introWord:" + later["words"][1], head)
    check("no page errors", not errs, errs)
    c.close()
    # ---- someone who has done lessons before: unchanged ----
    st2=dict(st); st2["done"]={"w1-1": True}; st2["prefs"]=dict(st["prefs"], order="letters")
    c,pg,errs=ctx(b, st2)
    pg.evaluate("openLesson(LESSONS.find(l => l.id === 'a1-1'))"); pg.wait_for_timeout(400)
    n=pg.evaluate("R.queue.length")
    check(f"for someone who's done a lesson before, Meet the letters is the full lesson ({n} steps)", n >= 18, n)
    c.close(); b.close()
print(f"{sum(res)}/{len(res)} passed")
