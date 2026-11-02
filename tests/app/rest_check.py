from playwright.sync_api import sync_playwright
import json
res = []
def check(n, ok, x=""): res.append(ok); print("PASS" if ok else "FAIL", n, "" if ok else x)
SEED = """(() => { const D = n => { const d = new Date(); d.setDate(d.getDate() - n); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
  const c = %s; const days = c.days.map(D);
  localStorage.setItem('alefba-v3', JSON.stringify({ done: { "a1-1": true }, items: {}, days, rest: c.rest, talks: {}, prefs: { lang: "en", fing: "auto" }, log: {}, speak: 1, read: 1,
    profile: { name: "Sara", goal: 2, adult: false, speakSelf: 1, readSelf: 1, reasons: [] } })); })()"""
def page(b, days, rest=0, dark=False):
    c = b.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark" if dark else "light")
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); " + SEED % json.dumps({"days": days, "rest": rest}) + " }")
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.goto("http://127.0.0.1:8811/"); pg.wait_for_timeout(900)
    return c, pg, errs
info = lambda pg: pg.evaluate("({ sd: streakDays(), rest: S.rest, restDays: S.restDays.length, nudge: $('streakNudge').hidden ? '' : $('streakNudge').textContent, chip: $('streak').textContent })")
with sync_playwright() as p:
    b = p.chromium.launch()
    c, pg, errs = page(b, [])
    i = info(pg); check(f"no practice yet: no nudge ({i})", i["nudge"] == "" and "Start a streak" in i["chip"]); c.close()
    c, pg, errs = page(b, [1, 2, 3, 4, 5])
    i = info(pg); check(f"a 5-day streak, nothing yet today: the gentle nudge shows ({i['nudge']!r})", i["nudge"] == "One quick lesson keeps your 5-day streak going." and "not yet today" in i["chip"])
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec29/nudge.png", clip={"x": 0, "y": 0, "width": 390, "height": 420})
    pg.evaluate("practised(); renderAll()"); i = info(pg)
    check(f"after a lesson the nudge is gone and the streak is 6 ({i})", i["nudge"] == "" and i["sd"] == 6 and i["rest"] == 0); c.close()
    c, pg, errs = page(b, [1, 2, 3, 4, 5, 6])
    pg.evaluate("practised(); renderAll()"); i = info(pg)
    check(f"day 7 in a row earns a rest day ({i})", i["sd"] == 7 and i["rest"] == 1 and pg.evaluate("S.restEarned === todayStr()"))
    check("the streak chip says a rest day is saved (in its tooltip)", "1 rest day saved" in pg.get_attribute("#streak", "title")); c.close()
    c, pg, errs = page(b, [1, 2, 3, 4, 5, 6])
    pg.evaluate("startLesson({ id: 'x', title: 'x' }, [exWordMeaning(WORDS.find(W => W.tr === 'mersi'), WORDS)])"); pg.wait_for_timeout(300)
    pg.evaluate("finishLesson()"); pg.wait_for_timeout(400)
    t = pg.inner_text("#restEarned") if pg.locator("#restEarned").count() else ""
    check(f"the finish screen says a rest day was earned ({t!r})", "You earned a rest day!" in t and "1 saved" in t)
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec29/rest_earned.png"); c.close()
    c, pg, errs = page(b, list(range(2, 12)), rest=1)
    i = info(pg); check(f"missed yesterday with a rest day saved: the streak survives ({i})", i["sd"] == 10 and i["rest"] == 0 and i["restDays"] == 1)
    check(f"and it says so kindly ({i['nudge']!r})", i["nudge"] == "You missed a day, so a rest day kept your streak safe. One quick lesson keeps your 10-day streak going.")
    check("the missed day shows as a ring in the week dots", pg.evaluate("document.querySelectorAll('#weekDots i.rest').length") == 1)
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec29/rest_used.png", clip={"x": 0, "y": 0, "width": 390, "height": 420})
    pg.reload(); pg.wait_for_timeout(700); i = info(pg)
    check(f"reloading doesn't use another rest day ({i})", i["sd"] == 10 and i["rest"] == 0 and i["restDays"] == 1)
    pg.evaluate("practised(); renderAll()"); i = info(pg)
    check(f"after today's lesson: 11 days and a welcome back ({i['nudge']!r})", i["sd"] == 11 and i["nudge"] == "You missed a day, so a rest day kept your streak safe. Nice to see you back!"); c.close()
    c, pg, errs = page(b, list(range(3, 9)), rest=1)
    i = info(pg); check(f"missed two days with one rest day: the streak starts again, the rest day is kept ({i})", i["sd"] == 0 and i["rest"] == 1 and i["restDays"] == 0); c.close()
    c, pg, errs = page(b, list(range(3, 9)), rest=2)
    i = info(pg); check(f"missed two days with two rest days: both are used ({i['nudge']!r})", i["sd"] == 6 and i["rest"] == 0 and "You missed 2 days, so 2 rest days kept your streak safe." in i["nudge"]); c.close()
    c, pg, errs = page(b, list(range(1, 14)), rest=2)
    pg.evaluate("practised(); renderAll()"); i = info(pg)
    check(f"no more than 2 rest days are saved ({i})", i["sd"] == 14 and i["rest"] == 2)
    check("class progress still sends only real practice days", pg.evaluate("classSummary().days.length") == 14 and pg.evaluate("classSummary().streak") == 14)
    check("no page errors", not errs, errs); c.close()
    c, pg, errs = page(b, [1, 2, 3], dark=True)
    pg.screenshot(path="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec29/nudge_dark.png", clip={"x": 0, "y": 0, "width": 390, "height": 420})
    check("dark mode: no page errors", not errs, errs); c.close()
    b.close()
print(f"{sum(res)}/{len(res)} passed")
