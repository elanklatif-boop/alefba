import json
from playwright.sync_api import sync_playwright
PAID={"talks":True,"plans":True,"signedIn":True,"canTalk":True,"kind":"unlimited","plan":"yearly","left":30,"today":30,"hear":True,"hearReady":True,"voiceReady":True,"voice":True,"free":3,"prices":{"basic":"$4.99","unlimited":"$6.49","yearly":"$39"}}
def st(lang):
    s={"done":{},"items":{},"days":[],"talks":{},"prefs":{"lang":lang,"fing":"auto","voiceMode":True},"log":{},"speak":1,"read":0,"profile":{"name":"Elan","goal":2,"adult":False,"speakSelf":1,"readSelf":0,"reasons":[]}}
    return "localStorage.setItem('alefba-v3', "+json.dumps(json.dumps(s))+")"
STUB="AI = { web: true, json: async () => ({ fa: 'سلام! چطوری؟', translit: 'salâm! chetori?', en: 'Hi!', written: 'سلام! چطوری؟', written_translit: '', feedback: null, suggestions: [{ fa: 'خوبم', translit: 'khubam', en: 'I am good' }], new_words: [], goals_done: [], pace: 'same', done: false, you_said: null }) }; aiState = 'ready';"
res=[]
def check(n,ok,x=""): res.append(ok); print(("PASS " if ok else "FAIL ")+n+("" if ok else f"  [{x}]"))
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream","--autoplay-policy=no-user-gesture-required"])
    def page(lang, gloss_status=200):
        c=b.new_context(viewport={"width":390,"height":844},permissions=["microphone"]); c.add_init_script(st(lang))
        calls=[]
        c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(PAID)))
        c.route("**/api/hear*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"text":"من قهوه دوست دارم"})))
        c.route("**/api/say*", lambda r: r.fulfill(status=200, content_type="audio/mpeg", body=b"\x00"*3000))
        def gl(r):
            calls.append(r.request.post_data_json)
            if gloss_status!=200: return r.fulfill(status=gloss_status, content_type="application/json", body=json.dumps({"error":"server_error"}))
            l=r.request.post_data_json.get("lang")
            r.fulfill(status=200, content_type="application/json", body=json.dumps({"translit":"man ghahve dust dâram","meaning":"J'aime le café" if l=="fr" else "I like coffee"}))
        c.route("**/api/gloss*", gl)
        pg=c.new_page(); e=[]; pg.on("pageerror", lambda x: e.append(str(x))); pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(900)
        pg.evaluate(STUB+" openTalk(LESSONS.find(l => l.kind === 'talk'))"); pg.wait_for_timeout(300)
        pg.evaluate("TK.started = false; startTalk()"); pg.wait_for_timeout(800)
        pg.click("#talkMic"); pg.evaluate("TK.handsFree = false; 0"); pg.wait_for_timeout(1200); pg.click("#talkMic"); pg.wait_for_timeout(1500)  # (sent by itself only hands-free: fast_check)
        return pg,e,calls
    pg,e,calls=page("en")
    t=pg.inner_text("#heardCard")
    check("I heard box shows the Persian, its Finglish and its meaning", "من قهوه دوست دارم" in t and "man ghahve dust dâram" in t and "I like coffee" in t, t)
    check("gloss asked once, for the heard line in English", len(calls)==1 and calls[0]=={"text":"من قهوه دوست دارم","lang":"en"}, calls)
    pg.screenshot(path="gloss.png", clip={"x":0,"y":350,"width":390,"height":494})
    pg.click("#heardAgain"); pg.evaluate("TK.handsFree = false; 0"); pg.wait_for_timeout(1200); pg.click("#talkMic"); pg.wait_for_timeout(1500)
    check("the same line again doesn't ask the website twice", len(calls)==1, len(calls))
    check("no page errors", not e, e); pg.context.close()
    pg,e,calls=page("fr")
    t=pg.inner_text("#heardCard")
    check("French learner sees the meaning in French", "J'aime le café" in t and calls and calls[0]["lang"]=="fr", t)
    pg.context.close()
    pg,e,calls=page("en", 502)
    t=pg.inner_text("#heardCard")
    check("if the gloss fails, the box still works with just the Persian and the buttons", "من قهوه دوست دارم" in t and "…" not in t and pg.is_visible("#heardSend"), t)
    check("no page errors (failed gloss)", not e, e); pg.context.close()
    b.close()
print(f"{sum(res)}/{len(res)} passed")
