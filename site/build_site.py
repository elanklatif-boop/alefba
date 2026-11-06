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
DESC = "Learn to read and speak Persian (Farsi) at your own pace: the alphabet, everyday words with real voices, and practice conversations. For kids, families and adults. Free to start."
HEAD = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="{DESC}">
<meta name="theme-color" content="#1c3780">
<link rel="canonical" href="https://learnalefba.com/">
<meta property="og:title" content="Alefba الفبا">
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
open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(HEAD + app + "\n</body>\n</html>\n")
for f in ("_worker.js", "_routes.json", "_headers", "parents.html","adults.html", "teachers.html", "about.html", "class-note.html", "learn-persian.html","learn-persian-adults.html", "robots.txt", "sitemap.xml", "manifest.webmanifest"):
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
