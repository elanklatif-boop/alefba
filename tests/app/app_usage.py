import json, datetime
from playwright.sync_api import sync_playwright
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
res=[]
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
today = datetime.date.today()
ds = lambda k: (today - datetime.timedelta(days=k)).isoformat()
def st(**kw):
    s={"done": {"a1-1": True}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 1, "read": 1,
       "profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
    s.update(kw); return s
def run(b, state, then=None, reload=False):
    sent=[]
    c=b.new_context(viewport={"width":390,"height":844})
    if state is not None: c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    def usage(r):
        try: sent.append(json.loads(r.request.post_data))
        except Exception: pass
        r.fulfill(status=200, content_type="application/json", body='{"ok":true}')
    c.route("**/api/usage", usage)
    pg=c.new_page(); errs=[]; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1200)
    if then: then(pg)
    pg.evaluate("sendUsage()"); pg.wait_for_timeout(400)
    if reload:
        pg.reload(); pg.wait_for_timeout(1200); pg.evaluate("sendUsage()"); pg.wait_for_timeout(400)
    S=pg.evaluate("({ firstDay: S.firstDay, statDay: S.statDay })")
    c.close()
    ev=[e for p in sent for e in p["e"]]
    return ev, sent, S, errs
with sync_playwright() as p:
    b=p.chromium.launch()
    ev,sent,S,errs = run(b, None, reload=True)
    check(f"a brand-new visitor: open, new, child, counted once even after a reload ({ev})", sorted(ev)==sorted(["open","new","open_child"]), ev)
    check("their first day is saved", S["firstDay"]==today.isoformat() and S["statDay"]==today.isoformat(), S)
    check("the date sent is the visitor's own", all(x["d"]==today.isoformat() for x in sent), sent)
    ev,_,_,_ = run(b, st(firstDay=ds(1), statDay=ds(1)))
    check(f"back the next day ({ev})", "back_1" in ev and "open" in ev and "new" not in ev, ev)
    ev,_,_,_ = run(b, st(firstDay=ds(5), statDay=ds(2)))
    check(f"back after 5 days ({ev})", "back_2_7" in ev, ev)
    ev,_,S,_ = run(b, st(days=[ds(13), ds(12)]))
    check(f"someone from before the counting began: their first practice day counts ({ev})", "back_8_30" in ev and "new" not in ev and S["firstDay"]==ds(13), (ev,S))
    ev,_,_,_ = run(b, st(firstDay=ds(40), statDay=ds(3), profile={"name": "Ali", "goal": 2, "adult": True, "speakSelf": 1, "readSelf": 1, "reasons": []}))
    check(f"an adult, back after a month ({ev})", "back_31" in ev and "open_adult" in ev, ev)
    ev,_,_,errs = run(b, st(firstDay=ds(0), statDay=ds(0)), then=lambda pg: (pg.evaluate("openLesson(LESSONS.find(l => l.kind === 'words' && l.level.index === 0))"), pg.wait_for_timeout(300), pg.evaluate("finishLesson()"), pg.wait_for_timeout(300)))
    check(f"already counted today; a lesson started and finished ({ev})", sorted(ev)==["lesson_done","lesson_start"], ev)
    check("no page errors", not errs, errs)
    b.close()
print(f"{sum(res)}/{len(res)} passed")
