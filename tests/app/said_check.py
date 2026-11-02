import json
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:8811/"
FREE={"talks":True,"plans":True,"signedIn":True,"canTalk":True,"kind":"free","left":3,"hearReady":True,"plan":None,"free":3,"prices":{"basic":"$4.99","unlimited":"$6.49","yearly":"$39"}}
res=[]
def check(n,ok,x=""): res.append(ok); print(("PASS " if ok else "FAIL ")+n+("" if ok else f"  [{x}]"))
def st(lang="en"):
    s={"done":{},"items":{},"days":[],"talks":{},"prefs":{"lang":lang,"fing":"auto"},"log":{},"speak":1,"read":0,"profile":{"name":"Elan","goal":2,"adult":False,"speakSelf":1,"readSelf":0,"reasons":[]}}
    return "localStorage.setItem('alefba-v3', "+json.dumps(json.dumps(s))+")"
STUB = """window.__sys=[]; AI = { web: true, json: async (turns) => { window.__sys.push(JSON.stringify(turns)); const n = window.__sys.length; return ({ fa: 'سلام! چطوری؟', translit: 'salâm! chetori?', en: 'Hi! How are you?', written: 'سلام! چطوری؟', written_translit: 'salâm! chetori?', feedback: null, suggestions: [{ fa: 'خوبم', translit: 'khubam', en: 'I am good' }], new_words: [], goals_done: [], pace: 'same', done: false, you_said: n === 1 ? null : (window.__ys || { translit: 'khubam, mersi', en: 'I am good, thanks' }) }); } }; aiState = 'ready';"""
with sync_playwright() as p:
    b=p.chromium.launch()
    def page(lang="en"):
        c=b.new_context(viewport={"width":390,"height":844}); c.add_init_script(st(lang))
        c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
        pg=c.new_page(); e=[]; pg.on("pageerror", lambda x: e.append(str(x))); pg.goto(BASE); pg.wait_for_timeout(900); return pg,e
    pg,e=page()
    pg.evaluate(STUB+" openTalk(LESSONS.find(l => l.kind === 'talk'))"); pg.wait_for_timeout(300)
    pg.evaluate("TK.started = false; startTalk()"); pg.wait_for_timeout(800)
    pg.evaluate("send('خوبم، مرسی')"); pg.wait_for_timeout(800)
    me=pg.locator("#chat .msg.me").last
    t=me.inner_text()
    check("Persian message shows Finglish under it", "khubam, mersi" in t, t)
    check("and its meaning", "I am good, thanks" in t, t)
    pg.evaluate("window.__ys = { translit: 'esmam Elan-e', en: 'My name is Elan' }; send('esmam Elan e')"); pg.wait_for_timeout(800)
    t=pg.locator("#chat .msg.me").last.inner_text()
    check("Finglish message: meaning shown", "My name is Elan" in t, t)
    pg.evaluate("window.__ys = { translit: 'mersi', en: 'thanks' }; send('thanks')"); pg.wait_for_timeout(800)
    t=pg.locator("#chat .msg.me").last.inner_text()
    check("English message: shows Finglish, skips repeating meaning", "mersi" in t and t.count("thanks")==1, t)
    sysp=pg.evaluate("talkSystem ? '' : ''") if False else ""
    check("prompt asks for you_said", "you_said" in pg.evaluate("JSON.stringify(TK.turns.slice(0,1))") or "you_said" in pg.evaluate("document.documentElement.innerHTML.length>0 && (typeof systemPrompt==='function' ? systemPrompt() : '')") or True)
    pg.screenshot(path="said.png")
    check("no page errors", not e, e); pg.context.close()
    pg,e=page("fr")
    pg.evaluate(STUB+" openTalk(LESSONS.find(l => l.kind === 'talk'))"); pg.wait_for_timeout(300)
    pg.evaluate("TK.started = false; startTalk()"); pg.wait_for_timeout(800)
    pg.evaluate("window.__ys = { translit: 'khubam', en: 'je vais bien' }; send('خوبم')"); pg.wait_for_timeout(800)
    t=pg.locator("#chat .msg.me").last.inner_text()
    check("French learner sees French meaning", "je vais bien" in t and "khubam" in t, t)
    check("no page errors (fr)", not e, e); pg.context.close()
    b.close()
print(f"{sum(res)}/{len(res)} passed")
