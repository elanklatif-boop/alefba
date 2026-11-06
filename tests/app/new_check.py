# The new features in a real browser (Chromium, phone size), against the built site: voice mode, grammar tips,
# the install card, the offline helper, family profiles and the streak.
import json, base64
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8811/"
PRICES = {"basic": "$4.99", "unlimited": "$6.49", "yearly": "$39"}
FREE = {"talks": True, "plans": True, "signedIn": True, "canTalk": True, "kind": "free", "left": 3, "hear": False, "hearReady": True, "voice": False, "voiceReady": True, "plan": None, "free": 3, "basicTalks": 20, "perDay": 30, "prices": PRICES, "email": "el•••@gmail.com"}
PAID = {**FREE, "plan": "yearly", "kind": "unlimited", "today": 30, "hear": True, "voice": True, "managed": True}
# a tiny valid mp3-ish body (the browser only needs something playable; a silent WAV works for <audio>)
WAV = base64.b64decode("UklGRuwAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YcgAAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgA==")
results = []
def check(name, ok, extra=""):
    results.append((ok, name, extra)); print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if not ok and extra else ""))

def state(adult=False, done=None, prefs=None):
    st = {"done": done or {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", **(prefs or {})}, "log": {}, "speak": 1, "read": 0,
          "profile": {"name": "Elan", "goal": 2, "adult": adult, "speakSelf": 1, "readSelf": 0, "reasons": []}}
    return "localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(st)) + ")"

AI_STUB = "AI = { web: true, json: async () => ({ fa: 'سلام! چطوری؟', translit: 'salâm! chetori?', en: 'Hi! How are you?', written: 'سلام! چطوری؟', written_translit: 'salâm! chetori?', feedback: null, suggestions: [{ fa: 'خوبم', translit: 'khubam', en: 'I am good' }], new_words: [], goals_done: [], pace: 'same', done: false }) }; aiState = 'ready';"

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"])
    def page(acct, init, hear_text="خوبم"):
        ctx = b.new_context(viewport={"width": 390, "height": 844}, permissions=["microphone"])
        ctx.add_init_script(init)
        said = []
        ctx.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(acct)))
        ctx.route("**/api/hear*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"text": hear_text})))
        def say(r):
            said.append(json.loads(r.request.post_data)); r.fulfill(status=200, content_type="audio/mpeg", body=WAV)
        ctx.route("**/api/say", say)
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE, wait_until="domcontentloaded"); pg.wait_for_timeout(900)
        return pg, errs, said

    # 1. voice mode for a paying family
    pg, errs, said = page(PAID, state())
    pg.evaluate(AI_STUB + " openTalk(LESSONS.find(l => l.kind === 'talk'))"); pg.wait_for_timeout(300)
    check("voice mode toggle is offered (plan + voices)", pg.is_visible("#togVoice") and "locked" not in (pg.get_attribute("#togVoice", "class") or ""))
    pg.click("#togVoice"); pg.wait_for_timeout(100)
    check("voice mode switches on and is remembered", pg.get_attribute("#togVoice", "aria-pressed") == "true" and pg.evaluate("S.prefs.voiceMode") is True)
    pg.evaluate("window.__plays = []; PLAYER.addEventListener('play', () => window.__plays.push(PLAYER.src))")
    pg.evaluate("TK.started = false; startTalk()"); pg.wait_for_timeout(1200)
    check("the character's line is fetched from /api/say with the right voice", len(said) == 1 and said[0]["text"] == "سلام! چطوری؟" and said[0]["rate"] == "normal" and said[0]["voice"] in ("m", "f"), said)
    check("the line plays out loud", any(x.startswith("blob:") for x in pg.evaluate("window.__plays")), pg.evaluate("window.__plays"))
    check("the words stay hidden", pg.locator("#chat .msg.ai.listen").count() == 1 and pg.is_hidden("#chat .msg.ai .fa-line"))
    check("suggestions wait for Hint", "sugs-hidden" in (pg.get_attribute("#sugs", "class") or "") and pg.is_hidden("#sugs"))
    check("Play again, Slower, Show words, Hint are there", all(pg.is_visible("#" + i) for i in ["vmReplay", "vmSlow", "vmWords", "vmHint"]))
    pg.click("#vmSlow"); pg.wait_for_timeout(600)
    check("Slower asks for the slow version", len(said) == 2 and said[1]["rate"] == "slow", said)
    pg.click("#vmReplay"); pg.wait_for_timeout(400)
    check("Play again reuses the fetched line (no new request)", len(said) == 2, len(said))
    pg.click("#vmWords"); pg.wait_for_timeout(100)
    check("Show words shows the Persian", pg.is_visible("#chat .msg.ai .fa-line"))
    pg.click("#vmHint"); pg.wait_for_timeout(100)
    check("Hint shows the meaning and the suggestions", pg.is_visible("#chat .msg.ai .en") and pg.is_visible("#sugs"))
    check("the mic is the big button in voice mode", "voice" in (pg.get_attribute("#talkForm", "class") or "") and pg.is_visible("#talkMic"))
    pg.click("#talkMic"); pg.evaluate("TK.handsFree = false; 0"); pg.wait_for_timeout(600); pg.click("#talkMic"); pg.wait_for_timeout(2000)  # checking before sending (hands-free sending is in fast_check)
    check("after speaking, 'I heard' check appears instead of filling the box", pg.is_visible("#heardCard") and "خوبم" in pg.inner_text("#heardCard") and pg.input_value("#talkInput") == "")
    pg.click("#heardSend"); pg.wait_for_timeout(1200)
    check("Send sends what was heard, the next line arrives (same text: played from memory, no new request)", pg.locator("#chat .msg.me").count() == 1 and "خوبم" in pg.inner_text("#chat .msg.me") and pg.locator("#chat .msg.ai").count() == 2 and len(said) == 2)
    pg.click("#togVoice"); pg.wait_for_timeout(100)
    check("turning voice mode off reveals every line", pg.locator("#chat .msg.ai.listen").count() == 0 and pg.is_visible("#chat .msg.ai .fa-line"))
    check("no page errors (voice mode)", not errs, errs)
    pg.context.close()

    # 2. a free family sees voice mode locked
    pg, errs, said = page(FREE, state())
    pg.evaluate(AI_STUB + " openTalk(LESSONS.find(l => l.kind === 'talk'))"); pg.wait_for_timeout(300)
    check("free family: voice mode shown as locked, with the plans link", "locked" in (pg.get_attribute("#togVoice", "class") or "") and pg.is_visible("#voicePlans"))
    pg.click("#togVoice"); pg.wait_for_timeout(100)
    check("free family: tapping it doesn't turn it on", pg.get_attribute("#togVoice", "aria-pressed") == "false")
    pg.evaluate("TK.started = false; startTalk()"); pg.wait_for_timeout(1000)
    check("free family: text talk unchanged, nothing sent to /api/say", pg.locator("#chat .msg.ai.listen").count() == 0 and not said)
    pg.evaluate("closeTalk(); openAccount(); document.getElementById('acctGate').hidden = true; document.getElementById('acctBody').hidden = false; renderAccountBody(document.getElementById('acctBody'), document.getElementById('accountSheet'), null)")
    check("plan cards mention voice mode", pg.inner_text("#acctBody").count("Voice mode in talks") == 3)
    check("no page errors (free family)", not errs, errs)
    pg.context.close()

    # 3. grammar tips
    pg, errs, said = page(PAID, state())
    def finish():  # answer every card with "I don't know" until the lesson ends (missed cards come back once)
        for _ in range(8):
            if pg.evaluate("!!(R && R.finish)"): return
            if pg.is_visible("#idkBtn"): pg.click("#idkBtn"); pg.wait_for_timeout(150)
            pg.click("#mainBtn"); pg.wait_for_timeout(250)
    pg.evaluate("WORDS_MODE = 'grammar'; showView('words'); renderWords()"); pg.wait_for_timeout(200)
    check("Words tab has a Grammar mode with 14 cards", pg.locator("#wordList .gcard").count() == 14 and pg.get_attribute("#wmode-grammar", "aria-pressed") == "true")
    check("grammar examples are tappable to hear (voice available)", pg.locator("#wordList button.gex-fa").count() >= 40)
    pg.click("#gtip-ezafe button.gex-fa >> nth=0"); pg.wait_for_timeout(500)
    check("tapping an example asks the voice", len(said) == 1 and "سارا" in said[0]["text"], said)
    pg.evaluate("startLesson({ id: 'w1-1', title: 'x', level: LEVELS[0], kind: 'words' }, [exWordMeaning(WORDS.find(W => W.tr === 'mersi'), WORDS)])"); pg.wait_for_timeout(200)
    finish()
    check("after a Level 1 words lesson, a grammar tip for that level shows", pg.locator("#exBox .gcard").count() == 1 and pg.is_visible("#moreTipsBtn"))
    seen = pg.evaluate("Object.keys(S.tips || {})")
    pg.evaluate("startLesson({ id: 'w1-1', title: 'x', level: LEVELS[0], kind: 'words' }, [exWordMeaning(WORDS.find(W => W.tr === 'mersi'), WORDS)])"); pg.wait_for_timeout(200)
    finish()
    check("the next time, the level's other tip shows (each tip once)", pg.locator("#exBox .gcard").count() == 1 and pg.evaluate("Object.keys(S.tips || {})") != seen)
    check("no page errors (grammar)", not errs, errs)
    pg.context.close()

    # 4. install card and offline helper
    pg, errs, said = page(FREE, state(done={"a1-1": True, "a1-2": True}))
    check("home-screen banner on the lessons tab after a couple of lessons", pg.is_visible("#installBanner") and "home screen" in pg.inner_text("#installBanner"))
    pg.click("#installNo"); pg.wait_for_timeout(100); pg.evaluate("renderLessons()")
    check("'Not now' hides the banner for good", pg.locator("#installBanner").count() == 0)
    pg.evaluate("showView('review')")
    check("the Review tab keeps the full card", pg.is_visible("#installCard"))
    pg.evaluate("window.dispatchEvent(Object.assign(new Event('beforeinstallprompt'), { prompt: () => { window.__prompted = true; }, userChoice: Promise.resolve({ outcome: 'accepted' }) }))"); pg.wait_for_timeout(200)
    check("with the browser's install offer, the card gets an Add button", pg.is_visible("#installBtn"))
    pg.click("#installBtn"); pg.wait_for_timeout(200)
    check("the Add button asks the browser to install", pg.evaluate("window.__prompted === true"))
    sw = pg.evaluate("navigator.serviceWorker.getRegistration().then(r => !!r)")
    check("the offline helper is registered", sw)
    pg.wait_for_timeout(1500)
    cached = pg.evaluate("caches.keys().then(k => k)")
    check("the app's files are being kept on the device", any(k.startswith("alefba-app-") for k in cached), cached)
    man = pg.evaluate("fetch('manifest.webmanifest').then(r => r.json())")
    check("manifest: name, icons, standalone", man["short_name"] == "Alefba" and man["display"] == "standalone" and len(man["icons"]) == 3)
    for ic in ["icons/icon-192.png", "icons/icon-512.png", "icons/icon-180.png", "icons/maskable-512.png"]:
        check(f"{ic} is on the site", pg.evaluate(f"fetch('{ic}').then(r => r.ok)"))
    check("no page errors (install)", not errs, errs)
    pg.context.close()

    # 5. family profiles and streak (also covered in fam_check.py)
    pg, errs, said = page(FREE, state(done={"w1-1": True}))
    check("learner chip shows the name", pg.inner_text("#learnerBtn").strip() == "Elan")
    pg.click("#learnerBtn"); pg.wait_for_timeout(200); pg.click("#addLearnerBtn"); pg.wait_for_timeout(400)
    check("adding a learner starts the welcome for them", not pg.is_hidden("#onboard") and pg.evaluate("Object.keys(S.done).length") == 0)
    pg.click("#obAlt"); pg.wait_for_timeout(300); pg.click("#obfirst-no"); pg.wait_for_timeout(300); check("Try the first lesson opens a lesson", pg.is_visible("#lesson")); pg.evaluate("closeLesson()"); pg.wait_for_timeout(200); pg.click("#learnerBtn"); pg.wait_for_timeout(200)
    check("both learners are listed", pg.locator(".learner-row").count() == 2)
    pg.click("#learner-main"); pg.wait_for_timeout(300)
    check("switching back restores Elan's progress", pg.inner_text("#learnerBtn").strip() == "Elan" and pg.evaluate("Object.keys(S.done).length") == 1)
    pg.evaluate("S.days = [daysAgo(1), daysAgo(2)]; save(); renderStats()")
    check("streak shows days in a row", "2 days streak" in pg.inner_text("#streak") and "keeps your 2-day streak going" in pg.inner_text("#streakNudge"))
    check("no page errors (family)", not errs, errs)
    pg.context.close()
    b.close()

fails = [r for r in results if not r[0]]
print(f"\n{len(results) - len(fails)} of {len(results)} passed")
