# Bingo cards printed earlier must match the game played later (a teacher printed Read it cards for Level 5, then the
# screen called the words in Pictures, which left out هوا and آسمان, so two squares could never be marked). The cards a
# device printed are remembered for that level, every card carries a game code, and the code brings the same cards back.
import json
from playwright.sync_api import sync_playwright
FREE = {"talks": True, "plans": True, "signedIn": True, "email": "t@example.com", "canTalk": True, "kind": "basic", "plan": "basic", "basicTalks": 20, "left": 9, "free": 3}  # Level 5 needs a plan
BASE = "http://127.0.0.1:8811/"
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
CARDS = "[...Array(6)].map((_, k) => bingoCardWords(k).map(W => W.tr).join(','))"
with sync_playwright() as p:
    b = p.chromium.launch(); c = b.new_context(viewport={"width": 1366, "height": 768})
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    c.route("**/api/usage", lambda r: r.fulfill(status=200, body="{}"))
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.print = () => {}")
    pg.goto(BASE + "#play"); pg.wait_for_timeout(1800)
    pg.click("#gk-bingo"); pg.wait_for_timeout(200)
    pg.click("#bm-read"); pg.wait_for_timeout(200)
    lvl5 = pg.evaluate("[...document.querySelectorAll('[id^=gw-]')].find(b => /Weather/.test(b.textContent))?.id")
    pg.click("#" + lvl5); pg.wait_for_timeout(700)
    words = pg.evaluate("BINGO.pool.map(W => W.tr)")
    check("Level 5 in Read it has havâ and âsemân", "havâ" in words and "âsemân" in words, words)
    code = pg.evaluate("bingoCode(BINGO.read, BINGO.seed)"); cards = pg.evaluate(CARDS)
    check("the game code is R and 4 letters or digits", len(code) == 5 and code[0] == "R", code)
    pg.click("#bingoPrint"); pg.wait_for_timeout(300)
    check("printing remembers the cards for this level", pg.evaluate("S.prefs.bingoPrinted[BINGO.name].code") == code)
    check("and the screen says these are the printed cards", pg.is_visible("#bingoFromPrint") and code in pg.inner_text("#bingoFromPrint"))
    # the teacher closes it, switches to Pictures, and opens the same level again
    pg.click("#bingoBack"); pg.wait_for_timeout(300)
    pg.click("#bm-pics"); pg.wait_for_timeout(200)
    pg.click("#" + lvl5); pg.wait_for_timeout(700)
    check("opened again in Pictures: still the printed Read it game, same code, same cards", pg.evaluate("BINGO.read") is True and pg.evaluate("bingoCode(BINGO.read, BINGO.seed)") == code and pg.evaluate(CARDS) == cards)
    pg.click("#bingoStart"); pg.wait_for_timeout(300)
    called = set(pg.evaluate("BINGO.order.map(W => W.tr)"))
    on_cards = set(",".join(cards).split(","))
    check("every word on the printed cards gets called, havâ and âsemân too", on_cards <= called and "havâ" in called and "âsemân" in called, on_cards - called)
    # another device: no memory, but the code brings the same cards back
    c2 = b.new_context(viewport={"width": 1366, "height": 768})
    c2.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    c2.route("**/api/usage", lambda r: r.fulfill(status=200, body="{}"))
    p2 = c2.new_page(); p2.on("pageerror", lambda x: errs.append(str(x)))
    p2.goto(BASE + "#play"); p2.wait_for_timeout(1800)
    p2.click("#gk-bingo"); p2.wait_for_timeout(200); p2.click("#" + lvl5); p2.wait_for_timeout(700)
    check("another device starts with its own new cards", not p2.is_visible("#bingoFromPrint") and p2.evaluate("bingoCode(BINGO.read, BINGO.seed)") != code)
    p2.click("#bingoCodeBox summary"); p2.fill("#bingoCodeInput", "zzz"); p2.click("#bingoCodeGo"); p2.wait_for_timeout(200)
    check("a wrong code says so", p2.is_visible("#bingoCodeErr"))
    p2.click("#bingoCodeBox summary") if not p2.is_visible("#bingoCodeInput") else None
    p2.fill("#bingoCodeInput", code.lower()); p2.click("#bingoCodeGo"); p2.wait_for_timeout(300)
    check("the game code brings back exactly the printed cards", p2.evaluate("BINGO.read") is True and p2.evaluate(CARDS) == cards)
    # Make new cards forgets the printed ones
    pg.click("#bingoBack") if pg.is_visible("#bingoBack") else None; pg.wait_for_timeout(200)
    pg.click("#bingoBack") if pg.is_visible("#bingoBack") else None; pg.wait_for_timeout(200)
    pg.click("#" + lvl5); pg.wait_for_timeout(600)
    pg.click("#bingoForget"); pg.wait_for_timeout(300)
    check("Make new cards: the printed game is forgotten, and the way chosen now (Pictures) is used", not pg.is_visible("#bingoFromPrint") and pg.evaluate("BINGO.read") is False and not pg.evaluate("(S.prefs.bingoPrinted || {})[BINGO.name]"))
    check("no page errors", not errs, errs)
    b.close()
print(f"bingo_print_check: {sum(res)} of {len(res)} passed")
