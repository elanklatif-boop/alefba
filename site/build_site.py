"""Build the Alefba website folder from the app (web/alefba.html) and its recordings.
The result, ../alefba-site, is what gets uploaded to Cloudflare Pages (drag and drop the folder)."""
import os, shutil, json, re
HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web")
OUT = os.path.join(HERE, "..", "alefba-site")

app = open(os.path.join(WEB, "alefba.html"), encoding="utf-8").read()
assert "window.ALEFBA_WEB" in app, "the app needs its website mode"
# The website serves its own fonts, so visitors' browsers never contact Google.
GOOGLE_FONTS = re.compile(r'<link rel="preconnect" href="https://fonts\.googleapis\.com">\s*<link rel="preconnect" href="https://fonts\.gstatic\.com" crossorigin>\s*<link rel="stylesheet" href="https://fonts\.googleapis\.com/css2\?[^"]*">')
assert len(GOOGLE_FONTS.findall(app)) == 1, "the app's font links changed: update the website's fonts"
app = GOOGLE_FONTS.sub('<link rel="stylesheet" href="fonts/fonts.css">', app)
assert "googleapis" not in app and "gstatic" not in app

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%231c3780'/%3E"
           "%3Ctext x='32' y='46' font-size='40' text-anchor='middle' fill='%23f2b23c' font-family='Tahoma,sans-serif'%3E%D8%A7%3C/text%3E%3C/svg%3E")
DESC = "Learn to read and speak Persian (Farsi) online, the way Iranians actually talk: the alphabet, real voices and practice conversations. For kids, families and adults. Free lessons to start."
TITLE = "Learn Persian (Farsi) Online, Free to Start | Alefba الفبا"
# Questions and answers shown at the foot of the home page, and the same ones told to search engines (they must match what people can see).
FAQ = [
 ("Is Alefba free?", "Yes, to start. The Persian alphabet, the first 3 levels, the Shab-e Yalda pack and the Taarof pack are free, with no account needed. Teacher mode is free for teachers. A plan opens all 16 levels, the stories, the games and the AI talks."),
 ("How much does a plan cost?", "A plan opens all 16 levels, the stories, the games and the AI talks for the whole family: $5 a month, or $39 a year (about $3.25 a month). You can cancel any time. Persian schools can get a school plan for their students."),
 ("Does Alefba teach spoken Persian or book Persian?", "Both, side by side. Books say nân (bread) and khâne (house), but people say nun and khune. Alefba shows how each word and sentence is written and how Iranians actually say it, with real recorded voices."),
 ("What ages is Alefba for?", "Children 7 to 12, teens and adults have their own lessons and conversations, and there's a little mode for ages 3 to 6 with pictures, flashcards and letter tracing, with no reading needed."),
 ("Can I learn the Persian alphabet with Alefba?", "Yes. All 32 letters, one at a time, with each letter's shapes, its sound recorded by a real voice, a word that uses it, and tracing practice."),
 ("Is there a Duolingo for Persian?", "As of 2026, Duolingo doesn't offer a Persian (Farsi) course. Alefba is a Persian course you can use in your browser, free to start. Alefba isn't connected to Duolingo."),
 ("Can Persian schools and teachers use Alefba?", "Yes. Teacher mode is free: make a class, choose who it's for, share one link, and see how each student is doing."),
 ("Do I need to download anything?", "No. Alefba runs in the browser on a phone, tablet or computer, and you can add it to your home screen like an app."),
]
import html as _html, json as _json
LD = [
 {"@context": "https://schema.org", "@type": "WebSite", "name": "Alefba", "alternateName": "الفبا", "url": "https://learnalefba.com/"},
 {"@context": "https://schema.org", "@type": "WebApplication", "name": "Alefba", "url": "https://learnalefba.com/", "applicationCategory": "EducationalApplication", "operatingSystem": "Any (web browser)",
  "inLanguage": "en", "description": DESC, "image": "https://learnalefba.com/icons/og-image.png",
  "offers": [{"@type": "Offer", "price": "0", "priceCurrency": "USD", "description": "The alphabet and the first 3 levels are free"},
            {"@type": "Offer", "price": "39", "priceCurrency": "USD", "description": "Yearly family plan: all 16 levels, stories, games and AI talks (about $3.25 a month)"}]},
 {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
]
LD_TAGS = "".join(f'<script type="application/ld+json">{_json.dumps(x, ensure_ascii=False)}</script>\n' for x in LD)
ABOUT = (
 '<section class="site-about" aria-labelledby="siteAboutH"><style>'
 '.site-about{max-width:620px;margin:0 auto;padding:8px max(16px,env(safe-area-inset-left,0px)) calc(110px + env(safe-area-inset-bottom,0px));color:var(--muted);font-size:.92rem;line-height:1.55;border-top:1px solid var(--line)}'
 '.site-about h2{font-family:var(--font-display,Georgia,serif);color:var(--ink);font-size:1.15rem;margin:18px 0 6px}'
 '.site-about h3{color:var(--ink);font-size:1rem;margin:16px 0 6px}.site-about p{margin:0 0 8px}.site-about ul{margin:0 0 8px;padding-left:1.2em}'
 '.site-about details{border-bottom:1px solid var(--line);padding:8px 0}.site-about summary{cursor:pointer;color:var(--ink);font-weight:600;min-height:32px}'
 '.site-about a{color:var(--lapis-text);font-weight:600}.site-about .trust{margin-top:14px;font-size:.86rem}'
 '@media (min-width:960px){.site-about{max-width:760px;padding-bottom:48px}}'
 '@media (display-mode:standalone){.site-about{display:none}}'
 'body:has(#view-lessons[hidden]) .site-about{display:none}'
 '</style>'
 '<h2 id="siteAboutH">Learn Persian (Farsi) online, the way Iranians actually speak</h2>'
 '<p>Alefba teaches you to read and speak Persian. Books say <span lang="fa">نان</span> (nân) and <span lang="fa">خانه</span> (khâne), but people say <span lang="fa">نون</span> (nun) and <span lang="fa">خونه</span> (khune), so every word and sentence shows both, with real recorded voices. Free Persian lessons to start, in your browser, with nothing to download.</p>'
 '<p><b>Price:</b> the alphabet and the first 3 levels are free. A plan opens all 16 levels: $5 a month, or $39 a year (about $3.25 a month).</p>'
 '<ul><li>The Persian alphabet: all 32 letters, with tracing</li><li>252 everyday words and 16 short stories</li><li>Practice conversations at your level</li>'
 '<li>A free Taarof pack: Persian manners, with a game</li><li>A little mode for ages 3 to 6</li><li>A free teacher mode for Persian schools</li></ul>'
 '<h3>Questions</h3>'
 + "".join(f"<details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>" for q, a in FAQ) +
 '<p class="trust">No ads and no tracking. Payments are handled by Stripe. Made by a student in New York, with recordings by his family.</p>'
 '<p><a href="learn-persian">Persian for kids</a> · <a href="learn-persian-adults">Persian for adults</a> · <a href="parents">For parents</a> · <a href="teachers">For teachers</a> · <a href="name">Your name in Persian</a> · <a href="about">Who made Alefba</a></p>'
 '</section>\n')
HEAD = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="{DESC}">
<meta name="theme-color" content="#1c3780">
<link rel="canonical" href="https://learnalefba.com/">
<meta property="og:title" content="Alefba: learn Persian the way Iranians actually speak">
<meta property="og:description" content="{DESC}">
<meta property="og:url" content="https://learnalefba.com/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Alefba">
<meta property="og:image" content="https://learnalefba.com/icons/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Alefba: learn to read and speak Persian">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://learnalefba.com/icons/og-image.png">
<link rel="icon" href="{FAVICON}">
<link rel="manifest" href="manifest.webmanifest">
{LD_TAGS}
<link rel="apple-touch-icon" href="icons/icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Alefba">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<style>:root{{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}html{{scroll-padding-top:env(safe-area-inset-top,0px)}}body{{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}}img{{max-width:100%}}[hidden]:not([hidden=until-found i]){{display:none!important}}</style>
<script>window.ALEFBA_WEB = {{ api: "/api", parentsUrl: "parents.html", adultsUrl: "adults.html", teachersUrl: "teachers.html", aboutUrl: "about.html" }};</script>
</head>
<body>
"""
if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(os.path.join(OUT, "audio"))
assert app.count("<title>Alefba الفبا</title>") == 1 and app.count("</main>") == 1
app = app.replace("<title>Alefba الفبا</title>", f"<title>{TITLE}</title>").replace("</main>", "</main>\n" + ABOUT, 1)
open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(HEAD + app + "\n</body>\n</html>\n")
for f in ("_worker.js", "_routes.json", "_headers", "parents.html","adults.html", "teachers.html", "about.html", "class-note.html", "name.html", "taarof.html", "learn-persian.html","learn-persian-adults.html", "robots.txt", "sitemap.xml", "manifest.webmanifest"):
    shutil.copyfile(os.path.join(HERE, f), os.path.join(OUT, f))
shutil.copytree(os.path.join(HERE, "fonts"), os.path.join(OUT, "fonts"))
shutil.copytree(os.path.join(HERE, "icons"), os.path.join(OUT, "icons"))
shutil.copytree(os.path.join(HERE, "img"), os.path.join(OUT, "img"))  # screenshots for the teachers page
# the offline helper gets a version made from the app's own text, so every upload with a change clears the old copy
import hashlib
build = hashlib.sha256((HEAD + app).encode("utf-8")).hexdigest()[:12]
open(os.path.join(OUT, "sw.js"), "w", encoding="utf-8").write(open(os.path.join(HERE, "sw.js"), encoding="utf-8").read().replace("__BUILD__", build))
assert "googleapis" not in open(os.path.join(OUT, "parents.html"), encoding="utf-8").read()
manifest = json.load(open(os.path.join(WEB, "audio", "manifest.json")))
for f in manifest + ["manifest.json", "real_voice.json"]:
    shutil.copyfile(os.path.join(WEB, "audio", f), os.path.join(OUT, "audio", f))
n = sum(len(fs) for _, _, fs in os.walk(OUT))
size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(OUT) for f in fs)
print(f"built {OUT}: {n} files, {size / 1e6:.1f} MB")
