# Walk through every change from today in a real browser (Chromium, phone size), against the built site.
import json
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8811/"
PRICES = {"basic": "$4.99", "unlimited": "$6.49", "yearly": "$39"}
FREE = {"talks": True, "plans": True, "signedIn": True, "canTalk": True, "kind": "free", "left": 3, "hear": False, "hearReady": True, "plan": None, "free": 3, "basicTalks": 20, "perDay": 30, "prices": PRICES, "email": "el•••@gmail.com"}
PAID = {**FREE, "plan": "yearly", "kind": "unlimited", "today": 30, "hear": True, "managed": True}
results = []
def check(name, ok, extra=""):
    results.append((ok, name, extra)); print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if not ok and extra else ""))

def state(items=None, done=None, adult=False, profile=True):
    st = {"done": done or {}, "items": items or {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto"}, "log": {}, "speak": 1, "read": 0,
          "profile": ({"name": "Elan", "goal": 2, "adult": adult, "speakSelf": 1, "readSelf": 0, "reasons": []} if profile else None)}
    return "localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(st)) + ")"

FAKE_MIC = """
navigator.mediaDevices.getUserMedia = async () => new MediaStream([ (() => { const c = new AudioContext(); const o = c.createOscillator(); const d = c.createMediaStreamDestination(); o.connect(d); o.start(); return d.stream.getAudioTracks()[0]; })() ]);
"""

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"])
    def page(acct, init, hear_text="سلام"):
        ctx = b.new_context(viewport={"width": 390, "height": 844}, permissions=["microphone"])
        ctx.add_init_script(init)
        ctx.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(acct)))
        ctx.route("**/api/hear*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"text": hear_text})))
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE); pg.wait_for_timeout(900)
        return pg, errs

    # 1. opening page and first steps
    pg, errs = page({"talks": True, "plans": True, "signedIn": False, "hearReady": True, "free": 3, "turnstile": None, "prices": PRICES}, "localStorage.clear()")
    desc = pg.get_attribute('meta[name="description"]', "content")
    check("home page description is for everyone (kids, families and adults)", "kids, families and adults" in desc and "for kids." not in desc, desc)
    check("welcome says who it's for, broadly", "kids, teens and grown-ups" in pg.inner_text("#obMain"))
    pg.click("#obNext")
    check("first question: who's learning (child / adult, teens included)", "Who's learning" in pg.inner_text("#obMain") and "Teen or adult" in pg.inner_text("#obMain") and "13 and up" in pg.inner_text("#obMain"))
    check("no page errors (opening)", not errs, errs)
    pg.context.close()

    # 2. guided first build with letter sounds; I don't know; Finglish until right twice
    pg, errs = page(FREE, state())
    pg.evaluate("startLesson({ id: 'x', title: 'x', practice: true }, [exSpell(WORDS.find(W => W.tr === 'salâm')), exWordMeaning(WORDS.find(W => W.tr === 'mersi'), WORDS)])")
    pg.wait_for_timeout(300)
    check("first build is guided: 'Letter 1 of 4: tap sin'", "Letter 1 of 4: tap sin" in pg.inner_text("#guide"))
    check("first build shows Finglish sounds under the tiles", pg.locator(".tsound").count() >= 6)
    tiles = pg.evaluate("__alefba.state().queue[0].tiles"); used = []
    for g in ["س", "ل", "ا", "م"]:
        i = next(k for k, t in enumerate(tiles) if t == g and k not in used); used.append(i); pg.click(f"#tile-{i}"); pg.wait_for_timeout(80)
    pg.wait_for_timeout(600)
    check("guided build checks itself and counts as right", "Afarin" in pg.inner_text("#feedback") or "built it" in pg.inner_text("#feedback"))
    pg.click("#mainBtn"); pg.wait_for_timeout(300)
    check("meaning question shows Finglish for a new word", pg.inner_text(".glyph-cap") == "mersi")
    check("'I don't know' is there", pg.is_visible("#idkBtn"))
    pg.click("#idkBtn"); pg.wait_for_timeout(200)
    check("'I don't know' shows the answer gently", "No problem" in pg.inner_text("#feedback"))
    pg.context.close()
    pg, errs = page(FREE, state(items={"word:mersi": {"r": 1, "w": 0}, "hear:mersi": {"r": 1, "w": 0}}))
    pg.evaluate("startLesson({ id: 'x', title: 'x', practice: true }, [exWordMeaning(WORDS.find(W => W.tr === 'mersi'), WORDS)])"); pg.wait_for_timeout(300)
    check("after two right answers the Finglish is gone (hidden, behind Show Finglish)", pg.locator(".glyph-cap").count() == 0 or not pg.is_visible(".glyph-cap"))
    pg.context.close()

    # 3. sound for everything: every sound file the app can ask for is on the site
    pg, errs = page(FREE, state())
    missing = pg.evaluate("""async () => { const all = __alefba.sounds(); const bad = [];
      await Promise.all(all.map(async a => { const r = await fetch('audio/' + a.file, { method: 'HEAD' }); if (!r.ok) bad.push(a.file); })); return [all.length, bad]; }""")
    # Levels 13 to 16 (Oct 2026) have no recordings yet: with a plan the website's voice reads them. Everything older must be there.
    newer = set(pg.evaluate("""(() => { const s = new Set(), add = a => { if (a && a.file) s.add(a.file); };
      WORDS.filter(W => W.level >= 12).forEach(W => { add(wordAudio(W)); add(sentenceAudio(W)); if (W.two) { add(W.two.book.audio); add(W.two.said.audio); } });
      LEVELS.slice(12).forEach(lv => lv.dialogue.forEach(d => { add(lineAudio(d.fa)); if (d.wfa) add(lineAudio(d.wfa)); }));
      ADULT_LEVELS.slice(12).forEach(a => a.dialogue.forEach(d => { add(lineAudio(d.fa)); if (d.wfa) add(lineAudio(d.wfa)); }));
      SITUATIONS.concat(ADULT_SITUATIONS).filter(x => x.level >= 12).forEach(x => x.phrases.forEach(q => add(lineAudio(q.fa))));
      // the taarof talks (Nov 2026) are in Level 12 and the Taarof pack: their phrases are new too
      SITUATIONS.concat(ADULT_SITUATIONS).filter(x => ['tea', 'bill', 'fare', 'a-tea', 'a-bill', 'a-fare'].includes(x.id)).forEach(x => x.phrases.forEach(q => add(lineAudio(q.fa))));
      STORIES.concat(SEASON_PACKS.map(p => p.story)).forEach(st => st.lines.forEach(l => add(lineAudio(l.fa)))); SEASON_WORDS.forEach(W => { add(wordAudio(W)); add(sentenceAudio(W)); if (W.two) add(W.two.said.audio); }); STREET_WORDS.forEach(W => add(lineAudio(W.fa)));
      return [...s]; })()"""))
    old_missing = [f for f in missing[1] if f not in newer]
    check(f"every sound the older lessons use is on the site ({missing[0]} files; {len(missing[1])} new ones still to record)", missing[0] >= 899 and not old_missing, old_missing[:5])
    pg.context.close()

    # 4. free family: locked levels, locked speaking preview, plan cards with yearly
    pg, errs = page(FREE, state())
    pg.evaluate("renderLessons()")
    check("free family: Level 4 locked, Level 1 open", "locked" in (pg.get_attribute("#step-w4-1", "class") or "") and "locked" not in (pg.get_attribute("#step-w1-1", "class") or ""))
    pg.click("#step-w4-1"); pg.wait_for_timeout(200)
    check("tapping a locked lesson explains the plans ($39 a year shown)", "comes with a plan" in pg.inner_text("#lockedSheet") and "$39 a year" in pg.inner_text("#lockedSheet"))
    pg.click("#lockedClose")
    seq = pg.evaluate("buildLessonCore(__alefba.lessons.find(l => l.id === 'w1-1')).map(x => x.type)")
    check("free family: a locked Speak preview in a words lesson", "sayPreview" in seq and "say" not in seq, seq)
    pg.evaluate("openAccount(); document.getElementById('acctGate').hidden = true; document.getElementById('acctBody').hidden = false; renderAccountBody(document.getElementById('acctBody'), document.getElementById('accountSheet'), null)")
    body = pg.inner_text("#acctBody")
    check("plan cards: three plans with yearly, all levels + speaking on each", pg.locator(".plan-option").count() == 3 and "$39 a year" in body and body.count("All 16 levels of lessons") == 3 and body.count("Speaking practice") >= 3)
    check("no page errors (free family)", not errs, errs)
    pg.context.close()

    # 5. paying family: nothing locked; speaking with hear-yourself; mic in talks
    pg, errs = page(PAID, state())
    check("paying family: nothing locked", pg.evaluate("!__alefba.lessons.some(lessonLocked)"))
    seq = pg.evaluate("buildLessonCore(__alefba.lessons.find(l => l.id === 'w1-1')).map(x => x.type)")
    check("paying family: real Speak cards in a words lesson", seq.count("say") >= 2, seq)
    pg.evaluate("startLesson({ id: 'x', title: 'x', practice: true }, [exSay(WORDS.find(W => W.tr === 'salâm'))])"); pg.wait_for_timeout(300)
    sent = []
    pg.on("request", lambda r: sent.append(r.url) if "/api/hear" in r.url else None)
    pg.evaluate("window.__srcs = []; PLAYER.addEventListener('play', () => window.__srcs.push(PLAYER.src))")
    pg.click("#micBtn"); pg.wait_for_timeout(700); pg.click("#micBtn"); pg.wait_for_timeout(2500)
    srcs = pg.evaluate("window.__srcs")
    check("practice mode: your recording plays, then the real voice", any(x.startswith("blob:") for x in srcs) and srcs[-1].endswith("word_salaam.mp3"), srcs)
    check("practice mode: nothing is sent to the server", not sent, sent)
    check("practice mode: you decide, 'It sounded the same' / 'Not yet'", pg.is_visible("#saySame") and pg.is_visible("#sayAgain") and pg.is_visible("#hearMe"))
    pg.click("#saySame"); pg.wait_for_timeout(200)
    check("'It sounded the same' finishes the card", pg.evaluate("__alefba.state().phase") == "result" and pg.is_visible("#mainBtn"))
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    pg.evaluate("AI = { web: true, json: async () => ({ fa: 'سلام', translit: 'salâm', en: 'hi', written: 'سلام', written_translit: 'salâm', feedback: null, suggestions: [], new_words: [], goals_done: [], pace: 'same', done: false }) }; aiState = 'ready'; openTalk(LESSONS.find(l => l.kind === 'talk')); TK.started = false; startTalk();")
    pg.wait_for_timeout(800)
    check("paying family: working mic next to the talk box", pg.is_visible("#talkMic") and "locked" not in (pg.get_attribute("#talkMic", "class") or ""))
    check("no page errors (paying family)", not errs, errs)
    pg.context.close()

    # 7. adult mode: conversations, level check, account without the sum, link to the adults page
    pg, errs = page(FREE, state(adult=True))
    check("adult: conversations with Leila and the adult situations", pg.evaluate("__alefba.convs[0].who.name") == "Leila" and pg.evaluate("__alefba.convs.some(c => c.id === 's-a-taxi')"))
    check("adult level check uses adult lines", pg.evaluate("checkBank(2) === ADULT_CHECK_TALK[2]"))
    pg.evaluate("openAccount()"); pg.wait_for_timeout(200)
    check("adult: plans open without the maths question", pg.is_hidden("#acctGate") and pg.is_visible("#acctBody"))
    pg.evaluate("document.getElementById('accountSheet').remove(); openSignIn()"); pg.wait_for_timeout(200)
    check("adult: sign-in links to the adults page", pg.get_attribute("#signInSheet a.gate-link", "href") == "adults.html")
    check("no page errors (adult)", not errs, errs)
    pg.context.close()

    # 8. the extra pages
    ctx = b.new_context(viewport={"width": 390, "height": 844}); pg = ctx.new_page()
    for path, must in [("learn-persian.html", "for kids"), ("learn-persian-adults.html", "as an adult"), ("adults.html", "For adult learners"), ("parents.html", "For parents"), ("sitemap.xml", "learnalefba.com/adults")]:
        r = pg.goto(BASE + path); txt = pg.content()
        check(f"{path} is on the site", r.status == 200 and must in txt, r.status)
    check("Google pages say 'free to start', not 'lessons are free'", "lessons are free" not in (pg.goto(BASE + "learn-persian.html") and pg.content()))
    ctx.close()
    b.close()

fails = [r for r in results if not r[0]]
print(f"\n{len(results) - len(fails)} of {len(results)} passed")
