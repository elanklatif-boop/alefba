import json
from playwright.sync_api import sync_playwright
res=[]
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
FREE = {"talks": True, "plans": True, "signedIn": False, "canTalk": True, "kind": None, "plan": None, "left": 3, "free": 3}
st={"done": {"a1-1": True}, "items": {"letter:he jimi": {"r": 3, "w": 0}, "trace:he jimi": {"r": 1, "w": 0}}, "days": [], "talks": {}, "prefs": {"lang": "en", "fing": "auto", "order": "letters"}, "log": {}, "speak": 1, "read": 1,
    "profile": {"name": "Sara", "goal": 2, "adult": False, "speakSelf": 1, "readSelf": 1, "reasons": []}}
with sync_playwright() as p:
    b=p.chromium.launch();c=b.new_context(viewport={"width":390,"height":844})
    c.add_init_script("if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('alefba-v3', " + json.dumps(json.dumps(st)) + ") }")
    c.route("**/api/me*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(FREE)))
    pg=c.new_page();errs=[];pg.on("pageerror",lambda x:errs.append(str(x)));pg.goto("http://127.0.0.1:8811/");pg.wait_for_timeout(1500)
    L=pg.evaluate("BY_GLYPH['ح']")
    check(f"ح is called he ({L[1]})", L[1]=="he")
    check("its sound is letter_he.mp3 and that file ships", pg.evaluate("letterAudio(BY_GLYPH['ح']).file === 'letter_he.mp3' && fileFor(letterAudio(BY_GLYPH['ح'])) === 'letter_he.mp3'"))
    check("ه is still he do cheshm", pg.evaluate("BY_GLYPH['ه'][1]") == "he do cheshm")
    check("progress saved under he jimi still counts (knows the letter)", pg.evaluate("knowsLetter(BY_GLYPH['ح'])"))
    check("new answers are still saved under the old key", pg.evaluate("exTrace(BY_GLYPH['ح']).key") == "trace:he jimi" and pg.evaluate("exLetterName(BY_GLYPH['ح'], LETTERS.slice(4,8)).key") == "letter:he jimi")
    check("a review question can be made from the old key", pg.evaluate("(() => { const e = exForKey('letter:he jimi'); return !!e && e.reveal.join('').includes('he'); })()"), pg.evaluate("(() => { const e = exForKey('letter:he jimi'); return e && e.reveal; })()"))
    q=pg.evaluate("exLetterName(BY_GLYPH['ح'], LETTERS.slice(4,8)).options.map(o=>o.t)")
    check(f"the answers say he, not he jimi ({q})", "he (h)" in q and not any("jimi" in x for x in q))
    check("emshab plays the trimmed recording", pg.evaluate("fileFor(wordAudio(SEASON_WORDS.find(W => W.tr === 'emshab')))") == "word_emshab.mp3")
    check("no page errors", not errs, errs)
    b.close()
print(f"{sum(res)}/{len(res)} passed")
