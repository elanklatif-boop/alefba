# "Hear yourself" on Speak cards: the recording is tidied (quiet before and after cut, same loudness as the real
# voice, a little silence in front, nothing in the middle turned down).
import sys, json
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8811/"
OK = []
def check(name, cond, info=""):
    OK.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{info}]"))

with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "?nostats"); pg.wait_for_timeout(800)
    r = pg.evaluate("""() => {
      const rate = 16000, n = rate * 3, x = new Float32Array(n);
      let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647 - 0.5;
      // 1 s of room noise, then 0.8 s of a loud voice (soft start: an 'h' 60 ms long), then noise again
      for (let i = 0; i < n; i++) x[i] = rnd() * 0.02;
      const v0 = rate * 1.0, v1 = rate * 1.8;
      for (let i = v0; i < v1; i++) { const soft = i < v0 + rate * 0.06; x[i] += (soft ? 0.03 : 0.6) * Math.sin(i / rate * 2 * Math.PI * 220); }
      const y = cleanVoice(x, rate);
      const lead = Math.round(rate * 0.25);
      const rms = (a, s, e) => { let t = 0; for (let i = s; i < e; i++) t += a[i] * a[i]; return Math.sqrt(t / Math.max(1, e - s)); };
      let peak = 0; for (const v of y) peak = Math.max(peak, Math.abs(v));
      // where the soft start lands in the cleaned clip
      let firstSound = -1; for (let i = 0; i < y.length; i++) if (Math.abs(y[i]) > 0.004) { firstSound = i; break; }
      const voiceStart = firstSound;
      return { len: y.length / rate, leadQuiet: rms(y, 0, lead - 10), peak,
               voiceRms: rms(y, lead + rate * 0.15, lead + rate * 0.7),
               noiseBefore: rms(x, 0, rate * 0.5), noiseAfter: rms(y, y.length - rate * 0.12, y.length - rate * 0.01),
               softKept: firstSound > 0 && firstSound < lead + rate * 0.1, firstSound: firstSound / rate };
    }""")
    check("quiet before and after is cut (3 s becomes about 1.5 s)", 1.1 < r["len"] < 1.8, r)
    check("a short silence in front, so speakers don't swallow the start", r["leadQuiet"] < 0.001, r)
    check("the soft start of the word is kept", r["softKept"], r)
    check("voice at the real recordings' loudness (not boosted to the top)", 0.03 < r["voiceRms"] < 0.08 and r["peak"] <= 0.51, r)
    m = pg.evaluate("""() => {
      // "ta" loud, then a much softer second of voice, then loud again: like تعارف نکن said unevenly
      const rate = 16000, n = rate * 3, x = new Float32Array(n);
      let seed = 3; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647 - 0.5;
      for (let i = 0; i < n; i++) x[i] = rnd() * 0.01;
      const seg = (a, b, amp) => { for (let i = a * rate; i < b * rate; i++) x[i] += amp * Math.sin(i / rate * 2 * Math.PI * 200); };
      seg(0.5, 0.7, 0.8); seg(0.7, 1.7, 0.02); seg(1.7, 2.1, 0.5);
      const y = cleanVoice(x, rate);
      const rms = (a, s, e) => { let t = 0; for (let i = Math.round(s); i < Math.round(e); i++) t += a[i] * a[i]; return Math.sqrt(t / Math.max(1, Math.round(e) - Math.round(s))); };
      // find the loud start in the output, then compare the soft middle with it, before and after
      let at = 0; while (at < y.length && Math.abs(y[at]) < 0.05) at++;
      const inRatio = rms(x, 0.9 * rate, 1.5 * rate) / rms(x, 0.55 * rate, 0.65 * rate);
      const outRatio = rms(y, at + 0.4 * rate, at + 1.0 * rate) / rms(y, at + 0.05 * rate, at + 0.15 * rate);
      return { inRatio, outRatio };
    }""")
    check("a softer middle of a phrase isn't turned down (no cut out after the first sound)", abs(m["outRatio"] / m["inRatio"] - 1) < 0.15, m)
    q = pg.evaluate("""() => { const x = new Float32Array(16000); for (let i = 0; i < x.length; i++) x[i] = Math.sin(i) * 0.0005; const y = cleanVoice(x, 16000); let p = 0; for (const v of y) p = Math.max(p, Math.abs(v)); return p; }""")
    check("near silence isn't blown up into loud hiss", q < 0.004, q)
    check("no page errors", not errs, errs)
    b.close()
print(f"{sum(OK)}/{len(OK)}")
sys.exit(0 if all(OK) else 1)
