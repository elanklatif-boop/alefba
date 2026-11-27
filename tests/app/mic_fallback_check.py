# An iPhone's Safari refused to start the recording ("InvalidStateError") and the Speak card gave up. Now each way of
# recording has a back-up: if one won't start, the next is tried straight away, and the one that works is remembered.
# Here the browser is made to refuse in the same way (the fake microphone plays a real word).
import sys, json, os
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:8811/"
WAV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speak_mic_word.wav")
ST = {"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto"}, "log": {}, "speak": 1, "read": 0,
      "profile": {"name": "Mum", "goal": 2, "adult": True, "speakSelf": 1, "readSelf": 0, "reasons": []}}
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
OK = []
def check(n, ok, x=""): OK.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
BREAK = {
  "pcm": "window.__orig = pcmRecorder; pcmRecorder = function () { throw Object.assign(new Error('x'), { name: 'InvalidStateError' }); };",
  "mr": "window.MediaRecorder = function () { throw Object.assign(new Error('x'), { name: 'InvalidStateError' }); };",
}
def run(p, broken, label, mode0=None):
    b = p.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", f"--use-file-for-fake-audio-capture={WAV}", "--autoplay-policy=no-user-gesture-required"])
    c = b.new_context(viewport={"width": 390, "height": 844}, permissions=["microphone"])
    init = "localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(ST)) + ");" + (f"localStorage.setItem('alefba-recmode', '{mode0}');" if mode0 else "")
    c.add_init_script(init); c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    sent = []; c.route("**/api/usage*", lambda r: (sent.append(r.request.post_data or ""), r.fulfill(status=204, body=""))[1])
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE); pg.wait_for_timeout(900)
    pg.evaluate("document.querySelectorAll('.sheet-wrap').forEach(x => x.hidden = true)")
    if broken == "pcm-late-only":  # the context made at the tap never runs (an iPhone can hold it): only "late" works
        pg.evaluate("window.__n = 0; const O = window.AudioContext; window.AudioContext = function () { const c = new O(); window.__n++; if (window.__n === 1) { c.resume = () => new Promise(() => {}); Object.defineProperty(c, 'state', { get: () => 'suspended' }); } return c; }; " + BREAK["mr"] + " 0")
    else:
        for k in broken: pg.evaluate(BREAK[k] + " 0")
    pg.evaluate("startLesson({ id: 'x', title: 'x', practice: true }, [exSay(WORDS.find(W => W.tr === 'emshab') || WORDS[0])])"); pg.wait_for_timeout(300)
    pg.click("#micBtn"); pg.wait_for_timeout(2600); pg.click("#micBtn"); pg.wait_for_timeout(1400)
    r = pg.evaluate("({ heard: document.getElementById('heard').textContent, mine: !!(R.say && R.say.mine), mode: REC_MODE, saved: localStorage.getItem('alefba-recmode') })")
    pg.wait_for_timeout(4200)
    b.close(); return r, errs, sent
with sync_playwright() as p:
    r, errs, _ = run(p, [], "normal")
    check("normally it records the usual way (pcm)", r["mine"] and r["mode"] == "pcm", r)
    r, errs, _ = run(p, ["pcm"], "iphone")
    check("the first way refuses with InvalidStateError (as on her iPhone): it records anyway, the next way", r["mine"] and "Listen" in r["heard"], r)
    check("…and that way is remembered on this device", r["saved"] == "mr", r)
    check("no page errors (fallback)", not errs, errs)
    r, errs, _ = run(p, "pcm-late-only", "late")
    check("the sound context made at the tap never starts, and MediaRecorder refuses: the third way records", r["mine"] and r["mode"] == "late", r)
    r, errs, sent = run(p, ["pcm", "mr"], "allbroken", mode0="pcm")
    # with pcmRecorder broken, "late" fails too: every way refuses
    check("if every way refuses, it says it didn't record, to try again, with where it failed", "didn't record" in r["heard"] and "InvalidStateError, start" in r["heard"], r["heard"])
    check("…and it's counted for the stats (mic_rec_fail)", any("mic_rec_fail" in s for s in sent), sent)
    check("no page errors (all broken)", not errs, errs)
print(f"{sum(OK)}/{len(OK)}")
sys.exit(0 if all(OK) else 1)
