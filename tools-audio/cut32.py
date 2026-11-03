import subprocess, re, json, wave, numpy as np, sys
SP = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec32/"
T = json.load(open(SP + "takes.json"))["src"]
seg = lambda i: (T[i]["a"], T[i]["b"])
MAP = [("alef",1,2),("be",3,4),("pe",5,6),("te",7,8),("se",9,10),("jim",11,12),("che",13,14),("he",15,16),("khe",17,18),
 ("daal",19,20),("zaal",22,23),("re",24,25),("ze",26,27),("zhe",28,29),("sin",31,32),("shin",33,34),
 ("saad",(109.98,110.56),(112.06,112.79)),("zaad",(114.80,115.57),(118.05,118.63)),
 ("taa",37,38),("zaa",39,40),("eyn",41,42),("gheyn",43,44),("fe",45,46),("ghaaf",47,48),("kaaf",49,50),("gaaf",51,52),
 ("laam",53,54),("mim",55,56),("nun",57,58),("vaav",59,60),("he_do_cheshm",61,62),("ye",64,65)]
w = wave.open(SP + "src.wav"); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768
h = sr // 100; fr = x[:len(x) // h * h].reshape(-1, h); DB = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
noise = np.percentile(DB, 20)
def core(a, b):
    # the loudest connected stretch inside [a,b]: drops breaths and the odd "uh" around the letter
    s, e = int(a * 100), int(b * 100); d = DB[s:e]; thr = max(noise + 18, d.max() - 32)
    on = d > thr; runs = []; st = None
    for i, v in enumerate(on):
        if v and st is None: st = i
        if not v and st is not None: runs.append([st, i]); st = None
    if st is not None: runs.append([st, len(on)])
    m = []
    for r in runs:
        if m and r[0] - m[-1][1] < 12: m[-1][1] = r[1]
        else: m.append(r)
    best = max(m, key=lambda r: (10 ** (d[r[0]:r[1]] / 10)).sum())  # most sound energy, not the most dB
    s2, e2 = s + best[0], s + best[1]
    lo = noise + 10
    while s2 > s - 25 and DB[s2 - 1] > lo: s2 -= 1   # soft onsets
    while e2 < e + 40 and DB[e2] > lo: e2 += 1       # soft endings (m, n, f)
    return s2 / 100 - 0.08, e2 / 100 + 0.12
def clip(a, b): return int((np.abs(x[int(a * sr):int(b * sr)]) > 0.98).sum())
def loud(p):
    r = subprocess.run(["ffmpeg","-v","info","-i",p,"-af","apad=pad_dur=1,ebur128=framelog=quiet","-f","null","-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
TARGET = -25.5; res = []
for name, t1, t2 in MAP:
    takes = []
    for k, t in enumerate((t1, t2)):
        a, b = seg(t) if isinstance(t, int) else t
        s, e = core(a, b); takes.append(dict(k=k, s=s, e=e, d=e - s, c=clip(s, e)))
    ok = [t for t in takes if 0.35 <= t["d"] <= 1.35] or takes
    pick = min(ok, key=lambda t: (t["c"] > 0, t["c"], t["k"]))
    s, e, d = pick["s"], pick["e"], pick["d"]; tmp = SP + "out/tmp.wav"
    pre = "highpass=f=70" + (",adeclip" if pick["c"] else "")
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{s:.3f}","-to",f"{e:.3f}","-i",SP + "src.wav","-af",pre,"-ac","1","-ar","24000",tmp], check=True)
    Lu = loud(tmp); out = SP + f"out/letter_{name}.mp3"
    af = f"volume={TARGET-Lu:.2f}dB,alimiter=limit=0.70:level=disabled,afade=t=in:d=0.02,afade=t=out:st={d-0.06:.3f}:d=0.06"
    subprocess.run(["ffmpeg","-v","error","-y","-i",tmp,"-af",af,"-ac","1","-ar","24000","-b:a","64k",out], check=True)
    res.append(dict(name=name, take=pick["k"] + 1, s=round(s, 2), e=round(e, 2), d=round(d, 2), clip=pick["c"], other=[(round(t["d"],2), t["c"]) for t in takes]))
    print(f"{name:<13} take {pick['k']+1}  {s:7.2f}-{e:7.2f} ({d:.2f}s) clipped {pick['c']:3d}  takes {[(round(t['d'],2), t['c']) for t in takes]}  -> {loud(out):.1f} LUFS")
json.dump(res, open(SP + "cuts.json", "w"), indent=1)
