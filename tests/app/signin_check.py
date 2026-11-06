# Signing in on a second device: the welcome screen offers it even after trying a lesson here first, and signing in
# then brings the learner from the other device into this one, instead of adding a second learner.
import json
from playwright.sync_api import sync_playwright
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
URL = "http://127.0.0.1:8811/"
OUT = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
REMOTE = {"profile": {"name": "Elan", "goal": 5, "adult": True, "speakSelf": 1, "readSelf": 1, "reasons": []},
          "done": {"a1-1": True, "a1-2": True, "a1-3": True}, "items": {}, "days": ["2026-11-01"], "updated": 1}
def page(b, state=None, me=OUT):
    c = b.new_context(viewport={"width": 390, "height": 844})
    if state: c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(state)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(me)))
    c.route("**/api/usage", lambda r: r.fulfill(status=200, body="{}"))
    c.route("**/api/sync", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "learners": [{"sid": "S1", "state": REMOTE}], "gone": []})))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto(URL); pg.wait_for_timeout(1300); return c, pg, errs
with sync_playwright() as p:
    b = p.chromium.launch()
    c, pg, errs = page(b)
    check("a first visit: the welcome offers signing in", pg.is_visible("#obSignIn"))
    box = pg.locator("#obSignIn").bounding_box()
    check(f"at the top, without scrolling ({box})", box and box["y"] < 80)
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/signin_first.png")
    pg.click("text=Start learning: 2 minutes"); pg.wait_for_timeout(300); pg.click("#obfirst-no"); pg.wait_for_timeout(500)
    pg.evaluate("finishLesson()"); pg.wait_for_timeout(300); pg.evaluate("closeLesson()"); pg.wait_for_timeout(300)
    pg.evaluate("openOnboarding()"); pg.wait_for_timeout(300)
    check("after trying a lesson here: the welcome still offers it", pg.is_visible("#obSignIn"), pg.inner_text("#onboard")[:300])
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/signin_welcome.png")
    # signing in, with progress on every device on: the learner from the other device fills this one
    pg.evaluate("""ACCT = {...ACCT, signedIn: true, sync: true, fam: 'F1', email: 'x@example.com'}; closeOnboarding();""")
    pg.evaluate("syncNow()"); pg.wait_for_timeout(800)
    fam = pg.evaluate("FAM.learners.length"); prof = pg.evaluate("S.profile"); done = pg.evaluate("Object.keys(S.done).filter(k => S.done[k] === true)")
    check(f"one learner, not two ({fam})", fam == 1)
    check(f"with the other device's name and settings ({prof})", prof and prof.get("name") == "Elan" and prof.get("adult") is True)
    check(f"and the lessons from both devices ({sorted(done)})", {"a1-1", "a1-2", "a1-3"} <= set(done))
    check("no page errors", not errs, errs)
    c.close()
    # already signed in on this device: no sign-in button
    c, pg, errs = page(b, None, {**OUT, "signedIn": True, "email": "x@example.com"})
    check("signed in already: the welcome doesn't offer it", pg.is_visible("#onboard") and not pg.is_visible("#obSignIn"))
    c.close()
    # a device with a real learner set up here: someone from the other device comes as a second learner, nothing is overwritten
    mine = {"profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}, "done": {"a1-1": True}, "items": {}, "days": [], "prefs": {"lang": "en"}, "updated": 5}
    c, pg, errs = page(b, mine)
    pg.evaluate("ACCT = {...ACCT, signedIn: true, sync: true, fam: 'F1'}"); pg.evaluate("syncNow()"); pg.wait_for_timeout(800)
    names = pg.evaluate("FAM.learners.map(l => (readLearner(l.id) || {}).profile).map(x => x && x.name)")
    check(f"a learner set up here stays, the other comes alongside ({names})", names == ["Sara", "Elan"])
    check("no page errors", not errs, errs)
    c.close(); b.close()
print(f"{sum(res)} of {len(res)} passed")
