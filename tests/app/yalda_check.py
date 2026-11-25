# learnalefba.com/yalda: tap the book for a Hafez fâl (20, none repeated until all are seen), take another, show it big
# for a class, the picture to send, the five Yalda words, and the links into Yalda bingo, balloons and the story.
import json
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:8811/"
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []; sent = []
    c = b.new_context(viewport={"width": 390, "height": 844})
    def got(r):
        try: sent.extend(json.loads(r.request.post_data or "{}").get("e", []))
        except Exception: pass
        r.fulfill(status=200, body="{}")
    c.route("**/api/usage", got)
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body='{"talks":true,"plans":true,"signedIn":false}'))
    pg = c.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "yalda.html"); pg.wait_for_timeout(800)
    check("the page opens on the book, with the wish and what families say", pg.is_visible("#book") and "ای حافظ" in pg.inner_text("#say") and not pg.is_visible("#fal"))
    check("20 couplets are in the page", pg.evaluate("JSON.parse(document.getElementById('falData').textContent.replace('/*FAL_DATA*/','')).length") == 20)
    seen = []
    for i in range(20):
        pg.click("#book"); pg.wait_for_timeout(650)
        seen.append(pg.inner_text("#verse"))
        if i == 0:
            check("a fâl: two lines of Persian, how to say them, the meaning and a line for the wish", pg.is_visible("#fal") and pg.locator("#verse span").count() == 2 and pg.locator("#finglish span").count() == 2 and "What it says" in pg.inner_text("#meaning") and "For your wish" in pg.inner_text("#forwish"))
            check("the book is hidden while the fâl shows", not pg.is_visible("#book"))
        pg.click("#againBtn"); pg.wait_for_timeout(100)
    check("Take another goes back to the book, for the next wish", pg.is_visible("#book") and not pg.is_visible("#fal"))
    check("all 20 come up once before any repeats", len(set(seen)) == 20, len(set(seen)))
    check("no Hear it for the fâl until its recording exists", (pg.click("#book"), pg.wait_for_timeout(650), not pg.is_visible("#hearFal"))[2])
    with pg.expect_download() as dl: pg.click("#saveBtn")
    check("Save the picture gives a picture", dl.value.suggested_filename == "my-yalda-fal.png")
    words = pg.evaluate("[...document.querySelectorAll('#words .word')].map(w => w.innerText.replace(/\\s+/g,' '))")
    check("five Yalda words, watermelon with books vs everyday", len(words) == 5 and "hendevâne" in words[0] and "hendune" in words[0] and "people say" in words[0].lower())
    check("the family's recordings are marked real voice", pg.locator("#words .rv").count() == 6)
    pg.click("#bigBtn"); pg.wait_for_timeout(300)
    check("show it big: only the fâl, and a way out", pg.evaluate("document.body.classList.contains('big')") and not pg.is_visible("main") and pg.is_visible("#exitBig") and pg.is_visible("#fal"))
    pg.click("#exitBig"); pg.wait_for_timeout(200)
    check("exit big screen", not pg.evaluate("document.body.classList.contains('big')") and pg.is_visible("main"))
    check("links into the app for bingo, balloons and the story", [pg.get_attribute(i, "href") for i in ("#linkBingo", "#linkBalloons", "#linkStory")] == ["./#yalda-bingo", "./#yalda-balloons", "./#yalda-story"])
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(300)
    check("counted: opened, fâls taken, picture saved, shown big", all(e in sent for e in ("yalda_open", "yalda_fal", "yalda_share", "yalda_big")), set(sent))
    pg.click("#linkBingo"); pg.wait_for_timeout(1800)
    check("Yalda bingo opens in the app, set for a classroom screen", pg.is_visible("#bingo") and "Shab-e Yalda" in pg.inner_text("#bingoTitle") and pg.evaluate("document.body.classList.contains('class-play')"))
    check("no page errors", not errs, errs)
    b.close()
print(f"yalda_check: {sum(res)} of {len(res)} passed")
