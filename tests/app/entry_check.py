# Finding the way in: the welcome shows "Join your class" and "I'm a teacher" where they can't be missed; a teacher's
# link (#join=CODE) opens joining with the code filled in; the class's age group (set by the teacher) decides the
# learner's mode; and someone who starts straight from the welcome is asked who's learning after the first lesson,
# with wording that doesn't assume a child until then.
import json, re, sys
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8811/"
PAD = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/"
OUT = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def cls(ages): return {"name": "Saturday class", "ages": ages, "assigned": [], "fullUntil": 0, "talks": None}
def page(b, me=OUT, state=None, join_ages="teens", progress_ages=None, wide=False):
    c = b.new_context(viewport={"width": 1100 if wide else 390, "height": 900 if wide else 844})
    if state: c.add_init_script("localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ")")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(me)))
    c.route("**/api/usage", lambda r: r.fulfill(status=200, body="{}"))
    joins = []
    def join(r): joins.append(json.loads(r.request.post_data)); r.fulfill(status=200, content_type="application/json", body=json.dumps({"token": "T" * 43, "name": "Sara", "class": cls(join_ages)}))
    c.route("**/api/class/join", join)
    c.route("**/api/class/progress", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"name": "Sara", "class": cls(progress_ages or join_ages)})))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    return c, pg, errs, joins
def gate(pg, id):
    q = pg.inner_text(f"#{id}Form"); a, b = map(int, re.findall(r"(\d+) × (\d+)", q)[0])
    pg.fill(f"#{id}Answer", str(a * b)); pg.click(f"#{id}Ok"); pg.wait_for_timeout(300)
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- the welcome ----
    for wide in (False, True):
        c, pg, errs, joins = page(b, wide=wide); pg.goto(URL); pg.wait_for_timeout(1300)
        jb, tb, lb = (pg.locator(x).bounding_box() for x in ("#obJoinBtn", "#obTeachBtn", "#obLittleBtn"))
        check(f"the welcome shows Join a class, Little one and I'm a teacher ({'wide' if wide else 'phone'})", all(pg.is_visible(x) for x in ("#obJoinBtn", "#obTeachBtn", "#obLittleBtn"))
              and "Join a class" in pg.inner_text("#obJoinBtn") and "I'm a teacher" in pg.inner_text("#obTeachBtn") and "3 to 6" in pg.inner_text("#obLittleBtn"))
        check(f"easy to tap, and on the first screen without scrolling ({jb})", all(x["height"] >= 40 for x in (jb, tb, lb)) and max(x["y"] + x["height"] for x in (jb, tb, lb)) < (900 if wide else 844))
        pg.screenshot(path=PAD + f"entry_welcome_{'wide' if wide else 'phone'}.png")
        c.close()
    c, pg, errs, joins = page(b); pg.goto(URL); pg.wait_for_timeout(1300)
    pg.click("#obJoinBtn"); pg.wait_for_timeout(300); gate(pg, "joinGate")
    check("Join your class asks for the code and a name", pg.is_visible("#joinCode") and pg.is_visible("#joinName"))
    pg.click("#joinCancel"); pg.wait_for_timeout(300)
    check("Not now goes back to the welcome", pg.is_visible("#onboard") and pg.is_visible("#obJoinBtn"))
    pg.click("#obTeachBtn"); pg.wait_for_timeout(400)
    check("I'm a teacher: sign in for teacher mode", "teacher mode" in pg.inner_text("#signTitle").lower(), pg.locator("#signTitle").count() and pg.inner_text("#signTitle"))
    check("no page errors", not errs, errs); c.close()

    # ---- a teacher's link, for a class of 13 and up ----
    c, pg, errs, joins = page(b); pg.goto(URL + "#join=abc234"); pg.wait_for_timeout(1300)
    gate(pg, "joinGate")
    check("the link opens joining with the code filled in", pg.input_value("#joinCode") == "ABC234", pg.locator("#joinCode").count() and pg.input_value("#joinCode"))
    check("and takes the code out of the address", "#join" not in pg.url)
    pg.screenshot(path=PAD + "entry_join.png")
    pg.fill("#joinName", "Sara"); pg.click("#joinOk"); pg.wait_for_timeout(900)
    prof = pg.evaluate("S.profile")
    check(f"joined: a class for 13 and up gives the teens' and adults' conversations ({prof})", joins and joins[0]["code"] == "ABC234" and prof["adult"] is True and prof["whoSet"] is True and prof["name"] == "Sara")
    check("the welcome is gone and the lessons are showing", pg.is_hidden("#onboard") and "Saturday class" in pg.inner_text("#classCard"))
    check("no page errors", not errs, errs); c.close()
    # a class for 7 to 12, which the teacher later changes to 13 and up
    c, pg, errs, joins = page(b, join_ages="kids", progress_ages="kids"); pg.goto(URL + "#join=ABC234"); pg.wait_for_timeout(1300)
    gate(pg, "joinGate"); pg.fill("#joinName", "Sara"); pg.click("#joinOk"); pg.wait_for_timeout(900)
    check("a class for 7 to 12 gives the children's conversations", pg.evaluate("S.profile.adult") is False and pg.evaluate("S.cls.ages") == "kids")
    pg.unroute("**/api/class/progress")
    pg.route("**/api/class/progress", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"name": "Sara", "class": cls("teens")})))
    pg.evaluate("syncClass(true)"); pg.wait_for_timeout(800)
    check("when the teacher changes it, the learner's mode follows", pg.evaluate("S.profile.adult") is True and pg.evaluate("S.cls.ages") == "teens")
    check("no page errors", not errs, errs); c.close()

    # ---- straight from the welcome: asked who's learning after the first lesson ----
    for pick, adult in (("whoMe", True), ("whoChild", False)):
        c, pg, errs, joins = page(b); pg.goto(URL); pg.wait_for_timeout(1300)
        pg.click("#obStart"); pg.wait_for_timeout(300); pg.click("#obfirst-no"); pg.wait_for_timeout(500)
        check("before saying who's learning, nothing assumes a child", pg.evaluate("talksToYou()") and pg.evaluate("plansBtnText()") == "Sign in to see the plans", pg.evaluate("plansBtnText()"))
        pg.evaluate("finishLesson()"); pg.wait_for_timeout(400)
        t = pg.inner_text("#whoCard")
        check("after the first lesson: who's learning, with the same four choices as everywhere", all(x in t for x in ["Teen or adult", "13 and up", "Child", "Ages 7 to 12", "Little one", "Ages 3 to 6", "Teacher", "Have a class code?"]), t)
        check("and only one question at a time (no email offer yet)", not pg.locator("#nudgeCard").count())
        if adult: pg.screenshot(path=PAD + "entry_who.png")
        pg.click("#" + pick); pg.wait_for_timeout(400)
        prof = pg.evaluate("S.profile")
        check(f"{pick}: saved ({prof})", prof["adult"] is adult and prof["whoSet"] is True and not pg.locator("#whoCard").count())
        check("then the wording fits", pg.evaluate("plansBtnText()") == ("Sign in to see the plans" if adult else "Ask a grown-up to sign in"), pg.evaluate("plansBtnText()"))
        check("the email offer comes after", pg.locator("#nudgeCard").count() == 1)
        check("no page errors", not errs, errs); c.close()
    # Little one opens little mode; Teacher goes straight to teacher mode (after signing in, with no sum)
    c, pg, errs, joins = page(b); pg.goto(URL); pg.wait_for_timeout(1300)
    pg.click("#obStart"); pg.wait_for_timeout(300); pg.click("#obfirst-no"); pg.wait_for_timeout(500)
    pg.evaluate("finishLesson()"); pg.wait_for_timeout(400); pg.click("#whoLittle"); pg.wait_for_timeout(600)
    check("Little one: little mode opens", pg.is_visible("#little") and pg.evaluate("S.profile.little") is True)
    check("no page errors", not errs, errs); c.close()
    c, pg, errs, joins = page(b, {**OUT, "signedIn": True, "email": "t@example.com"})
    c.route("**/api/class/list", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"classes": []})))
    pg.goto(URL); pg.wait_for_timeout(1300)
    pg.click("#obLevelBtn"); pg.wait_for_timeout(300)
    t = pg.inner_text("#obMain")
    check("the welcome's question has the same four choices", all(x in t for x in ["Teen or adult", "13 and up", "Child", "Ages 7 to 12", "Little one", "Ages 3 to 6", "Teacher"]), t)
    pg.click("#obwho-teacher"); pg.wait_for_timeout(700)
    check("Teacher: straight into teacher mode, no sum to answer", pg.is_visible("#teach") and not pg.locator("#teachGate").count())
    pg.screenshot(path=PAD + "entry_ob_who.png")
    check("no page errors", not errs, errs); c.close()

    # ---- the teacher picks who the class is for ----
    TEACHER = {**OUT, "signedIn": True, "email": "t@example.com", "prices": {"school": "$49", "schoolTalks": "$59.99", "schoolUpgrade": "$10.99"}, "classTalks": 5}
    st = {"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en"}, "log": {}, "speak": 1, "read": 0,
          "profile": {"name": "Ms T", "goal": 2, "adult": True, "whoSet": True, "speakSelf": 1, "readSelf": 0, "reasons": []}}
    c, pg, errs, joins = page(b, TEACHER, st)
    made, aged = [], []
    VIEW = {"id": "a" * 24, "name": "Saturday class", "code": "ABC234", "ages": None, "assigned": [], "paidUntil": 0, "talksUntil": 0, "pending": False, "members": []}
    c.route("**/api/class/list", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"classes": []})))
    c.route("**/api/class/create", lambda r: (made.append(json.loads(r.request.post_data)), r.fulfill(status=200, content_type="application/json", body=json.dumps({"class": {**VIEW, "ages": made[-1].get("ages")}}))))
    c.route("**/api/class/view", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"class": VIEW})))
    c.route("**/api/class/ages", lambda r: (aged.append(json.loads(r.request.post_data)), r.fulfill(status=200, content_type="application/json", body=json.dumps({"class": {**VIEW, "ages": aged[-1]["ages"]}}))))
    pg.goto(URL); pg.wait_for_timeout(1300)
    pg.evaluate("openTeacher()"); pg.wait_for_timeout(700)
    t = pg.inner_text("#teachMain")
    check("making a class asks who it's for: 4 to 6, 7 to 12, 13 and up", all(x in t for x in ["Who is the class for?", "Little ones, 3 to 6", "Little mode", "Children, 7 to 12", "Teens and adults, 13 and up"]), t)
    pg.fill("#newClassName", "Saturday class"); pg.click("#newClassOk"); pg.wait_for_timeout(300)
    check("it has to be picked", not made and "Pick who the class is for" in pg.inner_text("#newClassErr"))
    pg.screenshot(path=PAD + "entry_teacher_new.png", full_page=True)
    pg.click("#age-little"); pg.click("#newClassOk"); pg.wait_for_timeout(800)
    check("picked: the class is made for that age group", made == [{"name": "Saturday class", "ages": "little"}], made)
    t = pg.inner_text("#teachMain")
    check("the class shows its link, with the code in it", pg.inner_text("#classLink").strip() == "https://learnalefba.com/#join=ABC234" and "Join your class" in t, t[:400])
    check("and who it's for, to change", pg.is_visible("#classAges"))
    pg.click("#classAges #age-teens"); pg.wait_for_timeout(500)
    check("changing it saves", aged == [{"id": "a" * 24, "ages": "teens"}] and "Saved" in pg.inner_text("#classAges"), aged)
    pg.screenshot(path=PAD + "entry_teacher_class.png", full_page=True)
    check("no page errors", not errs, errs); c.close()
    b.close()
print(f"{sum(res)} of {len(res)} passed")
sys.exit(0 if all(res) else 1)
