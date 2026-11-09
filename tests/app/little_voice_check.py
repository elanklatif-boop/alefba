# Little mode's English lines are Elan's recordings: the menu greets the child, flashcards say "Tap the picture to
# hear it" and only then the first word, the games and letters say their line, and no computer voice is used.
import json
from playwright.sync_api import sync_playwright
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
URL = "http://127.0.0.1:8811/"
ST = {"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en"}, "log": {}, "speak": 1, "read": 0,
      "profile": {"name": "Dara", "goal": 1, "little": True, "whoSet": True, "adult": False, "speakSelf": 0, "readSelf": 0, "reasons": [], "order": "letters"}}
with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    c.add_init_script("localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(ST)) + ")")
    c.add_init_script("window.__tts = 0; try { const o = speechSynthesis.speak.bind(speechSynthesis); speechSynthesis.speak = u => { window.__tts++; (window.__said = window.__said || []).push(u && u.text); }; } catch (e) {}")
    c.route("**/api/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{"talks":true,"plans":true,"signedIn":false}'))
    pg = c.new_page(); errs = []; heard = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("request", lambda rq: heard.append(rq.url.rsplit("/", 1)[-1]) if "/audio/" in rq.url and rq.url.endswith(".mp3") else None)
    pg.goto(URL); pg.wait_for_timeout(1500)
    check("the little menu greets the child in Elan's voice", pg.is_visible("#little") and "en_hi.mp3" in heard and "What do you want to do today?" in pg.inner_text("#littleHint"), heard)
    heard.clear(); pg.click("#lm-cards"); pg.wait_for_timeout(600)
    check("the topics say Pick a topic", "en_pick_topic.mp3" in heard, heard)
    heard.clear(); pg.locator("[id^=lw-]").first.click(); pg.wait_for_timeout(4000)
    words = [h for h in heard if h.startswith("word_")]
    check(f"a flashcard says 'Tap the picture to hear it' first, then the word ({heard})", heard and heard[0] == "en_tap_picture_hear.mp3" and words)
    pg.click("#littleHome"); pg.wait_for_timeout(300); pg.click("#littleHome"); pg.wait_for_timeout(400)
    heard.clear(); pg.click("#lm-games"); pg.wait_for_timeout(600)
    check("the games menu says Pick a game", "en_pick_game.mp3" in heard, heard)
    heard.clear(); pg.click("#lg-memory"); pg.wait_for_timeout(500); pg.locator("[id^=lw-]").first.click(); pg.wait_for_timeout(800)
    check("memory says Find the pairs", "en_find_pairs.mp3" in heard, heard)
    said = [t for t in (pg.evaluate("window.__said") or []) if t and t.strip()]  # a silent " " only wakes up the voice on phones
    check("no computer voice anywhere", not said, said)
    check("no page errors", not errs, errs)
    b.close()
print(f"{sum(res)} of {len(res)} passed")
import sys; sys.exit(0 if all(res) else 1)
