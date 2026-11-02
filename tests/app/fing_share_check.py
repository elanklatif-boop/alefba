import json, base64, datetime
from playwright.sync_api import sync_playwright
OUT = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/v70/"
URL = "http://127.0.0.1:8811/"
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def st(fing="auto", done=None, items=None, order="letters", name="Sara"):
    return {"done": done or {}, "items": items or {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": fing, "order": order}, "log": {}, "speak": 1, "read": 1,
            "profile": {"name": name, "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
def page(b, state, when=None):
    c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    if when: pg.clock.set_fixed_time(when)
    pg.goto(URL); pg.wait_for_timeout(1200); return c, pg, errs
def goto_type(pg, pred, n=60):
    """answer questions correctly until the current one matches pred (a JS expression on e = current())"""
    for _ in range(n):
        if pg.evaluate(f"(() => {{ const e = current(); return !!e && ({pred}); }})()"): return True
        e = pg.evaluate("(() => { const e = current(); return e && { type: e.type, answer: e.answer, n: e.pairs ? e.pairs.length : 0 }; })()")
        if not e: return False
        t = e["type"]
        if t == "choice": pg.click(f"#opt-{e['answer']}")
        elif t == "match":
            for i in range(e["n"]): pg.click(f"#exBox .mitem[data-side='l'][data-i='{i}']"); pg.click(f"#exBox .mitem[data-side='r'][data-i='{i}']")
        elif t == "spell":
            tiles = pg.evaluate("(() => { const e = current(); const used = []; return e.target.map(g => { const i = e.tiles.findIndex((t, k) => t === g && !used.includes(k)); used.push(i); return i; }); })()")
            for i in tiles:
                if pg.evaluate("R.phase === 'answer'"): pg.evaluate(f"tapTile({i})")
            pg.wait_for_timeout(60)
            if pg.is_visible("#mainBtn") and pg.is_enabled("#mainBtn"): pg.click("#mainBtn")
            pg.wait_for_timeout(60)
        elif t == "trace": pg.click("#traceSkip"); pg.wait_for_timeout(60); continue
        elif pg.is_visible("#idkBtn"): pg.click("#idkBtn")
        pg.wait_for_timeout(50)
        if pg.is_visible("#mainBtn") and pg.is_enabled("#mainBtn"): pg.click("#mainBtn")
        elif pg.is_visible("#skipBtn"): pg.click("#skipBtn")
        pg.wait_for_timeout(70)
    return False
def finish(pg): goto_type(pg, "false", 200); return pg.evaluate("!R || !!R.finish")
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---------- Finglish, default ----------
    c, pg, errs = page(b, st(done={"a1-1": True}))
    pg.evaluate("startLesson(LESSONS.find(l => l.id === 'w1-1'))"); pg.wait_for_timeout(300)
    check("the first question about a word has its Finglish", goto_type(pg, "e.type === 'choice' && e.capW") and pg.is_visible("#exBox .glyph-cap") and pg.inner_text("#exBox .glyph-cap").strip() == pg.evaluate("current().capW.tr"))
    w0 = pg.evaluate("current().capW.tr")
    check("and it's remembered as shown", pg.evaluate(f"!!S.fseen[{json.dumps(w0)}]"))
    check("no Show Finglish button when nothing is hidden", not pg.is_visible("#fingBtn"))
    ok = goto_type(pg, "e.type === 'match'"); pg.wait_for_timeout(100)
    hidden = pg.evaluate("[...document.querySelectorAll('#exBox .mitem .sub')].filter(s => s.hidden).length")
    total = pg.evaluate("[...document.querySelectorAll('#exBox .mitem .sub')].length")
    check(f"in the match after it, the words already shown have no Finglish ({hidden} of {total} hidden)", ok and hidden >= 1, (hidden, total))
    pg.screenshot(path=OUT + "fing_match_hidden.png")
    check("a Show Finglish button is there", pg.is_visible("#fingBtn"))
    pg.click("#fingBtn"); pg.wait_for_timeout(80)
    check("and it brings the Finglish back for this question", pg.evaluate("[...document.querySelectorAll('#exBox .mitem .sub')].every(s => !s.hidden)") and not pg.is_visible("#fingBtn"))
    ok = goto_type(pg, "e.type === 'choice' && e.options.some(o => o.fw)")
    if ok:
        subs = pg.evaluate("[...document.querySelectorAll('#exBox .opt .sub')].map(s => s.hidden)")
        tr = pg.evaluate("current().options.map(o => o.fw && o.fw.tr)")
        seen_before = pg.evaluate("current().options.map(o => true)")
        pg.screenshot(path=OUT + "fing_options.png")
        target = pg.evaluate("current().options[current().answer].fw.tr")
        check(f"'which word…' answers: all or nothing, never mixed ({subs}, {tr})", len(set(subs)) == 1)
        check(f"…and hidden because {target} was already asked about", all(subs))
    else: check("found a which-word question", False)
    check("finishes", finish(pg)); check("no page errors (auto)", not errs, errs); c.close()
    # a brand-new question about a word built before its Finglish was seen still shows it (decided when shown)
    c, pg, errs = page(b, st(done={"a1-1": True}))
    r = pg.evaluate("""(() => { const W = LEVELS[0].words[3]; const a = exMeaningWord(W, LEVELS[0].words), b2 = exMeaningWord(W, LEVELS[0].words);
       R = { queue: [a, b2], pos: 0, mistakes: 0, graded: 0, requeued: 0, phase: 'answer', built: [], missed: [], finish: false }; openOverlay('lesson'); showExercise();
       const shown = () => Object.fromEntries([...document.querySelectorAll('#exBox .opt')].map(o => [o.querySelector('.sub').textContent, !o.querySelector('.sub').hidden]));
       const first = shown(); R.pos = 1; showExercise(); const second = shown(); return { first, second }; })()""")
    check(f"two questions about one word: Finglish under every answer the first time, under none the second ({r})", all(r["first"].values()) and not any(r["second"].values()))
    r2 = pg.evaluate("Object.keys(S.fseen)")
    check(f"only the word asked about counts as seen, not the wrong answers ({r2})", len(r2) == 1)
    c.close()
    # ---------- Finglish always / never ----------
    for mode in ("always", "off"):
        c, pg, errs = page(b, st(fing=mode, done={"a1-1": True}))
        r = pg.evaluate("""(() => { const W = LEVELS[0].words[2]; S.fseen = { [W.tr]: 1 }; const a = matchWords(LEVELS[0].words.slice(0, 4));
           R = { queue: [a], pos: 0, mistakes: 0, graded: 0, requeued: 0, phase: 'answer', built: [], missed: [], finish: false }; openOverlay('lesson'); showExercise();
           return { shown: [...document.querySelectorAll('#exBox .mitem .sub')].filter(s => !s.hidden).length, btn: !!document.getElementById('fingBtn') }; })()""")
        if mode == "always": check(f"'Always': every word keeps its Finglish ({r})", r["shown"] == 4 and not r["btn"])
        else: check(f"'Never': no Finglish and no button ({r})", r["shown"] == 0 and not r["btn"])
        c.close()
    # the settings label
    c, pg, errs = page(b, st())
    check("the setting reads 'Just at first'", pg.evaluate("document.documentElement.innerHTML.includes('Just at first')")); c.close()
    # ---------- Share card ----------
    W1 = None
    c, pg, errs = page(b, st(done={"a1-1": True}))
    lv0 = pg.evaluate("wordLessons(LEVELS[0]).map(l => l.id)")
    items = pg.evaluate("Object.fromEntries(LEVELS[0].words.map(W => ['word:' + W.tr, { r: 2, w: 0 }]))")
    c.close()
    done = {"a1-1": True}; done.update({k: True for k in lv0[:-1]})
    c, pg, errs = page(b, st(done=done, items=items))
    pg.evaluate(f"startLesson(LESSONS.find(l => l.id === {json.dumps(lv0[-1])}))"); pg.wait_for_timeout(300)
    check("the last words lesson of Level 1 finishes", finish(pg))
    check("the reward box offers 'Share with family'", pg.is_visible("#shareBtn"))
    pg.screenshot(path=OUT + "share_finish.png", full_page=False)
    pg.click("#shareBtn"); pg.wait_for_timeout(1200)
    check("the share sheet opens with the picture", pg.is_visible("#shareSheet") and pg.evaluate("document.getElementById('shareImg').src.startsWith('data:image/png')"))
    alt = pg.evaluate("document.getElementById('shareImg').alt")
    check(f"it says what Sara did ({alt})", alt == "Sara finished Level 1: Hello!")
    open(OUT + "share_card_level.png", "wb").write(base64.b64decode(pg.evaluate("document.getElementById('shareImg').src").split(",")[1]))
    wa = pg.evaluate("document.getElementById('shareWa').href")
    check("the WhatsApp button has the message and the link", wa.startswith("https://wa.me/?text=") and "learnalefba.com" in wa and "Sara" in wa)
    pg.click("#shareNameBox"); pg.wait_for_timeout(900)
    check("leaving the name off changes the picture and the message", pg.evaluate("document.getElementById('shareImg').alt") == "I finished Level 1: Hello!" and "Sara" not in pg.evaluate("document.getElementById('shareWa').href"))
    pg.screenshot(path=OUT + "share_sheet.png")
    # the share button: with no share menu (desktop) it saves the picture
    with pg.expect_download() as dl: pg.evaluate("navigator.canShare = undefined"); pg.click("#shareGo")
    check("without a share menu, the picture is saved", dl.value.suggested_filename == "alefba.png")
    # with a share menu: navigator.share is called with the file
    pg.evaluate("() => { window.__shared = null; navigator.canShare = () => true; navigator.share = d => { window.__shared = { files: d.files.length, type: d.files[0].type, text: d.text }; return Promise.resolve(); }; }")
    pg.click("#shareGo"); pg.wait_for_timeout(500)
    sh = pg.evaluate("window.__shared")
    check(f"with a share menu, the picture goes to it ({sh})", sh and sh["files"] == 1 and sh["type"] == "image/png" and "learnalefba.com" in sh["text"])
    pg.click("#shareClose")
    check("no page errors (share)", not errs, errs); c.close()
    # sticker book
    c, pg, errs = page(b, st(done={"a1-1": True}, items=items))
    pg.evaluate("openStickers()"); pg.wait_for_timeout(200)
    check("the sticker book has 'Share my progress'", pg.is_visible("#stickerSheet #shareBtn") and "Share my progress" in pg.inner_text("#stickerSheet #shareBtn"))
    pg.click("#stickerSheet #shareBtn"); pg.wait_for_timeout(1200)
    alt = pg.evaluate("document.getElementById('shareImg').alt")
    check(f"the progress card counts the words ({alt})", alt.startswith("Sara has learned 16 Persian words"))
    open(OUT + "share_card_words.png", "wb").write(base64.b64decode(pg.evaluate("document.getElementById('shareImg').src").split(",")[1]))
    check("no page errors (sticker book)", not errs, errs); c.close()
    # no words yet: no share button in the sticker book
    c, pg, errs = page(b, st(done={"a1-1": True}))
    pg.evaluate("openStickers()"); pg.wait_for_timeout(200)
    check("nothing learned yet: no share button", not pg.is_visible("#stickerSheet #shareBtn")); c.close()
    # Yalda pack finished, in December
    c, pg, errs = page(b, st(done={"a1-1": True, "yalda-1": True, "yalda-2": True, "yalda-game": True}), when=datetime.datetime(2026, 12, 10, 12))
    pg.evaluate("startLesson(LESSONS.find(l => l.id === 'yalda-story'))"); pg.wait_for_timeout(300)
    check("the Yalda story finishes the pack", finish(pg) and pg.is_visible("#levelDone"))
    check("the 'finished' box has a share button", pg.is_visible("#levelDone #shareBtn"))
    pg.click("#levelDone #shareBtn"); pg.wait_for_timeout(1200)
    alt = pg.evaluate("document.getElementById('shareImg').alt")
    check(f"the pack card ({alt})", alt == "Sara finished the Shab-e Yalda pack!")
    open(OUT + "share_card_yalda.png", "wb").write(base64.b64decode(pg.evaluate("document.getElementById('shareImg').src").split(",")[1]))
    check("no page errors (Yalda)", not errs, errs); c.close()
    # adult learner without a name
    c, pg, errs = page(b, st(done={"a1-1": True}, items=items, name=""))
    pg.evaluate("openStickers()"); pg.wait_for_timeout(200); pg.click("#stickerSheet #shareBtn"); pg.wait_for_timeout(1000)
    check("no name: 'I've learned…' and no name box", pg.evaluate("document.getElementById('shareImg').alt").startswith("I've learned") and not pg.is_visible("#shareNameBox"))
    c.close()
    # merge keeps both devices' record
    c, pg, errs = page(b, st())
    m = pg.evaluate("mergeProgress({ updated: 1, fseen: { a: 1 } }, { updated: 2, fseen: { b: 1 } }).fseen")
    check(f"merging two devices keeps both lists of shown Finglish ({m})", m == {"a": 1, "b": 1}); c.close()
    b.close()
print(f"{sum(res)}/{len(res)} passed")
