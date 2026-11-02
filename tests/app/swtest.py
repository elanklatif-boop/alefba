# Old site (v68) on a port, the page saves word_sar.mp3 (computer voice) on the device; then the server switches to
# the new build, the page reloads, and word_sar.mp3 must now come back as the family recording.
import subprocess, time, os, hashlib
from playwright.sync_api import sync_playwright
SP = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec30/"
link = SP + "serve_root"
def serve(target):
    if os.path.islink(link): os.unlink(link)
    os.symlink(target, link)
res = []
def check(n, ok, x=""): res.append(ok); print("PASS" if ok else "FAIL", n, "" if ok else x)
md5 = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
OLD, NEW = md5(SP + "site68/audio/word_sar.mp3"), md5("/home/claude/alefba-site/audio/word_sar.mp3")
OLDG, NEWG = md5(SP + "site68/audio/word_gol.mp3"), md5("/home/claude/alefba-site/audio/word_gol.mp3")
serve(SP + "site68")
srv = subprocess.Popen(["python3", "-m", "http.server", "8821", "-d", link], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
GET = """async f => { const r = await fetch('audio/' + f); const b = await r.arrayBuffer(); const h = await crypto.subtle.digest('SHA-256', b); return b.byteLength; }"""
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); c = b.new_context(); pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8821/"); pg.wait_for_timeout(1500); pg.reload(); pg.wait_for_timeout(1500)
        check("the old helper is running", pg.evaluate("!!navigator.serviceWorker.controller"))
        a1 = pg.evaluate(GET, "word_sar.mp3"); g1 = pg.evaluate(GET, "word_gol.mp3"); pg.wait_for_timeout(300)
        check("old site: word_sar.mp3 is the computer voice", a1 == os.path.getsize(SP + "site68/audio/word_sar.mp3"), a1)
        cached = pg.evaluate("caches.open('alefba-media-v1').then(c => c.keys()).then(k => k.map(r => r.url.split('/').pop()))")
        check("and it's saved on the device", "word_sar.mp3" in cached, cached)
        # the server now has the new build
        serve("/home/claude/alefba-site"); pg.reload(); pg.wait_for_timeout(2500); pg.reload(); pg.wait_for_timeout(2500)
        v = pg.evaluate("fetch('sw.js').then(r => r.text()).then(t => t.includes('realList'))")
        check("the new helper is in charge", v and pg.evaluate("!!navigator.serviceWorker.controller"))
        a2 = pg.evaluate(GET, "word_sar.mp3")
        check(f"word_sar.mp3 is now the family recording ({a1} -> {a2} bytes)", a2 == os.path.getsize("/home/claude/alefba-site/audio/word_sar.mp3"), a2)
        cached = pg.evaluate("caches.open('alefba-media-v1').then(c => c.keys()).then(k => k.map(r => r.url.split('/').pop()))")
        check("the first-run mark is saved", ".fresh-2" in cached, cached)
        # a later new recording: pretend word_gol was only just added (drop it from the saved list), save a fake old copy
        pg.evaluate("""async () => { const c = await caches.open('alefba-media-v1'); const k = (await c.keys()).find(r => /real_voice/.test(r.url));
            const list = await (await c.match(k)).json(); await c.put(k, new Response(JSON.stringify(list.filter(f => f !== 'word_gol.mp3'))));
            await c.put(new URL('audio/word_gol.mp3', location.href).href, new Response(new Uint8Array(10))); }""")
        check("a stale 10-byte copy of word_gol.mp3 is now on the device", pg.evaluate(GET, "word_gol.mp3") == 10)
        check("word_sar.mp3 is still on the device before the list is refreshed", "word_sar.mp3" in pg.evaluate("caches.open('alefba-media-v1').then(c => c.keys()).then(k => k.map(r => r.url.split('/').pop()))"))
        pg.reload(); pg.wait_for_timeout(2000)
        g2 = pg.evaluate(GET, "word_gol.mp3")
        check(f"after the list is refreshed, word_gol.mp3 is fetched again ({g2} bytes)", g2 == os.path.getsize("/home/claude/alefba-site/audio/word_gol.mp3"), g2)
        cached = pg.evaluate("caches.open('alefba-media-v1').then(c => c.keys()).then(k => k.map(r => r.url.split('/').pop()))")
        check("recordings that didn't change stay saved (word_sar.mp3 not dropped again)", pg.evaluate("caches.open('alefba-media-v1').then(c => c.match(new URL('audio/word_sar.mp3', location.href).href)).then(r => !!r)"))
        # offline: the list and sounds still work
        c.set_offline(True); pg.reload(); pg.wait_for_timeout(1500)
        check("offline: the app opens and word_sar.mp3 still plays from the device", pg.evaluate(GET, "word_sar.mp3") == os.path.getsize("/home/claude/alefba-site/audio/word_sar.mp3"))
        check("offline: the list of recordings comes from the device", pg.evaluate("REAL_VOICE.has('word_sar.mp3')"))
        c.set_offline(False)
        check("no page errors", not errs, errs); b.close()
finally:
    srv.terminate()
print(f"{sum(res)}/{len(res)} passed")
