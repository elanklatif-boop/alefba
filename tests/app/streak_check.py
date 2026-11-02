import json, datetime
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:8811/"
FREE = {"talks": True, "plans": True, "signedIn": True, "canTalk": True, "kind": "free", "left": 3, "hearReady": True, "plan": None, "free": 3, "prices": {"basic":"$4.99","unlimited":"$6.49","yearly":"$39"}}
res=[]
def check(n, ok, x=""): res.append(ok); print(("PASS " if ok else "FAIL ")+n+("" if ok else f"  [{x}]"))
def st(days, best=None):
    s={"done":{},"items":{},"days":days,"talks":{},"prefs":{"lang":"en","fing":"auto"},"log":{},"speak":1,"read":0,"profile":{"name":"Elan","goal":2,"adult":False,"speakSelf":1,"readSelf":0,"reasons":[]}}
    if best: s["best"]=best
    return "if(!sessionStorage.getItem('x')){sessionStorage.setItem('x',1);localStorage.setItem('alefba-v3', "+json.dumps(json.dumps(s))+")}"
with sync_playwright() as p:
    b=p.chromium.launch()
    def page(init):
        c=b.new_context(viewport={"width":390,"height":844}); c.add_init_script(init)
        c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
        pg=c.new_page(); e=[]; pg.on("pageerror", lambda x: e.append(str(x))); pg.goto(BASE); pg.wait_for_timeout(900); return pg,e
    pg,e=page(st([]))
    t=pg.inner_text("#streak"); check("day 0: badge visible, 'Start a streak'", pg.is_visible("#streak") and "Start a streak" in t, t)
    pg.screenshot(path="streak0.png", clip={"x":0,"y":0,"width":390,"height":330})
    # finish a lesson -> day 1
    pg.evaluate("startLesson({ id: 'x', title: 'x' }, [exWordMeaning(WORDS.find(W => W.tr === 'mersi'), WORDS)])"); pg.wait_for_timeout(300)
    pg.evaluate("finishLesson()"); pg.wait_for_timeout(300)
    t=pg.inner_text("#streakDone") if pg.locator("#streakDone").count() else ""
    check("finish screen shows Day 1 streak message", "Day 1" in t, t)
    pg.screenshot(path="streak_finish.png")
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    t=pg.inner_text("#streak"); check("header: '1 day streak' lit", "1 day streak" in t and "lit" in pg.get_attribute("#streak","class"), t)
    # finishing again today: no repeat message
    pg.evaluate("startLesson({ id: 'y', title: 'y' }, [exWordMeaning(WORDS.find(W => W.tr === 'mersi'), WORDS)])"); pg.wait_for_timeout(200)
    pg.evaluate("finishLesson()"); pg.wait_for_timeout(200)
    check("second lesson same day: no streak message again", pg.locator("#streakDone").count()==0)
    check("no page errors", not e, e); pg.context.close()
    # 2 days before, not today
    days=pg and None
    pg,e=page("")  # placeholder
    pg.context.close()
    ds=[ (datetime.date.today()-datetime.timedelta(days=i)).isoformat() for i in (1,2,3)]
    pg,e=page(st(ds,best=5))
    fmt=pg.evaluate("[todayStr(), daysAgo(1)]")
    if fmt[0]!=datetime.date.today().isoformat():
        ds=pg.evaluate("[daysAgo(1),daysAgo(2),daysAgo(3)]"); pg.context.close(); pg,e=page(st(ds,best=5))
    t=pg.inner_text("#streak"); check("3-day streak not done today: reminder, flame not lit", "3 days streak" in t and "not yet today" in t and "keeps your 3-day streak going" in pg.inner_text("#streakNudge") and "lit" not in pg.get_attribute("#streak","class"), t)
    pg.screenshot(path="streak3.png", clip={"x":0,"y":0,"width":390,"height":330})
    pg.evaluate("startLesson({ id: 'x', title: 'x' }, [exWordMeaning(WORDS.find(W => W.tr === 'mersi'), WORDS)])"); pg.wait_for_timeout(200)
    pg.evaluate("finishLesson()"); pg.wait_for_timeout(200)
    t=pg.inner_text("#streakDone"); check("4th day finish: '4 days in a row' with Best: 5", "4 days in a row" in t and "Best: 5" in t, t)
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    t=pg.inner_text("#streak"); check("header shows best 5", "4 days streak" in t and "best 5" in t, t)
    check("no page errors", not e, e)
    # dark mode screenshot
    pg.emulate_media(color_scheme="dark"); pg.wait_for_timeout(200); pg.screenshot(path="streak_dark.png", clip={"x":0,"y":0,"width":390,"height":330})
    pg.context.close()
    b.close()
print(f"{sum(res)}/{len(res)} passed")
