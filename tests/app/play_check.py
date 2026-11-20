# learnalefba.com/play, the balloon game for a classroom screen: it opens on the Games tab with Balloons picked and no
# welcome in front, it's counted (play_link), the balloons are big on a big screen and unchanged on a phone, a game plays
# to the end, and a normal first visit still gets the welcome.
import json
from playwright.sync_api import sync_playwright
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
BASE = "http://127.0.0.1:8811/"
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def ctx(b, w, h):
    c = b.new_context(viewport={"width": w, "height": h}); sent = []
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    def got(r):
        try: sent.extend(json.loads(r.request.post_data or "{}").get("e", []))
        except Exception: pass
        r.fulfill(status=200, body="{}")
    c.route("**/api/usage", got)
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    return c, pg, errs, sent
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- a classroom screen ----
    c, pg, errs, sent = ctx(b, 1366, 768)
    pg.goto(BASE + "play.html"); pg.wait_for_timeout(1800)
    check("the short link lands in the app, with the link tidied away", pg.evaluate("location.pathname + location.hash") == "/", pg.url)
    check("no welcome in front of it", not pg.is_visible("#onboard"))
    check("the Games tab, with Balloons picked", pg.is_visible("#view-games") and pg.get_attribute("#gk-balloons", "aria-pressed") == "true")
    check("a note for teachers at the top", pg.is_visible("#classPlayNote") and "big screen" in pg.inner_text("#classPlayNote"))
    check("the two classroom games to pick from, Balloons and Bingo (no Memory)", pg.is_visible("#gk-balloons") and pg.is_visible("#gk-bingo") and pg.locator("#gk-memory").count() == 0)
    pg.evaluate("sendUsage()"); pg.wait_for_timeout(300)
    check("it's counted once (play_link)", sent.count("play_link") == 1, sent)
    pg.click("#gw-1"); pg.wait_for_timeout(700)
    check("Level 1 opens the balloon game", pg.is_visible("#sky") and "Pop the balloon" in pg.inner_text("#exBox"))
    bw = pg.evaluate("document.querySelector('.balloon').getBoundingClientRect().width")
    sky = pg.evaluate("(() => { const r = document.querySelector('#sky').getBoundingClientRect(); return [r.top, r.bottom, innerHeight]; })()")
    check(f"big balloons on a big screen ({round(bw)}px wide)", bw >= 140, bw)
    check("the sky fits on the screen", sky[1] <= sky[2] + 1, sky)
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/play_big.png")
    # a wrong balloon: it shakes, stops where it is, and keeps an ✕; it can't be tapped again
    w = pg.evaluate("(() => { const ex = current(), m = ex.words[R.balloon.round].m; return [...document.querySelectorAll('.balloon')].findIndex(b => b.getAttribute('aria-label') !== m); })()")
    pg.locator(f"#balloon-{w}").click(force=True); pg.wait_for_timeout(250)
    wrong = pg.evaluate(f"(() => {{ const b = document.getElementById('balloon-{w}'); return {{ x: !!b.querySelector('.balloon-x'), off: b.disabled, cls: b.className, label: b.getAttribute('aria-label') }}; }})()")
    check("a wrong balloon gets an ✕ and can't be tapped again", wrong["x"] and wrong["off"] and "wrong" in wrong["cls"] and "not this one" in wrong["label"], wrong)
    check("the other balloons can still be tapped", pg.evaluate("[...document.querySelectorAll('.balloon')].filter(b => !b.disabled).length") == pg.evaluate("document.querySelectorAll('.balloon').length") - 1)
    # the right one bursts with a ring and flying bits, where it had floated to
    m = pg.evaluate("current().words[R.balloon.round].m")
    before = pg.evaluate(f"(() => {{ const b = document.querySelector('.balloon[aria-label=\"{m}\"]'); const r = b.getBoundingClientRect(); return r.top + r.height / 2; }})()")
    pg.locator(f".balloon[aria-label=\"{m}\"]").first.click(force=True); pg.wait_for_timeout(60)
    burst = pg.evaluate(f"(() => {{ const b = document.querySelector('.balloon.popped'), L = document.querySelector('.pop-layer'); const r = b.getBoundingClientRect(); return {{ bits: L ? L.querySelectorAll('i').length : 0, ring: !!(L && L.querySelector('b')), mid: r.top + r.height / 2 }}; }})()")
    check(f"the right balloon bursts: a ring and {burst['bits']} bits fly out", burst["bits"] >= 14 and burst["ring"], burst)
    check(f"it bursts where it was, not back at the bottom (moved {round(abs(burst['mid'] - before))}px)", abs(burst["mid"] - before) < 40, (before, burst))
    pg.wait_for_timeout(900)
    check("the bits are tidied away afterwards", pg.locator(".pop-layer").count() == 0)
    # play every other round: pop the balloon whose label is the word being said
    for _ in range(20):
        if pg.evaluate("!R || R.phase === 'result'"): break
        m = pg.evaluate("(() => { const ex = current(); return ex.words[R.balloon.round].m; })()")
        pg.locator(f".balloon[aria-label=\"{m}\"]").first.click(force=True); pg.wait_for_timeout(850)
    check("the game plays to the end", pg.evaluate("R && R.phase === 'result'"))
    check("one miss: no confetti on the result", pg.locator(".confetti").count() == 0 and "Every balloon on the first try" not in pg.inner_text("#lesson"))
    pg.click("#mainBtn"); pg.wait_for_timeout(600)
    if pg.evaluate("!!R"): pg.click("#mainBtn"); pg.wait_for_timeout(600)
    check("afterwards it's back on the Games tab, still with no welcome", pg.evaluate("!R") and pg.is_visible("#view-games") and not pg.is_visible("#onboard"))
    # ---- Read it: the harder way, words in Persian on the balloons ----
    check("under Balloons: Pictures (picked) and Read it", pg.get_attribute("#bm-pics", "aria-pressed") == "true" and pg.is_visible("#bm-read"))
    pg.click("#bm-read"); pg.wait_for_timeout(300)
    check("Read it is picked, and the levels say how many words there are to read", pg.get_attribute("#bm-read", "aria-pressed") == "true" and "to read" in pg.inner_text("#gw-1"), pg.inner_text("#gw-1"))
    pg.click("#gw-1"); pg.wait_for_timeout(700)
    info = pg.evaluate("""(() => { const ex = current(); const bs = [...document.querySelectorAll('.balloon')];
      return { read: !!ex.read, rounds: ex.words.length, n: bs.length, text: bs.map(b => b.textContent), allFa: bs.every(b => b.querySelector('.balloon-fa')),
               fit: bs.every(b => { const t = b.querySelector('.balloon-fa'); return t && t.getBoundingClientRect().width <= b.getBoundingClientRect().width + 1; }),
               w: bs[0].getBoundingClientRect().width }; })()""")
    check(f"6 balloons, each with a word in Persian ({info['text']})", info["read"] and info["n"] == 6 and info["allFa"], info)
    check(f"every word fits inside its balloon (balloons {round(info['w'])}px wide)", info["fit"] and info["w"] >= 120, info)
    check(f"{info['rounds']} rounds (10 when the level has enough words)", info["rounds"] == min(10, pg.evaluate("readWords(LEVELS[0].words).length")), info["rounds"])
    alike = 0; played = 0
    for _ in range(14):
        if pg.evaluate("!R || R.phase === 'result'"): break
        r = pg.evaluate("""(() => { const ex = current(), W = ex.words[R.balloon.round], a = plainFa(W.fa);
          const bs = [...document.querySelectorAll('.balloon')], i = bs.findIndex(b => b.textContent === Z(W.fa));
          const others = bs.filter((b, k) => k !== i).map(b => plainFa(b.textContent));
          return { i, alike: others.some(o => o[0] === a[0] || [...new Set(o)].filter(ch => a.includes(ch)).length >= 2) }; })()""")
        played += 1; alike += r["alike"]
        pg.locator(f"#balloon-{r['i']}").click(force=True); pg.wait_for_timeout(850)
    check("Read it plays to the end", pg.evaluate("R && R.phase === 'result'"))
    conf = {"layers": pg.locator(".confetti").count(), "bits": pg.locator(".confetti i").count(), "text": pg.inner_text("#lesson")}
    check("every balloon on the first try: confetti", conf["layers"] >= 1 and conf["bits"] >= 80 and "Every balloon on the first try" in conf["text"], conf)
    check(f"the wrong answers look like the right one (in {alike} of {played} rounds a wrong word shares its first letter or two letters)", played and alike >= played - 1, (alike, played))
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/play_read_done.png")
    pg.click("#mainBtn"); pg.wait_for_timeout(600)
    if pg.evaluate("!!R"): pg.click("#mainBtn"); pg.wait_for_timeout(600)
    check("no page errors (classroom screen)", not errs, errs); c.close()

    # ---- the same link on a phone: balloons as they always were ----
    c, pg, errs, sent = ctx(b, 390, 844)
    pg.goto(BASE + "play.html"); pg.wait_for_timeout(1800); pg.click("#gw-1"); pg.wait_for_timeout(700)
    bw = pg.evaluate("document.querySelector('.balloon').getBoundingClientRect().width")
    check(f"on a phone the balloons are their usual size ({round(bw)}px)", bw <= 80, bw)
    pg.click("#quitBtn"); pg.wait_for_timeout(200)
    if pg.is_visible("#leaveBtn"): pg.click("#leaveBtn"); pg.wait_for_timeout(300)
    pg.click("#bm-read"); pg.wait_for_timeout(200); pg.click("#gw-1"); pg.wait_for_timeout(700)
    info = pg.evaluate("""(() => { const bs = [...document.querySelectorAll('.balloon')];
      return { n: bs.length, fit: bs.every(b => { const t = b.querySelector('.balloon-fa'); return t && t.getBoundingClientRect().width <= b.getBoundingClientRect().width + 1; }),
               inSky: bs.every(b => b.getBoundingClientRect().right <= innerWidth) }; })()""")
    check("Read it on a phone: 4 balloons, every word inside its balloon and on the screen", info["n"] == 4 and info["fit"] and info["inSky"], info)
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/play_read_phone.png")
    check("no page errors (phone)", not errs, errs); c.close()

    # ---- a normal first visit is unchanged ----
    c, pg, errs, sent = ctx(b, 390, 844)
    pg.goto(BASE); pg.wait_for_timeout(1500)
    check("a normal first visit still opens the welcome, without the classroom styles", pg.is_visible("#onboard") and not pg.evaluate("document.body.classList.contains('class-play')"))
    c.close()
    b.close()
print(f"play_check: {sum(res)} of {len(res)} passed")
