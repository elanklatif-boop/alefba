# The four guide pages (What is taarof?, Thank you in Persian, The Persian alphabet, Teaching your child Persian):
# they fit a phone, every recording and link is there, what search engines are told matches what people see,
# the play buttons work, and visits are counted without being mistaken for the taarof short link.
import json, re, sys, os, html
from playwright.sync_api import sync_playwright
SHOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/"
SITE = os.environ.get("SITE", "/home/claude/alefba-site")
BASE = "http://127.0.0.1:8811/"
PAGES = ["what-is-taarof", "thank-you-in-persian", "persian-alphabet", "teach-your-child-persian"]
REAL = set(json.load(open(os.path.join(SITE, "audio", "real_voice.json"))))
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3, "prices": {"basic": "$5", "unlimited": "$6.49", "yearly": "$39"}}
res = []
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
norm = lambda t: re.sub(r"\s+", " ", t).strip()

sitemap = open(os.path.join(SITE, "sitemap.xml")).read()
home = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
with sync_playwright() as p:
    b = p.chromium.launch()
    sent = []
    for scheme in ("light", "dark"):
        c = b.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=1, color_scheme=scheme)
        c.route("**/api/usage*", lambda r: (sent.append(r.request.post_data or ""), r.fulfill(status=204, body=""))[1])
        for slug in PAGES if scheme == "light" else PAGES[2:3]:
            pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
            pg.goto(BASE + slug + ".html"); pg.wait_for_timeout(600)
            pg.screenshot(path=f"{SHOT}guide_{slug}_{scheme}.png", full_page=True)
            if scheme == "dark": check(f"{slug}: readable in dark mode (no page errors)", not errs, errs); pg.close(); continue
            check(f"{slug}: fits a 360px phone (no sideways scroll)", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), pg.evaluate("document.documentElement.scrollWidth"))
            check(f"{slug}: canonical link and sitemap entry", pg.get_attribute("link[rel=canonical]", "href") == "https://learnalefba.com/" + slug and f"https://learnalefba.com/{slug}<" in sitemap)
            check(f"{slug}: linked from the home page", f'href="{slug}"' in home)
            # what search engines are told matches the page, word for word
            ld = json.loads(pg.inner_text("script[type='application/ld+json']") if False else pg.evaluate("document.querySelector('script[type=\"application/ld+json\"]').textContent"))
            seen = pg.evaluate("[...document.querySelectorAll('main section')].map(s => [s.querySelector('h2').innerText, (s.querySelector('h2 + p') || {innerText: ''}).innerText])")
            want = [(q, norm(a)) for q, a in seen if q.endswith("?")]
            got = [(m["name"], norm(m["acceptedAnswer"]["text"])) for m in ld["mainEntity"]]
            check(f"{slug}: {len(got)} questions told to search engines, each matching the page", got == want and len(got) >= 4, [g for g, w in zip(got, want) if g != w][:2])
            check(f"{slug}: the short answer comes first", pg.evaluate("document.querySelector('main .wrap').firstElementChild.className") == "short")
            # every play button is a real recording that's in the site
            files = pg.evaluate("[...document.querySelectorAll('[data-a]')].map(b => b.dataset.a)")
            bad = [f for f in files if not f.startswith("audio/") or f[6:] not in REAL or not os.path.exists(os.path.join(SITE, f))]
            check(f"{slug}: {len(files)} play buttons, all real recordings", files and not bad, bad)
            # links: within the site they go to a page that exists; the app's links are counted
            links = pg.evaluate("[...document.querySelectorAll('a[href]')].map(a => [a.getAttribute('href'), a.hasAttribute('data-go')])")
            missing = [h for h, _ in links if not h.startswith("http") and not os.path.exists(os.path.join(SITE, (h.split("#")[0].lstrip("./") or "index") + ("" if h.split("#")[0].endswith(".html") else ".html")))]
            check(f"{slug}: all {len(links)} links go somewhere real", not missing, missing)
            toapp = [h for h, go in links if h.startswith("./")]
            check(f"{slug}: every link into the app is counted", toapp and all(go for h, go in links if h.startswith("./")), [h for h, go in links if h.startswith("./") and not go])
            # a play button lights up while it plays, and a second tap stops it
            pg.evaluate("HTMLMediaElement.prototype.play = function () { window.__played = this.src; return Promise.resolve(); }")
            first = pg.locator("[data-a]").first; first.click(); pg.wait_for_timeout(100)
            check(f"{slug}: tapping ▶ plays its recording", (pg.evaluate("window.__played") or "").endswith(files[0]) and "on" in first.get_attribute("class"))
            first.click(); pg.wait_for_timeout(100)
            check(f"{slug}: a second tap stops it", "on" not in first.get_attribute("class"))
            check(f"{slug}: no page errors", not errs, errs); pg.close()
        c.close()
    check("each guide page counts its visit (guide_open)", sum(s.count("guide_open") for s in sent) == 5, sent)

    # from the taarof guide into the taarof test: counted as a guide visit, not as the short link from a reel
    c = b.new_context(viewport={"width": 390, "height": 844})
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    sent = []; c.route("**/api/usage*", lambda r: (sent.append(r.request.post_data or ""), r.fulfill(status=204, body=""))[1])
    pg = c.new_page(); errs = []; pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto(BASE + "what-is-taarof.html"); pg.wait_for_timeout(500)
    pg.click("a.cta[href='./#taarof']"); pg.wait_for_timeout(1800)
    check("Take the taarof test opens the test", pg.is_visible("#exBox") and "taarof" in pg.inner_text("#exBox").lower(), pg.inner_text("body")[:200])
    pg.wait_for_timeout(4500)
    check("the tap is counted as guide_start, not as taarof_link", any("guide_start" in s for s in sent) and not any("taarof_link" in s for s in sent), sent)
    check("no page errors (guide to the test)", not errs, errs); c.close()

    # the short link itself is still counted as before
    c = b.new_context(viewport={"width": 390, "height": 844})
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    sent = []; c.route("**/api/usage*", lambda r: (sent.append(r.request.post_data or ""), r.fulfill(status=204, body=""))[1])
    pg = c.new_page(); pg.goto(BASE + "taarof.html"); pg.wait_for_timeout(6000)
    check("learnalefba.com/taarof is still counted as taarof_link", any("taarof_link" in s for s in sent), sent); c.close()
    b.close()

lp = open(os.path.join(SITE, "learn-persian.html"), encoding="utf-8").read()
check("the kids page no longer says every word is in a real voice", "every word in a real voice" not in lp and lp.count("many by a real Persian speaker") == 2)
check("the kids page links to all four guides", all(f'href="{s}"' in lp for s in PAGES))
print(f"guides_check: {sum(res)} of {len(res)} passed")
