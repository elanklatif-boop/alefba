# What brings people back, on the finish screen of the first lessons: someone who passes over "who's learning?" is still
# offered the email (on the second lesson), then the home-screen icon, then the calendar reminder; turning the email
# down offers the calendar in its place; and the offers are counted.
import json, sys
from playwright.sync_api import sync_playwright
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3, "prices": {"basic": "$5", "unlimited": "$6.49", "yearly": "$39"}}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
CARDS = "['whoCard','nudgeCard','installBanner','remindCard'].filter(i => { const e = document.querySelector('#exBox #' + i); return e && e.offsetParent !== null; })"
def fresh(b):
    c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    sent = []; c.route("**/api/usage*", lambda r: (sent.append(r.request.post_data or ""), r.fulfill(status=204, body=""))[1])
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1300)
    pg.click("#obAlt"); pg.wait_for_timeout(300); pg.locator("#obMain button").first.click(); pg.wait_for_timeout(600)   # Try a free lesson, then its one question
    return c, pg, errs, sent
def finish(pg, first=False):
    if not first: pg.evaluate("openLesson(nextLesson())"); pg.wait_for_timeout(300)
    pg.evaluate("finishLesson()"); pg.wait_for_timeout(500); return pg.evaluate(CARDS)
with sync_playwright() as p:
    b = p.chromium.launch()
    # 1. passes over the question every time
    c, pg, errs, sent = fresh(b)
    seen = [finish(pg, True)]
    for _ in range(5): pg.evaluate("closeLesson()"); pg.wait_for_timeout(200); seen.append(finish(pg))
    check("lesson 1: who's learning", seen[0] == ["whoCard"], seen)
    check("lesson 2: the email offer gets its turn", seen[1] == ["nudgeCard"], seen)
    check("lesson 3: the question once more", seen[2] == ["whoCard"], seen)
    check("lesson 4: the home-screen icon", seen[3] == ["installBanner"], seen)
    check("lesson 5: the calendar reminder", seen[4] == ["remindCard"], seen)
    check("lesson 6: nothing more to ask", seen[5] == [], seen)
    pg.wait_for_timeout(4500)
    check("the email offer being shown is counted once (nudge_show)", sum(s.count("nudge_show") for s in sent) == 1, sent)
    check("no page errors (passes over)", not errs, errs); c.close()
    # 2. turns the email down: the calendar reminder in its place
    c, pg, errs, sent = fresh(b)
    finish(pg, True); pg.evaluate("closeLesson()"); pg.wait_for_timeout(200); finish(pg)
    t = pg.inner_text("#nudgeCard")
    check("the email offer doesn't assume who it's for", "This is my email" in t and "Grown-ups" not in t, t)
    pg.click("#nudgeNo"); pg.wait_for_timeout(300)
    check("No thanks: the calendar reminder is offered in its place", pg.evaluate(CARDS) == ["remindCard"] and "reminder to practise" in pg.inner_text("#remindCard"), pg.evaluate(CARDS))
    pg.locator("#remindCard").scroll_into_view_if_needed(); pg.screenshot(path=(sys.argv[1] if len(sys.argv) > 1 else "/tmp/") + "returns_calendar.png")
    pg.evaluate("document.getElementById('remindGoogle').addEventListener('click', e => e.preventDefault())"); pg.click("#remindGoogle"); pg.wait_for_timeout(600)
    check("choosing a calendar sets it", "Reminder set" in pg.inner_text("#remindCard") and pg.evaluate("S.prefs.remind") == "17:00")
    pg.wait_for_timeout(4500)
    check("and it's counted (cal_on)", any("cal_on" in s for s in sent), sent)
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    seen = [finish(pg), None]; pg.evaluate("closeLesson()"); pg.wait_for_timeout(200); seen[1] = finish(pg)
    check("later lessons don't ask for the email or the calendar again", "nudgeCard" not in seen[0] + seen[1] and "remindCard" not in seen[0] + seen[1], seen)
    check("no page errors (turns it down)", not errs, errs); c.close()
    # 3. answers the question: the email offer straight after, as before, and the home screen on the next lesson
    c, pg, errs, sent = fresh(b)
    finish(pg, True); pg.click("#whoMe"); pg.wait_for_timeout(400)
    check("says who's learning: the email offer follows at once", pg.evaluate(CARDS) == ["nudgeCard"] and "Want an email" in pg.inner_text("#nudgeCard"), pg.evaluate(CARDS))
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    check("the next lesson offers the home-screen icon, not the email again", finish(pg) == ["installBanner"])
    check("no page errors (answers)", not errs, errs); c.close()
    b.close()
print(f"{sum(res)} of {len(res)} passed")
