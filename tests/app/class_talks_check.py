# The school plan with talks, in the app: a learner in such a class talks (and answers out loud) with the class key,
# nobody signs in; and the teacher can buy it only after ticking the box for the families, with a note to send home.
import json, sys, time
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8811/"
PAD = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/"
OUT = {"talks": True, "plans": True, "hearReady": True, "voiceReady": True, "signedIn": False, "free": 3}
DAY = 864e5
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
now = time.time() * 1000
def learner(left):
    return {"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto"}, "log": {}, "speak": 1, "read": 0,
            "profile": {"name": "Sara", "goal": 2, "adult": False, "whoSet": True, "speakSelf": 1, "readSelf": 0, "reasons": []},
            "cls": {"token": "T" * 43, "name": "Sara", "cname": "Saturday class", "assigned": [], "fullUntil": now + 300 * DAY, "talks": {"until": now + 300 * DAY, "per": 5, "left": left}}}
REPLY = {"fa": "سلام! حالت چطوره؟", "translit": "salâm! hâlet chetore?", "en": "Hi! How are you?", "written": "سلام!", "written_translit": "salâm!", "feedback": None,
         "suggestions": [{"fa": "خوبم.", "translit": "khubam.", "en": "I'm good."}], "new_words": [], "goals_done": [], "pace": "same", "done": False, "you_said": None, "talk_id": "T1"}
def page(b, st, me=OUT, extra=None):
    c = b.new_context(viewport={"width": 390, "height": 844})
    c.add_init_script("localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(st)) + ")")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(me)))
    c.route("**/api/usage", lambda r: r.fulfill(status=200, body="{}"))
    talks = []
    def talk(r):
        talks.append({"key": r.request.headers.get("x-alefba-class"), "body": json.loads(r.request.post_data)})
        body = json.dumps({"early": {"fa": REPLY["fa"]}}) + "\n" + json.dumps({"reply": {**REPLY, "class": {"name": "Saturday class", "assigned": [], "fullUntil": now + 300 * DAY, "talks": {"until": now + 300 * DAY, "per": 5, "left": 3}}}}) + "\n"
        r.fulfill(status=200, content_type="application/x-ndjson", body=body)
    c.route("**/api/talk", talk)
    if extra: extra(c)
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto(URL); pg.wait_for_timeout(1300)
    pg.evaluate("if (!$('onboard').hidden) closeOnboarding(); 0")
    return c, pg, errs, talks
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- a learner whose class has talks ----
    c, pg, errs, talks = page(b, learner(4))
    pg.evaluate("showView('lessons'); 0"); pg.wait_for_timeout(300)
    check("the class card says talks are included, and how many are left", "Talks with the characters are included. 4 of 5 class talks left this month" in pg.inner_text("#classCard"), pg.inner_text("#classCard"))
    pg.evaluate("openTalk(LESSONS.find(l => l.kind === 'talk')); 0"); pg.wait_for_timeout(600)
    sa = pg.inner_text("#startArea")
    check("a talk can start with nobody signed in", pg.is_visible("#startTalkBtn") and not pg.locator("#grownUpBtn").count(), sa)
    check("and says how many class talks are left", "4 of 5 class talks left this month" in sa, sa)
    check("answering out loud and Voice mode are there too (the class key covers them)", pg.evaluate("canHear() && canVoiceMode()"))
    pg.screenshot(path=PAD + "class_talk_start.png")
    pg.click("#startTalkBtn"); pg.wait_for_timeout(1200)
    check("the talk is sent with the class key", talks and talks[0]["key"] == "T" * 43, talks)
    check("the character answers", "سلام" in pg.inner_text("#chat"))
    check("and the learner's talks left are updated from the reply", pg.evaluate("S.cls.talks.left") == 3)
    check("no page errors", not errs, errs); c.close()

    # ---- the month's class talks are used up ----
    c, pg, errs, talks = page(b, learner(0))
    pg.evaluate("openTalk(LESSONS.find(l => l.kind === 'talk')); 0"); pg.wait_for_timeout(600)
    sa = pg.inner_text("#startArea")
    check("used up: it says so, and that more come next month", "used up" in sa and "more next month" in sa and not pg.locator("#startTalkBtn").count(), sa)
    check("with no plans button for a child to press", not pg.locator("#plansBtn").count())
    check("no page errors", not errs, errs); c.close()

    # ---- a family with its own paid plan uses that, not the class ----
    fam = {**OUT, "signedIn": True, "plan": "unlimited", "kind": "unlimited", "canTalk": True, "hear": True, "voice": True, "perDay": 30, "email": "x@example.com"}
    c, pg, errs, talks = page(b, learner(4), fam)
    pg.evaluate("openTalk(LESSONS.find(l => l.kind === 'talk')); 0"); pg.wait_for_timeout(600); pg.click("#startTalkBtn"); pg.wait_for_timeout(1000)
    check("a family's own paid plan is used first (no class key sent)", talks and not talks[0]["key"], talks)
    c.close()

    # ---- the teacher ----
    TEACHER = {**OUT, "signedIn": True, "plan": None, "kind": "free", "canTalk": True, "left": 3, "email": "t@example.com", "classTalks": 5,
               "prices": {"basic": "$5", "unlimited": "$6.49", "yearly": "$39", "school": "$49", "schoolTalks": "$59.99", "schoolUpgrade": "$10.99"}}
    for case in ["none", "school", "talks"]:
        cls = {"id": "a" * 24, "name": "Saturday class", "code": "ABC123", "assigned": [], "paidUntil": 0, "talksUntil": 0, "pending": False, "members": []}
        if case == "school": cls["paidUntil"] = now + 200 * DAY
        if case == "talks": cls["paidUntil"] = cls["talksUntil"] = now + 300 * DAY
        bought = []
        def extra(ctx, cls=cls, bought=bought):
            ctx.route("**/api/class/view", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"class": cls})))
            ctx.route("**/api/class/checkout", lambda r: (bought.append(json.loads(r.request.post_data)), r.fulfill(status=200, content_type="application/json", body=json.dumps({"url": URL + "?paying"}))))
        st = learner(4); del st["cls"]; st["profile"]["adult"] = True
        c, pg, errs, talks = page(b, st, TEACHER, extra)
        pg.evaluate("$('onboard').inert = true; openOverlay('teach'); teachClass('" + "a" * 24 + "'); 0"); pg.wait_for_timeout(800)
        t = pg.inner_text("#schoolSec")
        if case == "none":
            check("a class with no plan sees both: with talks ($59.99 a year) and lessons only ($49)", "Get the plan with talks ($59.99 a year)" in t and "Lessons only ($49 a year)" in t and "5 talks a month" in t, t)
            check("the agreement box and the note for families are there", pg.is_visible("#schoolAgreeBox") and pg.get_attribute("#schoolNoteLink", "href") == "class-note?class=Saturday%20class")
            pg.screenshot(path=PAD + "class_teacher.png", full_page=True)
            pg.click("#schoolBuyTalks"); pg.wait_for_timeout(300)
            check("buying talks without ticking the box: it asks for it, nothing is bought", not bought and "Tick the box first" in pg.inner_text("#schoolSec"), bought)
            pg.check("#schoolAgreeBox"); pg.click("#schoolBuyTalks"); pg.wait_for_timeout(800)
            check("ticked: the checkout is for talks, with the agreement", bought == [{"id": "a" * 24, "kind": "talks", "agree": True}], bought)
        elif case == "school":
            check("a class with the school plan can add talks for the difference, until the plan ends", "Add talks until" in t and "($10.99)" in t and not pg.locator("#schoolBuy").count(), t)
        else:
            check("a class with talks says so, and buys nothing more yet", "with talks" in t and "5 talks a month each" in t and not pg.locator("#schoolBuyTalks").count() and not pg.locator("#schoolBuy").count() and pg.is_visible("#schoolNoteLink"), t)
        check(f"no page errors ({case})", not errs, errs); c.close()

    # ---- the note for families ----
    c = b.new_context(viewport={"width": 390, "height": 844}); pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto(URL + "class-note.html?class=Saturday%20class"); pg.wait_for_timeout(500)
    t = pg.inner_text("#note")
    check("the note has the class's name and says what's kept and what isn't", "Our class is using Alefba: Saturday class" in t and "never recorded or stored" in t and "5 talks a month" in t and "removed from the class" in t, t[:300])
    pg.screenshot(path=PAD + "class_note.png", full_page=True)
    pg.goto(URL + "class-note.html?class=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E"); pg.wait_for_timeout(300)
    check("a name in the link is shown as text only", pg.locator("#note img").count() == 0)
    check("no page errors (note)", not errs, errs); c.close()
    b.close()
print(f"{sum(res)} of {len(res)} passed")
sys.exit(0 if all(res) else 1)
