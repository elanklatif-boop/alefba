# A Speak card with a microphone that "says" a real word (Chromium's fake microphone plays a sound file): the word
# must be in the recording, the button says "Speak now" only once recording, and the clip isn't cut to nothing.
# Usage: python3 speak_mic_check.py [word.wav]   (default: speak_mic_word.wav next to this file: room noise, امشب, more noise)
import sys, json
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8811/"
import os
WAV = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "speak_mic_word.wav")
PRICES = {"basic": "$4.99", "unlimited": "$6.49", "yearly": "$39"}
PAID = {"talks": True, "plans": True, "signedIn": True, "canTalk": True, "kind": "unlimited", "left": 3, "hear": True, "hearReady": True,
        "plan": "yearly", "free": 3, "basicTalks": 20, "perDay": 30, "today": 30, "managed": True, "prices": PRICES, "email": "el•••@gmail.com"}
ST = {"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto"}, "log": {}, "speak": 1, "read": 0,
      "profile": {"name": "Elan", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 0, "reasons": []}}
OK = []
def check(name, cond, info=""):
    OK.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{info}]"))

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", f"--use-file-for-fake-audio-capture={WAV}",
                                "--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1280, "height": 800}, permissions=["microphone"])
    ctx.add_init_script("localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(ST)) + ")")
    ctx.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(PAID)))
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "?nostats"); pg.wait_for_timeout(900)
    pg.evaluate("document.querySelectorAll('.sheet-wrap').forEach(x => x.hidden = true)")
    for attempt in range(3):
        pg.evaluate("startLesson({ id: 'x', title: 'x', practice: true }, [exSay(WORDS.find(W => W.tr === 'emshab') || WORDS[0])])"); pg.wait_for_timeout(300)
        pg.click("#micBtn")
        labels = []
        for i in range(12): labels.append(pg.inner_text("#micBtn")); pg.wait_for_timeout(50)
        pg.wait_for_timeout(2600); pg.click("#micBtn"); pg.wait_for_timeout(1200)
        r = pg.evaluate("""() => { const w = R && R.say && R.say.mine; if (!w) return null; const v = new DataView(w); const n = (w.byteLength - 44) / 2;
            let s = 0, loud = 0; const F = 320; let frames = 0;
            for (let f = 0; f + F <= n; f += F) { let t = 0; for (let i = f; i < f + F; i++) { const x = v.getInt16(44 + i * 2, true) / 32768; t += x * x; } t = Math.sqrt(t / F); frames++; if (t > 0.02) loud++; }
            return { secs: n / 16000, loudSecs: loud * 0.02 }; }""")
        check(f"try {attempt + 1}: 'Getting ready…' first, then 'Speak now'", labels[0].strip().startswith("Getting ready") and any("Speak now" in l for l in labels), labels[:4])
        check(f"try {attempt + 1}: the word is in the recording (at least half a second of voice)", r and r["loudSecs"] >= 0.5, r)
        pg.evaluate("closeLesson()"); pg.wait_for_timeout(300)
    check("no page errors", not errs, errs)
    b.close()
print(f"{sum(OK)}/{len(OK)}")
sys.exit(0 if all(OK) else 1)
