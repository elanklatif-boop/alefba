# What search engines see: every public page, opened with JavaScript switched off, has its title, one main heading,
# real text to read, a canonical link to itself, and no noindex. The sitemap lists them all, and robots.txt points to it.
import sys, re
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:8811/"
PAGES = ["", "yalda", "learn-persian", "learn-persian-adults", "spoken-vs-written-persian", "spoken-persian-verbs", "i-miss-you-in-persian", "what-is-taarof",
         "thank-you-in-persian", "persian-alphabet", "teach-your-child-persian", "taarof", "rally", "play", "teachers", "parents", "adults", "name", "about", "class-note"]
OK = []
def check(name, cond, info=""):
    OK.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{info}]"))
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(java_script_enabled=False); pg = ctx.new_page()
    sitemap = pg.goto(BASE + "sitemap.xml").text(); robots = pg.goto(BASE + "robots.txt").text()
    check("robots.txt points to the sitemap", "Sitemap: https://learnalefba.com/sitemap.xml" in robots and "Disallow: /\n" not in robots, robots)
    for slug in PAGES:
        url = BASE + (slug + ".html" if slug else "")
        pg.goto(url)
        title = pg.title(); h1 = pg.locator("h1").count()
        text = pg.evaluate("document.body.innerText") or ""
        canon = pg.evaluate("(document.querySelector('link[rel=canonical]') || {}).href || ''")
        robots_meta = pg.evaluate("(document.querySelector('meta[name=robots]') || {}).content || ''")
        words = len(text.split())
        name = slug or "home"
        check(f"{name}: title names Alefba and Persian, one h1, {words} words without JavaScript",
              "Alefba" in title and "Persian" in title and h1 == 1 and words >= 150, (title, h1, words))
        check(f"{name}: canonical to itself, indexable, in the sitemap",
              canon == "https://learnalefba.com/" + slug and "noindex" not in robots_meta and f"<loc>https://learnalefba.com/{slug}</loc>" in sitemap, (canon, robots_meta))
    b.close()
print(f"{sum(OK)}/{len(OK)}")
sys.exit(0 if all(OK) else 1)
