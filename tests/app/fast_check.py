# Faster talks: the character's line is shown and spoken as soon as it arrives (before the rest of the reply), the
# microphone stops by itself when the learner pauses, what it heard is sent after a moment, and in voice mode the
# microphone opens by itself once the character has finished speaking. Uses Chrome's pretend microphone.
import json, sys
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8811/"
PAD = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/"
ME = {"talks": True, "plans": True, "signedIn": True, "canTalk": True, "kind": "unlimited", "plan": "unlimited", "hear": True, "hearReady": True,
      "voice": True, "voiceReady": True, "left": 99, "free": 3, "perDay": 30, "email": "x@example.com",
      "prices": {"basic": "$5", "unlimited": "$6.49", "yearly": "$39"}}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def state(voice):
    s = {"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "voiceMode": voice}, "log": {}, "speak": 1, "read": 0,
         "profile": {"name": "Elan", "goal": 2, "adult": True, "whoSet": True, "speakSelf": 1, "readSelf": 0, "reasons": []}}
    return "localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(s)) + ")"
FAKE = """
window.__talks = 0; window.__hears = 0; window.__gap = 1500; window.__said = []; window.__hearAt = [];
const realFetch = window.fetch;
window.fetch = async (u, o) => {
  u = String(u);
  if (u.includes('/api/talk') && o && o.method === 'POST') {
    const n = ++window.__talks; window.__lastBody = JSON.parse(o.body);
    const reply = { fa: n === 1 ? 'سلام! حالت چطوره؟' : 'چه خوب! امروز چیکار کردی؟', translit: n === 1 ? 'salâm! hâlet chetore?' : 'che khub! emruz chikâr kardi?',
      en: n === 1 ? 'Hi! How are you?' : 'Great! What did you do today?', written: 'سلام!', written_translit: 'salâm!', feedback: null,
      suggestions: [{ fa: 'خوبم.', translit: 'khubam.', en: "I'm good." }], new_words: [], goals_done: [], pace: 'same', done: false, you_said: null, talk_id: 'T1' };
    const enc = new TextEncoder(), wait = ms => new Promise(r => setTimeout(r, ms));
    const body = new ReadableStream({ async start(c) {
      await wait(200); c.enqueue(enc.encode(JSON.stringify({ early: { fa: reply.fa } }) + '\\n'));
      await wait(window.__gap); c.enqueue(enc.encode(JSON.stringify({ reply }) + '\\n')); c.close();
    } });
    return new Response(body, { status: 200, headers: { 'content-type': 'application/x-ndjson; charset=utf-8' } });
  }
  if (u.includes('/api/hear')) { window.__hears++; window.__hearAt.push(performance.now()); return new Response(JSON.stringify({ text: 'خوبم، مرسی' }), { status: 200, headers: { 'content-type': 'application/json' } }); }
  if (u.includes('/api/gloss')) return new Response(JSON.stringify({ translit: 'khubam, mersi', meaning: "I'm good, thanks" }), { status: 200, headers: { 'content-type': 'application/json' } });
  return realFetch(u, o);
};
"""
SETUP = """(async () => {
  sayText = (t, o) => { window.__said.push(t); setTimeout(() => o && o.after && o.after(), 300); return Promise.resolve(true); };
  AI = await webTalkAI(WEB.api); aiState = 'ready'; accountChanged();
  openTalk(LESSONS.find(l => l.kind === 'talk')); TK.started = false; startTalk();
})(); 0"""
def page(b, voice):
    c = b.new_context(viewport={"width": 390, "height": 844}, permissions=["microphone"])
    c.add_init_script(state(voice)); c.add_init_script(FAKE)
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(ME)))
    c.route("**/api/usage", lambda r: r.fulfill(status=200, body="{}"))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto(URL); pg.wait_for_timeout(1200)
    pg.evaluate("closeOnboarding && !$('onboard').hidden && closeOnboarding(); 0")
    return c, pg, errs
def launch(p, wav):
    return p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", f"--use-file-for-fake-audio-capture={wav}%noloop", "--autoplay-policy=no-user-gesture-required"])
def answer_wav(path):
    """A pretend answer for the fake microphone: a third of a second of quiet, then speech-like sound up to 1.7 s, then quiet
    until 10 s (the file must go on past the end of the recording: once it ends, Chrome's fake microphone gives noise)."""
    import math, struct, wave
    rate = 16000; out = []
    for i in range(int(rate * 10)):
        t = i / rate
        v = 0 if t < 0.3 or t > 1.7 else 0.5 * math.sin(2 * math.pi * 180 * t) * (0.6 + 0.4 * math.sin(2 * math.pi * 4 * t)) * (0.7 + 0.3 * math.sin(2 * math.pi * 11 * t))
        out.append(struct.pack("<h", int(v * 32767)))
    with wave.open(path, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(b"".join(out))
with sync_playwright() as p:
    import os
    if not os.path.exists(PAD + "answer.wav"): answer_wav(PAD + "answer.wav")
    b = launch(p, PAD + "answer.wav")
    # ---- reading mode: the line comes early, then the rest ----
    c, pg, errs = page(b, False)
    pg.evaluate(SETUP); pg.wait_for_timeout(700)
    early = pg.locator("#chat .msg.ai").last
    check("the character's line shows before the rest of the reply has come", pg.locator("#chat .msg.ai.early").count() == 1 and "سلام" in early.inner_text(), pg.inner_text("#chat")[:200])
    check("and is already being spoken", pg.evaluate("window.__said") == ["سلام! حالت چطوره؟"], pg.evaluate("window.__said"))
    check("the app asked for the reply in pieces", pg.evaluate("window.__lastBody.stream") is True)
    pg.wait_for_timeout(1700)
    t = pg.locator("#chat .msg.ai").last.inner_text(includes_hidden=True) if False else pg.evaluate("$('chat').querySelector('.msg.ai:last-of-type') ? [...$('chat').querySelectorAll('.msg.ai')].pop().textContent : ''")
    check("then the same bubble is filled in with Finglish and English", pg.locator("#chat .msg.ai").count() == 1 and pg.locator("#chat .msg.ai.early").count() == 0 and "salâm" in t and "How are you" in t, t)
    check("and the line isn't spoken a second time", pg.evaluate("window.__said.length") == 1, pg.evaluate("window.__said"))
    check("the suggestions come and the box is ready", pg.locator("#sugs button").count() >= 1 and not pg.is_disabled("#talkInput"))
    pg.screenshot(path=PAD + "fast_text.png")
    check("no page errors", not errs, errs); c.close()

    # ---- voice mode, hands-free ----
    c, pg, errs = page(b, True)
    pg.evaluate(SETUP); pg.wait_for_timeout(2300)
    check("voice mode is on", pg.evaluate("!!TK.voice"), pg.evaluate("[canSayText(), canHear()]"))
    check("before answering out loud, the microphone waits for a tap", not pg.evaluate("!!TALK_REC"))
    t0 = pg.evaluate("performance.now()")
    pg.click("#talkMic")
    pg.wait_for_function("window.__hears >= 1", timeout=9000)
    took = pg.evaluate("window.__hearAt[0]") - t0
    check(f"the microphone stops by itself after the learner pauses ({took:.0f} ms, the answer ends at 1.7 s and it waits nearly 2 s of quiet)", 2500 < took < 5500, took)
    pg.wait_for_selector("#heardCard", timeout=3000)
    check("what it heard is shown, with a Send button and a way to hear the clip, and nothing is sent by itself", "خوبم" in pg.inner_text("#heardCard") and pg.is_visible("#heardSend") and pg.is_visible("#heardMe") and "Sending" not in pg.inner_text("#heardCard") and pg.locator("#heardCard.auto").count() == 0)
    pg.screenshot(path=PAD + "fast_heard.png")
    pg.wait_for_timeout(2500)
    check("it's still there after a few seconds, waiting for the learner to check it", pg.locator("#heardCard").count() == 1 and pg.evaluate("window.__talks") == 1)
    pg.click("#heardSend"); pg.wait_for_function("window.__talks >= 2", timeout=4000)
    check("Send sends it", pg.locator("#heardCard").count() == 0 and "خوبم" in pg.inner_text("#chat .msg.me >> nth=-1"))
    pg.wait_for_timeout(600)
    check("the answer's line is spoken as soon as it comes", pg.evaluate("window.__said.length") == 2 and pg.locator("#chat .msg.ai.early").count() == 1, pg.evaluate("window.__said"))
    check("the microphone doesn't open while the rest of the reply is still coming", not pg.evaluate("!!TALK_REC"))
    pg.wait_for_function("!!TALK_REC", timeout=4000)
    check("once the reply is in and the line was heard, the microphone opens by itself", pg.evaluate("$('talkMic').classList.contains('rec')") and "go ahead" in pg.get_attribute("#talkInput", "placeholder"), pg.get_attribute("#talkInput", "placeholder"))
    pg.screenshot(path=PAD + "fast_listening.png")
    # Play again while it listens: the microphone lets go so it doesn't hear the line
    pg.evaluate("TALK_REC.cancel(); 0"); pg.wait_for_timeout(500)
    hears = pg.evaluate("window.__hears")
    check("a dropped clip isn't sent anywhere", hears == 1 and not pg.evaluate("!!TALK_REC"), hears)
    check("no page errors", not errs, errs)
    # the 'I heard' card never goes by itself
    pg.evaluate("showHeard('خوبم', true); 0"); pg.wait_for_timeout(2200)
    check("what it heard stays there to check (not sent)", pg.locator("#heardCard").count() == 1 and pg.evaluate("window.__talks") == 2 and "Sending" not in pg.inner_text("#heardCard"))
    check("and the microphone still opens by itself for the next answer (only sending needs a tap)", pg.evaluate("TK.handsFree") is True)
    pg.evaluate("clearHeard(); 0")
    # typing turns hands-free off
    pg.evaluate("TK.handsFree = true; 0"); pg.fill("#talkInput", "khubam"); pg.click("#talkSend"); pg.wait_for_timeout(2400)
    check("after typing a reply, the microphone doesn't open by itself", not pg.evaluate("!!TALK_REC") and pg.evaluate("TK.handsFree") is False)
    check("no page errors", not errs, errs); c.close(); b.close()

    # ---- nobody speaks: nothing is sent ----
    b = launch(p, PAD + "silence.wav")
    c, pg, errs = page(b, True)
    pg.evaluate(SETUP); pg.wait_for_timeout(2300)
    pg.click("#talkMic"); pg.wait_for_timeout(11500)
    check("if nobody speaks, the microphone stops with nothing sent", pg.evaluate("window.__hears") == 0 and not pg.evaluate("!!TALK_REC"), pg.evaluate("[window.__hears, !!TALK_REC]"))
    check("and says to tap when ready", "ready to answer" in pg.get_attribute("#talkInput", "placeholder"), pg.get_attribute("#talkInput", "placeholder"))
    check("no page errors", not errs, errs); c.close(); b.close()
print(f"{sum(res)} of {len(res)} passed")
sys.exit(0 if all(res) else 1)
