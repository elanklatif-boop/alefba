# What brings people back, on the finish screen of the first lessons: after the first lesson everyone gets the come-back
# card (a daily calendar reminder in one tap at about this time of day, or an email instead); then "who's learning?"
# (twice, for someone who passes over it), then the home-screen icon; and the offers are counted.
import json, sys
from playwright.sync_api import sync_playwright
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3, "prices": {"basic": "$5", "unlimited": "$6.49", "yearly": "$39"}}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
CARDS = "['comebackCard','whoCard','nudgeCard','installBanner','remindCard'].filter(i => { const e = document.querySelector('#exBox #' + i); return e && e.offsetParent !== null; })"
def fresh(b):
    c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    sent = []; c.route("**/api/usage*", lambda r: (sent.append(r.request.post_data or ""), r.fulfill(status=204, body=""))[1])
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1300)
    pg.click("#obHeard"); pg.wait_for_timeout(600)   # Already speak some Persian? (the free first lesson that starts with words they know)
    return c, pg, errs, sent
def finish(pg, first=False):
    if not first: pg.evaluate("openLesson(nextLesson())"); pg.wait_for_timeout(300)
    pg.evaluate("finishLesson()"); pg.wait_for_timeout(500); return pg.evaluate(CARDS)
with sync_playwright() as p:
    b = p.chromium.launch()
    # 1. passes over everything
    c, pg, errs, sent = fresh(b)
    seen = [finish(pg, True)]
    for _ in range(5): pg.evaluate("closeLesson()"); pg.wait_for_timeout(200); seen.append(finish(pg))
    check("lesson 1: see you tomorrow?", seen[0] == ["comebackCard"], seen)
    check("lessons 2 and 3: who's learning", seen[1] == ["whoCard"] and seen[2] == ["whoCard"], seen)
    check("lesson 4: the home-screen icon", seen[3] == ["installBanner"], seen)
    check("lessons 5 and 6: nothing more to ask", seen[4] == [] and seen[5] == [], seen)
    pg.wait_for_timeout(4500)
    check("the card is counted once (comeback_show), and no email offer was opened", sum(s.count("comeback_show") for s in sent) == 1 and not any("nudge_show" in s for s in sent), sent)
    check("no page errors (passes over)", not errs, errs); c.close()
    # 2. one tap on the calendar
    c, pg, errs, sent = fresh(b)
    finish(pg, True)
    t = pg.inner_text("#comebackCard"); want = pg.evaluate("(() => { const d = new Date(), q = Math.round((d.getHours() * 60 + d.getMinutes()) / 15) * 15 % 1440; return hm12(String(Math.floor(q / 60)).padStart(2, '0') + ':' + String(q % 60).padStart(2, '0')); })()")
    check(f"the card: next lesson, and a reminder tomorrow at about this time ({want})", "See you tomorrow?" in t and "Next up:" in t and f"Remind me tomorrow at {want}" in t and "daily" not in t, t)
    href = pg.get_attribute("#comebackCal", "href")
    check("on this (non-Apple) browser the big button is Google Calendar, just tomorrow (no repeat)", href.startswith("https://calendar.google.com/") and "FREQ" not in href and "recur" not in href and pg.get_attribute("#comebackCal", "target") == "_blank", href)
    check("and the phone's other calendar (.ics, once) is a small link", "/api/reminder.ics" in pg.get_attribute("#comebackCalOther", "href") and "once=1" in pg.get_attribute("#comebackCalOther", "href"))
    pg.click("#comebackChange"); pg.fill("#comebackTime", "19:30"); pg.wait_for_timeout(100)
    check("Change the time: the button and both links follow", "7:30 pm" in pg.inner_text("#comebackCal") and "T193000" in pg.get_attribute("#comebackCal", "href") and "t=1930" in pg.get_attribute("#comebackCalOther", "href"))
    pg.locator("#comebackCard").scroll_into_view_if_needed(); pg.screenshot(path=(sys.argv[1] if len(sys.argv) > 1 else "/tmp/") + "returns_comeback.png")
    pg.evaluate("document.getElementById('comebackCal').addEventListener('click', e => e.preventDefault())"); pg.click("#comebackCal"); pg.wait_for_timeout(600)
    check("one tap sets it, for tomorrow (not a daily one in Settings)", "Reminder added" in pg.inner_text("#comebackCard") and "Tomorrow at 7:30 pm" in pg.inner_text("#comebackCard") and pg.evaluate("S.prefs.remindOnce") == "19:30" and not pg.evaluate("S.prefs.remind"))
    pg.wait_for_timeout(4500)
    check("and it's counted (cal_on, and cb_cal for the first-lesson table)", any("cal_on" in s for s in sent) and any("cb_cal" in s for s in sent), sent)
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(200)
    seen = [finish(pg), None]; pg.evaluate("closeLesson()"); pg.wait_for_timeout(200); seen[1] = finish(pg)
    check("later lessons don't ask about the email or the calendar again", not any(x in seen[0] + seen[1] for x in ("comebackCard", "nudgeCard", "remindCard")), seen)
    check("no page errors (calendar)", not errs, errs); c.close()
    # 3. on an iPhone the big button is the phone's own calendar
    c = b.new_context(**p.devices["iPhone 13"])
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    c.route("**/api/usage*", lambda r: r.fulfill(status=204, body=""))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1300); pg.click("#obHeard"); pg.wait_for_timeout(600)
    finish(pg, True)
    check("iPhone: the big button adds it to the iPhone's calendar, Google is the small link", "/api/reminder.ics" in pg.get_attribute("#comebackCal", "href") and "Google Calendar" in pg.inner_text("#comebackCalOther"))
    check("no page errors (iPhone)", not errs, errs); c.close()
    # 4. an email instead
    c, pg, errs, sent = fresh(b)
    finish(pg, True); pg.click("#comebackEmail"); pg.wait_for_timeout(300)
    t = pg.inner_text("#nudgeCard") if pg.is_visible("#nudgeCard") else ""
    check("Email me tomorrow instead opens the email form in the card", "want an email" in t.lower() and pg.is_visible("#nudgeEmail") and pg.is_visible("#comebackCal"), t)
    pg.wait_for_timeout(4500)
    check("and that's counted as the email offer being shown", any("nudge_show" in s for s in sent), sent)
    check("no page errors (email)", not errs, errs); c.close()
    # 5. the big button after the first lesson goes straight on into the next lesson, and that's counted
    c, pg, errs, sent = fresh(b)
    finish(pg, True)
    mb = pg.inner_text("#mainBtn"); nx = pg.evaluate("nextLesson().title")
    check(f"the main button says Keep going, with the next lesson and its minutes ({mb})", mb.startswith(f"Keep going: {nx}, about ") and mb.endswith(" minutes"), mb)
    pg.click("#mainBtn"); pg.wait_for_timeout(300)
    check("a tap straight after the finish (a double tap) doesn't skip the finish screen", pg.evaluate("!!(R && R.finish)"))
    pg.wait_for_timeout(700); pg.click("#mainBtn"); pg.wait_for_timeout(500)
    check("a tap on it starts that lesson", pg.evaluate("!!(R && !R.finish && R.lesson && R.lesson.title)") == True and pg.evaluate("R.lesson.title") == nx)
    pg.evaluate("closeLesson()"); pg.wait_for_timeout(4500)
    check("counted as cb_keep", any("cb_keep" in s for s in sent), sent)
    finish(pg); check("the second lesson's button is Back to lessons again", pg.inner_text("#mainBtn") == "Back to lessons", pg.inner_text("#mainBtn"))
    check("no page errors (keep going)", not errs, errs); c.close()
    # 6. No thanks is counted
    c, pg, errs, sent = fresh(b)
    finish(pg, True); pg.click("#comebackNo"); pg.wait_for_timeout(4500)
    check("No thanks closes the card and is counted (cb_no)", not pg.is_visible("#comebackCard") and any("cb_no" in s for s in sent), sent)
    c.close()
    # 7. nobody has said who's learning: the email form asks for a grown-up's email, never a child's own
    c, pg, errs, sent = fresh(b)
    finish(pg, True); pg.click("#comebackEmail"); pg.wait_for_timeout(300)
    check("not said who's learning: 'A grown-up's email', for grown-ups", pg.get_attribute("#nudgeEmail", "placeholder") == "A grown-up's email" and "Grown-ups" in pg.inner_text("#nudgeCard"), pg.inner_text("#nudgeCard"))
    c.close()
    # 8. inside Instagram's browser: email first; on an iPhone no calendar (it can't open there); on Android it opens in Chrome
    IG_IOS = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 357.0.0.25.101 (iPhone15,2; iOS 18_1; en_US; en; scale=3.00; 1179x2556; 659315223)"
    IG_AND = "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP2A.240905.003; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36 Instagram 357.0.0.25.101 Android (34/14; 420dpi; 1080x2205; Google/google; Pixel 8; shiba; shiba; en_US; 659315229)"
    for name, ua in (("iPhone", IG_IOS), ("Android", IG_AND)):
        c = b.new_context(viewport={"width": 390, "height": 844}, user_agent=ua, has_touch=True, is_mobile=True)
        c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
        c.route("**/api/usage*", lambda r: r.fulfill(status=204, body=""))
        pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(1300); pg.click("#obHeard"); pg.wait_for_timeout(600)
        finish(pg, True)
        em_first = pg.evaluate("(() => { const k = [...document.querySelectorAll('#comebackCard > *')]; return k.findIndex(x => x.id === 'comebackEmail') < Math.max(0, k.findIndex(x => x.id === 'comebackCal')) || !document.getElementById('comebackCal'); })()")
        check(f"Instagram on {name}: Email me tomorrow is the big button, first", em_first and "btn primary" in pg.get_attribute("#comebackEmail", "class"))
        if name == "iPhone":
            check("…no calendar button (it can't open from inside Instagram), and it says why", not pg.locator("#comebackCal").count() and "can't be added from inside Instagram" in pg.inner_text("#comebackCard"), pg.inner_text("#comebackCard"))
        else:
            h = pg.get_attribute("#comebackCal", "href") or ""
            check("…the calendar opens Google Calendar in Chrome, with the plain page as the fallback", h.startswith("intent://calendar.google.com/calendar/render?") and "package=com.android.chrome" in h and "S.browser_fallback_url=https%3A%2F%2Fcalendar.google.com" in h and "opens Chrome" in pg.inner_text("#comebackCal"), h)
        pg.click("#comebackEmail"); pg.wait_for_timeout(300)
        check(f"…and the email form opens (Instagram, {name})", pg.is_visible("#nudgeEmail"))
        pg.screenshot(path=(sys.argv[1] if len(sys.argv) > 1 else "/tmp/") + f"returns_instagram_{name}.png")
        check(f"no page errors (Instagram {name})", not errs, errs); c.close()
    b.close()
print(f"{sum(res)} of {len(res)} passed")
