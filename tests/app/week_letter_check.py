# The letter of the week, for a class for ages 3 to 6. The teacher sees letters to pick instead of lessons to assign,
# picks one (and can clear it), prints a tracing sheet for it, and sees which children have traced it. A child in the
# class finds it first on the little menu, with a star, and tracing it reaches the teacher. Older classes are unchanged.
import json, time
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8811/"
PAD = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/"
TEACHER = {"talks": True, "plans": True, "signedIn": True, "plan": None, "kind": "free", "canTalk": True, "left": 3, "free": 3, "email": "t@example.com", "classTalks": 5,
           "prices": {"basic": "$5", "unlimited": "$6.49", "yearly": "$39", "school": "$49", "schoolTalks": "$59.99"}}
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
now = time.time() * 1000; today = time.strftime("%Y-%m-%d")
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
GROWN = {"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 0, "read": 0,
         "profile": {"name": "Ms Sara", "goal": 2, "adult": True, "whoSet": True}}
def members():
    return [{"id": "m1", "name": "Dara", "seen": now, "progress": {"done": ["letter-alef", "letter-be"], "days": [today], "streak": 1, "best": 1, "letters": 0, "words": 0, "today": today}},
            {"id": "m2", "name": "Nika", "seen": now, "progress": {"done": ["letter-alef"], "days": [today], "streak": 1, "best": 1, "letters": 0, "words": 0, "today": today}},
            {"id": "m3", "name": "Arya", "seen": 0, "progress": None}]
def teacher_page(b, ages):
    c = b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    c.add_init_script("if (!sessionStorage.getItem('s')) { sessionStorage.setItem('s', 1); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(GROWN)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(TEACHER)))
    c.route("**/api/usage", lambda r: r.fulfill(status=200, body="{}"))
    cls = {"id": "a" * 24, "name": "K2 Saturday", "code": "ABC234", "ages": ages, "assigned": [], "paidUntil": 0, "talksUntil": 0, "pending": False, "members": members()}
    saved = []
    def assign(r):
        body = json.loads(r.request.post_data); saved.append(body["lessons"]); cls["assigned"] = body["lessons"]
        r.fulfill(status=200, content_type="application/json", body=json.dumps({"class": cls}))
    c.route("**/api/class/view", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"class": cls})))
    c.route("**/api/class/assign", assign)
    c.route("**/api/class/list", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"classes": [cls]})))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto(URL); pg.wait_for_timeout(1300)
    pg.evaluate("$('onboard').inert = true; openOverlay('teach'); teachClass('" + "a" * 24 + "'); 0"); pg.wait_for_timeout(800)
    return c, pg, errs, saved
with sync_playwright() as p:
    b = p.chromium.launch()
    # ---- the teacher of a class for ages 3 to 6 ----
    c, pg, errs, saved = teacher_page(b, "little")
    check("letters to pick instead of lessons to assign", pg.is_visible("#weekLetterSec") and pg.locator("#assignBtn").count() == 0 and pg.locator(".week-letter").count() == 32)
    check("it says what little learners do and what the letter is for", "no lessons to assign" in pg.inner_text("#weekLetterSec") and "No letter picked yet" in pg.inner_text("#weekLetterMsg"))
    pg.click("#wl-letter-be"); pg.wait_for_timeout(900)
    check("tapping ب makes it the letter of the week", saved == [["letter-be"]] and pg.get_attribute("#wl-letter-be", "aria-pressed") == "true" and "ب" in pg.inner_text("#weekLetterMsg"), saved)
    check("and the page stays on the letters (it doesn't jump back to the top)", pg.evaluate("(() => { const r = document.querySelector('#weekLetterMsg').getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; })()"))
    cards = {n: pg.inner_text(f"#mem-{i}") for n, i in (("Dara", "m1"), ("Nika", "m2"), ("Arya", "m3"))}
    check("Dara traced it: ✓, with 2 letters traced", "traced ✓" in cards["Dara"] and "2 letters traced" in cards["Dara"], cards["Dara"])
    check("Nika hasn't yet", "not traced yet" in cards["Nika"] and "1 letter traced" in cards["Nika"], cards["Nika"])
    check("Arya hasn't practised since joining", "Hasn't practised since joining" in cards["Arya"] and "not traced yet" in cards["Arya"], cards["Arya"])
    check("the sheets button offers a tracing sheet for ب", pg.inner_text("#weekSheets") == "Print a tracing sheet for ب")
    pg.screenshot(path=PAD + "week_letter_teacher.png", full_page=True)
    pg.click("#weekSheets"); pg.wait_for_timeout(500)
    check("which opens the tracing sheets with just ب picked", pg.is_visible("#sheets") and pg.evaluate("[...SHEETS.picked].join('')") == "ب")
    pg.evaluate("closeOverlay('sheets')"); pg.wait_for_timeout(200)
    pg.click("#wl-letter-be"); pg.wait_for_timeout(900)
    check("tapping it again clears it", saved[-1] == [] and pg.get_attribute("#wl-letter-be", "aria-pressed") == "false" and "Letter of the week" not in pg.inner_text("#mem-m1"), saved)
    check("no page errors (teacher)", not errs, errs); c.close()

    # ---- an older class is unchanged ----
    c, pg, errs, saved = teacher_page(b, "kids")
    check("a class for 7 to 12 still assigns lessons", pg.is_visible("#assignBtn") and pg.locator("#weekLetterSec").count() == 0)
    check("and traced letters don't count as lessons done", "0 lessons done" in pg.inner_text("#mem-m1"), pg.inner_text("#mem-m1"))
    check("no page errors (older class)", not errs, errs); c.close()

    # ---- a child in the class ----
    kid = {**GROWN, "profile": {"name": "Dara", "goal": 1, "adult": False, "little": True, "whoSet": True, "at": today},
           "cls": {"token": "T" * 43, "name": "Dara", "cname": "K2 Saturday", "ages": "little", "assigned": ["letter-be"], "fullUntil": 0, "talks": None}}
    c = b.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
    c.add_init_script("if (!sessionStorage.getItem('s')) { sessionStorage.setItem('s', 1); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(kid)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    c.route("**/api/usage", lambda r: r.fulfill(status=200, body="{}"))
    sent = []
    def prog(r):
        sent.append(json.loads(r.request.post_data)["progress"])
        r.fulfill(status=200, content_type="application/json", body=json.dumps({"name": "Dara", "class": {"name": "K2 Saturday", "ages": "little", "assigned": ["letter-be"], "fullUntil": 0, "talks": None}}))
    c.route("**/api/class/progress", prog)
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto(URL); pg.wait_for_timeout(1500)
    check("little mode opens with the teacher's letter first, with a star", pg.is_visible("#littleWeek") and "ب" in pg.inner_text("#littleWeek") and "From your teacher" in pg.inner_text("#littleWeek"))
    check("the menu below it is unchanged", [t.split("\n")[0] for t in pg.locator(".little-act .lw-en").all_inner_texts()] == ["Flashcards", "Games", "Letters"])
    pg.screenshot(path=PAD + "week_letter_child.png")
    pg.click("#littleWeek"); pg.wait_for_timeout(500)
    check("tapping it opens ب to trace", pg.is_visible("#littleCanvas") and pg.inner_text("#littleBig").strip() == "ب")
    pg.evaluate("littleMark('ب'); syncClass(true)"); pg.wait_for_timeout(1200)
    check("once traced, it reaches the teacher", sent and "letter-be" in sent[-1]["done"], sent[-1:] )
    pg.evaluate("littleLetters()"); pg.wait_for_timeout(300)
    check("in the letters, ب is marked as the teacher's letter", "week" in pg.get_attribute("#lt-be", "class"))
    pg.evaluate("littleHome()"); pg.wait_for_timeout(300)
    check("and the menu shows it as traced", "Traced" in pg.inner_text("#littleWeek") and "⭐" in pg.inner_text("#littleWeek"))
    check("no page errors (child)", not errs, errs); c.close()
    b.close()
print(f"week_letter_check: {sum(res)} of {len(res)} passed")
