import subprocess, re, json, wave, numpy as np
SP = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec30/"
T = json.load(open(SP + "takes.json"))
slug = lambda s: re.sub(r"[^A-Za-z0-9_]", "", s.replace("â", "aa").replace(" ", "_"))
# (kind, finglish, source, take): the cleaner take of each pair
L = [("word","sar","r0",4),("word","cheshm","r0",7),("word","gush","r0",8),("word","bini","r0",10),("said","dahan","r0",12),
     ("word","dahân","r0",13),("word","dandân","r0",15),("word","mu","r0",17),("word","dast","r0",18),("word","pâ","r0",21),
     ("word","ghalb","r0",22),("word","khoshhâl","r1",2),("word","nârâhat","r1",4),("word","khaste","r1",5),
     ("word","asabâni","r1",7),("word","tarside","r1",9)]
TARGET = -25.5
def rd(n):
    w = wave.open(SP + n + ".wav"); sr = w.getframerate(); return np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768, sr
A = {n: rd(n) for n in ("r0", "r1")}
def db_track(x, sr):
    h = sr // 100; fr = x[:len(x) // h * h].reshape(-1, h); return 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
def edges(n, a, b):
    x, sr = A[n]; db = db_track(x, sr); noise = np.percentile(db, 20); thr = noise + 10
    s = int(a * 100); e = int(b * 100)
    while s > int(a * 100) - 25 and db[s - 1] > thr: s -= 1          # soft onsets (s, ch, kh)
    while e < int(b * 100) + 45 and db[e] > thr: e += 1             # weak endings (m, t, b, e)
    nxt = [t["a"] for t in T[n] if t["a"] > b]; lim = (min(nxt) - 0.15) if nxt else 1e9
    return max(0, s / 100 - 0.10), min(e / 100 + 0.15, lim)
def loud(p):
    r = subprocess.run(["ffmpeg","-v","info","-i",p,"-af","ebur128=framelog=quiet","-f","null","-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
res = []
for kind, tr, src, i in L:
    t = T[src][i]; s, e = edges(src, t["a"], t["b"]); x, sr = A[src]
    c = int((np.abs(x[int(s * sr):int(e * sr)]) > 0.98).sum()); tmp = SP + "out/tmp.wav"
    pre = "highpass=f=70" + (",adeclip" if c else "")
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{s:.3f}","-to",f"{e:.3f}","-i",SP + src + ".wav","-af",pre,"-ac","1","-ar","24000",tmp], check=True)
    Lu = loud(tmp); d = e - s; out = SP + f"out/{kind}_{slug(tr)}.mp3"
    af = f"volume={TARGET-Lu:.2f}dB,alimiter=limit=0.70:level=disabled,afade=t=in:d=0.025,afade=t=out:st={d-0.06:.3f}:d=0.06"
    subprocess.run(["ffmpeg","-v","error","-y","-i",tmp,"-af",af,"-ac","1","-ar","24000","-b:a","64k",out], check=True)
    res.append(dict(kind=kind, tr=tr, src=src, take=i, s=round(s, 2), e=round(e, 2), file=out.split("/")[-1]))
    print(f"{tr:<9} {src} take {i:<2} {s:6.2f}-{e:6.2f} ({d:4.2f}s, word {t['b']-t['a']:.2f}s) clipped {c:3d} -> {loud(out):.1f} LUFS  {out.split('/')[-1]}")
json.dump(res, open(SP + "cuts.json", "w"), ensure_ascii=False, indent=1)
