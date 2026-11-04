# The reminder email in the app: offered once after the first lesson, it books the email, each later lesson moves it,
# Settings shows it and can stop it, and a visit from the email is counted.
import json
from playwright.sync_api import sync_playwright
res=[]
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
URL="http://127.0.0.1:8811/"
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
def st(done=None, adult=False):
    return {"done": done or {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 1, "read": 1,
            "profile": {"name": "Sara", "goal": 2, "adult": adult, "speakSelf": 1, "readSelf": 1, "reasons": []}}
calls=[]
def page(b, state, url=URL, start_status=200):
    c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    def api(r):
        p = r.request.url.split("/api/")[1].split("?")[0]
        body = r.request.post_data_json if r.request.post_data else None
        calls.append((p, body))
        if p == "nudge/start": return r.fulfill(status=start_status, content_type="application/json", body=json.dumps({"ok": True, "token": "T" * 43} if start_status == 200 else {"error": "too_many"}))
        return r.fulfill(status=200, content_type="application/json", body='{"ok":true}')
    c.route("**/api/nudge**", api); c.route("**/api/usage", api)
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto(url); pg.wait_for_timeout(1300); return c, pg, errs
def finish_first(pg):
    pg.evaluate("openLesson(nextLesson())"); pg.wait_for_timeout(300); pg.evaluate("finishLesson()"); pg.wait_for_timeout(400)
with sync_playwright() as p:
    b = p.chromium.launch()
    c, pg, errs = page(b, st())
    finish_first(pg)
    check("after the first lesson: what's next, with its letters", pg.is_visible("#upNext") and pg.locator("#upNext .up-glyphs").count() <= 1)
    check("and the email offer, for a grown-up", pg.is_visible("#nudgeCard") and "Grown-ups" in pg.inner_text("#nudgeCard") and "parent or guardian" in pg.inner_text("#nudgeCard"))
    pg.locator("#nudgeCard").scroll_into_view_if_needed(); pg.screenshot(path="nudge/card_child.png")
    pg.click("#nudgeGo"); pg.wait_for_timeout(200)
    check("no address: it asks for one", "doesn't look right" in pg.inner_text("#nudgeCard"))
    pg.fill("#nudgeEmail", "mum@example.com"); pg.click("#nudgeGo"); pg.wait_for_timeout(200)
    check("the box not ticked: it asks", "tick the box" in pg.inner_text("#nudgeCard") and not any(x[0] == "nudge/start" for x in calls))
    pg.check("#nudgeAgree"); pg.click("#nudgeGo"); pg.wait_for_timeout(500)
    start = [x for x in calls if x[0] == "nudge/start"]
    check(f"it books the email, saying what's next ({start[-1][1] if start else None})", start and start[-1][1]["email"] == "mum@example.com" and start[-1][1]["agree"] is True and start[-1][1]["next"]["t"])
    check("and says it's done, with the spam tip", pg.is_visible("#nudgeDone") and "spam" in pg.inner_text("#nudgeCard"))
    check("the device keeps the token and address", json.loads(pg.evaluate("localStorage.getItem('alefba-nudge')")) == {"token": "T" * 43, "email": "mum@example.com"})
    pg.locator("#nudgeCard").scroll_into_view_if_needed(); pg.screenshot(path="nudge/card_done.png")
    pg.wait_for_timeout(4500)
    check("counted for the stats", any(x[0] == "usage" and "nudge_on" in (x[1] or {}).get("e", []) for x in calls))
    pg.evaluate("closeLesson()"); finish_first(pg)
    mv = [x for x in calls if x[0] == "nudge"]
    check(f"the next lesson moves the email ({mv[-1][1] if mv else None})", mv and mv[-1][1]["token"] == "T" * 43)
    check("not offered again", not pg.is_visible("#nudgeCard"))
    pg.evaluate("closeLesson(); showView('review')"); pg.wait_for_timeout(300)
    check("Settings shows it's on", pg.is_visible("#nudgeRow") and "mum@example.com" in pg.inner_text("#nudgeRow"))
    pg.locator("#nudgeRow").scroll_into_view_if_needed(); pg.screenshot(path="nudge/settings_on.png")
    pg.click("#nudgeStop"); pg.wait_for_timeout(300)
    check("Stop: tells the server and forgets it", any(x[0] == "nudge/stop" and x[1]["token"] == "T" * 43 for x in calls) and pg.evaluate("localStorage.getItem('alefba-nudge')") is None and "off" in pg.inner_text("#nudgeRow"))
    pg.click("#nudgeOn"); pg.wait_for_timeout(200)
    check("and it can be turned on again from Settings", pg.is_visible("#nudgeSetCard"))
    pg.locator("#nudgeSetCard").scroll_into_view_if_needed(); pg.screenshot(path="nudge/settings_form.png")
    check("no page errors", not errs, errs)
    c.close()
    # an adult, saying no thanks
    c, pg, errs = page(b, st(adult=True))
    finish_first(pg)
    check("for an adult it says 'your email'", "Want an email" in pg.inner_text("#nudgeCard") and pg.get_attribute("#nudgeEmail", "placeholder") == "Your email")
    pg.locator("#nudgeCard").scroll_into_view_if_needed(); pg.screenshot(path="nudge/card_adult.png")
    pg.click("#nudgeNo"); pg.wait_for_timeout(200)
    check("No thanks closes it", not pg.is_visible("#nudgeCard"))
    c.close()
    # a server that says no
    c, pg, errs = page(b, st(), start_status=429)
    finish_first(pg); pg.fill("#nudgeEmail", "mum@example.com"); pg.check("#nudgeAgree"); pg.click("#nudgeGo"); pg.wait_for_timeout(400)
    check("a refusal is explained and nothing is kept", "try again tomorrow" in pg.inner_text("#nudgeCard") and pg.evaluate("localStorage.getItem('alefba-nudge')") is None)
    c.close()
    # coming from the email
    calls.clear()
    c, pg, errs = page(b, st({"a1-1": True}), url=URL + "?ref=email"); pg.wait_for_timeout(4500)
    check("a visit from the email is counted, and the address bar tidied", any(x[0] == "usage" and "from_email" in (x[1] or {}).get("e", []) for x in calls) and "ref=email" not in pg.url)
    check("no page errors", not errs, errs)
    c.close(); b.close()
print(f"{sum(res)}/{len(res)} passed")
