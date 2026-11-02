from playwright.sync_api import sync_playwright
import json
res=[]
def check(n,ok,x=""): res.append(ok); print("PASS" if ok else "FAIL", n, "" if ok else x)
st={"done":{},"items":{},"days":[],"talks":{},"prefs":{"lang":"fr","fing":"auto","order":"letters","tr":1},"log":{},"speak":1,"read":1,"profile":{"name":"Elan","goal":2,"adult":True}}
ACC={"talks":True,"plans":True,"signedIn":True,"canTalk":True,"kind":"unlimited","plan":"unlimited","left":99,"free":3,"basicTalks":20,"perDay":30,"email":"e@example.com","hear":True,"hearReady":True,"voiceReady":True,"voice":True,"prices":{}}
STUB="""AI = { web: true, json: async (msgs) => { await new Promise(r => setTimeout(r, 1500)); const n = (msgs || []).filter(m => m.role === 'user').length; return { fa: 'سلام!', translit: 'salâm!', en: 'Salut !', written: 'سلام!', written_translit: 'salâm!', feedback: null, suggestions: [], new_words: [], goals_done: [], pace: 'same', done: false, you_said: { translit: 'khubam, mersi', en: 'Je vais bien, merci' } }; } }; aiState = 'ready';"""
with sync_playwright() as p:
    b=p.chromium.launch(); c=b.new_context(viewport={"width":390,"height":844})
    c.add_init_script("localStorage.setItem('alefba-v3', "+json.dumps(json.dumps(st))+")")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(ACC)))
    c.route("**/api/say*", lambda r: r.fulfill(status=404, body=""))
    pg=c.new_page(); errs=[]; pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1200)
    pg.evaluate(STUB+" openTalk(LESSONS.find(l => l.kind === 'talk'))"); pg.wait_for_timeout(400)
    pg.click("#startTalkBtn"); pg.wait_for_selector("#chat .msg.ai", timeout=8000)
    # a line the microphone heard (already glossed when the heard card showed it)
    pg.evaluate("GLOSSED.set(langOf().k + '|' + 'خوبم، مرسی', { translit: 'khubam, mersi', meaning: 'Je vais bien, merci' }); send('خوبم، مرسی')")
    pg.wait_for_timeout(150)
    ms0=pg.query_selector_all("#chat .msg.me"); t=ms0[-1].inner_text() if ms0 else ""
    check(f"a spoken line shows its Finglish and meaning right away, before the reply ({t!r})", "khubam, mersi" in t and "Je vais bien" in t and len(pg.query_selector_all("#chat .msg.ai"))==1)
    pg.wait_for_timeout(1800)
    check("and it isn't shown twice when the reply comes", len(pg.query_selector_all("#chat .msg.me .said"))==1)
    # a typed Finglish line: shown when the reply arrives
    pg.fill("#talkInput","khubam mersi"); pg.click("#talkSend"); pg.wait_for_timeout(2000)
    ms=pg.query_selector_all("#chat .msg.me"); t2=ms[-1].inner_text()
    check(f"a typed line gets its meaning in the learner's language with the reply ({t2!r})", "Je vais bien" in t2)
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec28/yousaid.png")
    check("no page errors", not errs, errs)
    b.close()
print(f"{sum(res)}/{len(res)} passed")
