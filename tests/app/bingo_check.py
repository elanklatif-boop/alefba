# Bingo for a class: a third game in the Games tab. The cards print two to a page, each one different, with pictures
# (or words in Persian in Read it); the screen says a word, shows it after a few seconds (or straight away on a tap),
# keeps a list of what's been called, and "Bingo!" throws confetti. Both are counted.
import json
from playwright.sync_api import sync_playwright
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
BASE = "http://127.0.0.1:8811/"
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
with sync_playwright() as p:
    b = p.chromium.launch(); c = b.new_context(viewport={"width": 1366, "height": 768}); sent = []
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    def got(r):
        try: sent.extend(json.loads(r.request.post_data or "{}").get("e", []))
        except Exception: pass
        r.fulfill(status=200, body="{}")
    c.route("**/api/usage", got)
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto(BASE + "play.html"); pg.wait_for_timeout(1800)
    check("Bingo is a third game, and the teachers' note mentions it", pg.is_visible("#gk-bingo") and "Bingo" in pg.inner_text("#classPlayNote"))
    pg.click("#gk-bingo"); pg.wait_for_timeout(300)
    check("with Pictures and Read it under it, worded for cards", pg.get_attribute("#bm-pics", "aria-pressed") == "true" and "cards" in pg.inner_text("#bm-read"))
    check("Level 1 is offered (8 words with pictures, enough for a card)", pg.is_visible("#gw-1") and "8 words" in pg.inner_text("#gw-1"), pg.inner_text("#gw-1"))
    pg.click("#gw-3"); pg.wait_for_timeout(800)
    check("it opens the Bingo screen for that level", pg.is_visible("#bingo") and pg.inner_text("#bingoTitle") == "Bingo: Level 3: Food and drink")
    info = pg.evaluate("""(() => { const cards = [...document.querySelectorAll('#bingoPreview .bingo-card')];
      const words = cards.map(cd => [...cd.querySelectorAll('.bc:not(.free) .w')].map(w => w.textContent));
      return { n: cards.length, free: cards.map(cd => cd.querySelectorAll('.bc.free').length), pics: cards.map(cd => cd.querySelectorAll('.bc .pic').length),
               squares: cards.map(cd => cd.querySelectorAll('.bc').length), same: words[0].join() === words[1].join(), uniq: words.map(w => new Set(w).size), cut: !!document.querySelector('#bingoPreview .bingo-cut') }; })()""")
    check("the preview shows two cards on one page, 3 x 3 with a free star, pictures, a cut line between them", info["n"] == 2 and info["squares"] == [9, 9] and info["free"] == [1, 1] and info["pics"] == [8, 8] and info["cut"], info)
    check("no word twice on a card, and the two cards differ", info["uniq"] == [8, 8] and not info["same"], info)
    first = pg.evaluate("bingoCardHtml(0)")
    pg.evaluate("$('bingoCount').value = 5; $('bingoCount').dispatchEvent(new Event('change'))"); pg.wait_for_timeout(100)
    pg.evaluate("window.print = () => {}; 0"); pg.click("#bingoPrint"); pg.wait_for_timeout(200)
    printed = pg.evaluate("[...document.querySelectorAll('#printSheets .sheet-page')].map(p => p.querySelectorAll('.bingo-card').length)")
    check("Print: 5 cards go on 3 pages (2, 2, 1), and the first printed card is the one previewed", printed == [2, 2, 1] and pg.evaluate("$('printSheets').querySelector('.bingo-card').outerHTML") == first, printed)
    pg.click("#bingoShuffle"); pg.wait_for_timeout(200)
    check("Different cards: the first card changes", pg.evaluate("bingoCardHtml(0)") != first)
    pg.evaluate("sendUsage()"); pg.wait_for_timeout(300)
    check("printing is counted", sent.count("bingo_print") == 1, sent)
    # calling the words
    pg.click("#bingoStart"); pg.wait_for_timeout(400)
    check("the calling screen opens, waiting for the first word", pg.is_visible("#bingoStage") and "Say the first word" in pg.inner_text("#bingoNext") and pg.locator("#bingoCalled").count() == 0)
    pg.click("#bingoNext"); pg.wait_for_timeout(500)
    stage = pg.inner_text("#bingoStage")
    check("the first word is said but not shown yet", "?" in stage and "Word 1 of 16" in stage and pg.is_visible("#bingoAgain") and pg.is_visible("#bingoShow"), stage)
    pg.wait_for_timeout(4200)
    shown = pg.evaluate("(() => { const s = document.querySelector('#bingoStage'); return { pic: !!s.querySelector('.bs-pic'), fa: s.querySelector('.bs-fa')?.textContent, tr: s.querySelector('.bs-tr')?.textContent }; })()")
    check(f"after a few seconds it's shown: picture, the word in Persian and its meaning ({shown['tr']})", shown["pic"] and shown["fa"] and " · " in (shown["tr"] or ""), shown)
    check("the called list has it", pg.locator("#bingoCalled span").count() == 1 and shown["fa"] in pg.inner_text("#bingoCalled"))
    pg.click("#bingoNext"); pg.wait_for_timeout(300); pg.click("#bingoShow"); pg.wait_for_timeout(200)
    check("Show it now shows the next word at once, and the list has 2", pg.locator("#bingoStage .bs-fa").count() == 1 and pg.is_hidden("#bingoShow") and pg.locator("#bingoCalled span").count() == 2)
    pg.click("#bingoWin"); pg.wait_for_timeout(100)
    check("Bingo! throws confetti", pg.locator(".confetti").count() == 1)
    for _ in range(14): pg.click("#bingoNext"); pg.wait_for_timeout(120)
    check("once every word is called, the button says so and stops", pg.is_disabled("#bingoNext") and "Every word" in pg.inner_text("#bingoNext") and pg.locator("#bingoCalled span").count() == 16)
    pg.evaluate("sendUsage()"); pg.wait_for_timeout(300)
    check("a game called on a screen is counted once", sent.count("bingo_call") == 1, sent)
    pg.click("#bingoCards"); pg.wait_for_timeout(200)
    check("Back to the cards", pg.is_visible("#bingoPrint"))
    pg.click("#bingoBack"); pg.wait_for_timeout(300)
    check("Back closes it, back on the Games tab", pg.is_hidden("#bingo") and pg.is_visible("#view-games"))
    # Read it: words in Persian on the cards, no pictures
    pg.click("#bm-read"); pg.wait_for_timeout(200); pg.click("#gw-1"); pg.wait_for_timeout(600)
    rd = pg.evaluate("(() => { const cd = document.querySelector('#bingoPreview .bingo-card'); return { pics: cd.querySelectorAll('.pic').length, words: cd.querySelectorAll('.bc .w').length, rule: cd.querySelector('.bingo-rule').textContent }; })()")
    check("Read it: cards with 8 words in Persian and no pictures", rd["pics"] == 0 and rd["words"] == 8 and "word" in rd["rule"], rd)
    pg.click("#bingoBack"); pg.wait_for_timeout(200)
    check("no page errors", not errs, errs)
    c.close()
    # on a phone the game is still there (families can play it too), and nothing else changed
    c = b.new_context(viewport={"width": 390, "height": 844}); c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE))); c.route("**/api/usage", lambda r: r.fulfill(status=200, body="{}"))
    pg = c.new_page(); pg.goto(BASE + "play.html"); pg.wait_for_timeout(1800)
    pg.click("#gk-bingo"); pg.wait_for_timeout(200); pg.click("#gw-1"); pg.wait_for_timeout(600)
    fits = pg.evaluate("(() => { const cd = document.querySelector('#bingoPreview .bingo-card').getBoundingClientRect(); return cd.right <= innerWidth && cd.width > 120; })()")
    check("on a phone the card preview fits the screen", fits)
    c.close(); b.close()
print(f"bingo_check: {sum(res)} of {len(res)} passed")
