import json
from playwright.sync_api import sync_playwright
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
state={"done": {"a1-1": True}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters", "stTr": True, "stEn": True}, "log": {}, "speak": 1, "read": 1,
       "profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
res=[]
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
with sync_playwright() as p:
    b=p.chromium.launch()
    for dark in (False, True):
        c=b.new_context(viewport={"width":390,"height":844}, color_scheme="dark" if dark else "light")
        c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
        c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
        pg=c.new_page(); errs=[]; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1300)
        if not dark:
            r=pg.evaluate("""STORIES.concat(SEASON_PACKS.map(p=>p.story)).map(s => [s.title, s.lines.length, (STORY_WHO[s.title]||[]).length, s.lines.filter(l=>l.who).length])""")
            check("every story has a speaker list the same length as its lines", all(x[1]==x[2] for x in r), [x for x in r if x[1]!=x[2]])
            check("every story has at least one named speaker", all(x[3]>0 for x in r), r)
        pg.evaluate("startLesson({ id: 'st-test', title: 'Story' }, [{ type: 'story', story: STORIES[12] }])"); pg.wait_for_timeout(600)
        tags=pg.eval_on_selector_all(".story-list .story-who", "e => e.map(x => x.innerText.replace(/\\n/g,' '))")
        if not dark: check(f"A call from Shiraz shows 8 names ({tags[:3]}...)", len(tags)==8 and "Grandma" in tags[0] and "Sara" in tags[1], tags)
        pg.screenshot(path=f"stories/story_{'dark' if dark else 'light'}.png")
        check("no page errors", not errs, errs)
        c.close()
    b.close()
print(f"{sum(res)}/{len(res)} passed")
