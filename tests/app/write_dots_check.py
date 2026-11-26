# Writing a letter from memory: dots drawn the way people really draw them count as right. Three dots for se in a
# row (not a little triangle), spread over the letter, is still se. But the number of dots and their side still
# matter: se with two dots (that's te), or with the dots underneath, is not accepted.
import json, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8811/"
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
ST = {"done": {}, "items": {}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 1, "read": 1,
      "profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
OK = []
def check(name, cond, info=""):
    OK.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{info}]"))
def stroke(pg, pts):
    pg.mouse.move(*pts[0]); pg.mouse.down()
    for x, y in pts[1:]: pg.mouse.move(x, y, steps=2)
    pg.mouse.up()
def dot(pg, x, y, r=5):
    pg.mouse.move(x - r, y); pg.mouse.down(); pg.mouse.move(x + r, y, steps=3); pg.mouse.move(x, y + r, steps=2); pg.mouse.up()
with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    c.add_init_script("localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(ST)) + ")")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x))); pg.goto(URL); pg.wait_for_timeout(1200)
    def attempt(letter, dots_at):
        """write the letter's main stroke from memory (its own shape), then dots_at(box) gives where to tap the dots"""
        pg.evaluate(f"""(() => {{ const L = LETTERS.find(L => L[1] === {json.dumps(letter)}); const ex = exTrace(L, true);
           R = {{ queue: [ex, exTrace(L, false)], pos: 0, mistakes: 0, graded: 0, requeued: 0, phase: 'answer', built: [], missed: [], finish: false }}; openOverlay('lesson'); showExercise(); }})()""")
        pg.wait_for_timeout(250)
        main = pg.evaluate("R.trace.pieces()[0]")
        xs = [q[0] for q in main]; ys = [q[1] for q in main]; box = (min(xs), min(ys), max(xs), max(ys))
        # the stroke, as a line through the middle of each column of the letter's main piece
        cols = {}
        for x, y in main: cols.setdefault(round(x / 6), []).append(y)
        line = [(k * 6, sum(v) / len(v)) for k, v in sorted(cols.items())]
        stroke(pg, line)
        for x, y in dots_at(box): dot(pg, x, y)
        pg.click("#mainBtn"); pg.wait_for_timeout(300)
        return pg.inner_text("#feedback")
    def row3(b, dy=-28):  # three dots in a row, spread over the letter (how many people draw them)
        x0, y0, x1, y1 = b; w = x1 - x0
        return [(x0 + w * 0.22, y0 + dy + 4), (x0 + w * 0.5, y0 + dy - 4), (x0 + w * 0.78, y0 + dy + 4)]
    fb = attempt("se", row3)
    check("se from memory with its 3 dots in a row above: accepted", "Check the dots" not in fb and "Not quite" not in fb, fb)
    fb = attempt("se", lambda b: row3(b)[:2])
    check("se with only 2 dots (that's te): not accepted", "Check the dots" in fb, fb)
    fb = attempt("se", lambda b: [(x, b[3] + 30) for x, _ in row3(b)])
    check("se with its 3 dots underneath (that's pe's place): not accepted", "Check the dots" in fb, fb)
    fb = attempt("te", lambda b: row3(b)[::2])
    check("te with its 2 dots spread apart above: accepted", "Check the dots" not in fb and "Not quite" not in fb, fb)
    fb = attempt("be", lambda b: [((b[0] + b[2]) / 2 + 10, b[3] + 26)])
    check("be with its dot underneath: accepted", "Check the dots" not in fb and "Not quite" not in fb, fb)
    fb = attempt("be", lambda b: [((b[0] + b[2]) / 2, b[1] - 26)])
    check("be with its dot on top (that's nun's place): not accepted", "Check the dots" in fb, fb)
    check("no page errors", not errs, errs)
    b.close()
print(f"{sum(OK)}/{len(OK)}")
sys.exit(0 if all(OK) else 1)
