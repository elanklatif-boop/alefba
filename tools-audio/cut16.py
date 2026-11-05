# The "time" words (روز ... بازی) in Elan's voice, from his Nov 5 recording: each said twice; the take whisper
# hears as the word wins, then the one without clipping, then the first.
import subprocess, re, json, wave, numpy as np, sherpa_onnx
SP = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec16/"
M = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/asr/sherpa-onnx-whisper-small/"
MAP = [("ruz","روز",(1.00,1.80),(3.28,4.22)),("shab","شب",(6.18,7.12),(8.38,9.48)),("sobh","صبح",(11.18,11.98),(13.36,14.20)),
 ("zohr","ظهر",(15.94,17.00),(18.22,19.24)),("asr","عصر",(20.78,21.66),(23.06,23.98)),("emruz","امروز",(25.40,26.80),(27.70,29.04)),
 ("fardaa","فردا",(29.76,31.46),(32.50,33.74)),("diruz","دیروز",(35.06,36.70),(37.22,38.84)),("haalaa","حالا",(39.40,40.88),(41.86,43.02)),
 ("hamishe","همیشه",(44.80,46.32),(47.54,48.70)),("saaat","ساعت",(50.14,51.30),(52.52,53.82)),("hafte","هفته",(55.20,56.30),(57.64,58.72)),
 ("saal","سال",(59.58,61.16),(62.44,63.74)),("dars","درس",(64.94,66.08),(66.90,68.18)),("khaab","خواب",(69.08,70.18),(71.18,72.26)),
 ("baazi","بازی",(73.30,74.42),(75.38,76.70))]
w = wave.open(SP + "src.wav"); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768
h = sr // 100; fr = x[:len(x) // h * h].reshape(-1, h); DB = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
noise = np.percentile(DB, 20)
R = sherpa_onnx.OfflineRecognizer.from_whisper(encoder=M + "small-encoder.int8.onnx", decoder=M + "small-decoder.int8.onnx", tokens=M + "small-tokens.txt", language="fa", task="transcribe", num_threads=4)
def heard(s, e):
    y = x[int(s * sr):int(e * sr)]; y16 = np.interp(np.arange(0, len(y), sr / 16000), np.arange(len(y)), y).astype(np.float32)
    st = R.create_stream(); st.accept_waveform(16000, y16); R.decode_stream(st); return re.sub(r"[^\u0600-\u06FF]", "", st.result.text)
def core(a, b):
    s, e = int(a * 100), int(b * 100); d = DB[s:e]; thr = max(noise + 18, d.max() - 32)
    on = d > thr; runs = []; st = None
    for i, v in enumerate(on):
        if v and st is None: st = i
        if not v and st is not None: runs.append([st, i]); st = None
    if st is not None: runs.append([st, len(on)])
    m = []
    for r in runs:
        if m and r[0] - m[-1][1] < 18: m[-1][1] = r[1]
        else: m.append(r)
    best = max(m, key=lambda r: (10 ** (d[r[0]:r[1]] / 10)).sum())
    s2, e2 = s + best[0], s + best[1]; lo = noise + 10
    while s2 > s - 25 and DB[s2 - 1] > lo: s2 -= 1
    while e2 < e + 40 and DB[e2] > lo: e2 += 1
    return s2 / 100 - 0.08, e2 / 100 + 0.12
def clip(a, b): return int((np.abs(x[int(a * sr):int(b * sr)]) > 0.98).sum())
def loud(p):
    r = subprocess.run(["ffmpeg","-v","info","-i",p,"-af","apad=pad_dur=1,ebur128=framelog=quiet","-f","null","-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
TARGET = -25.5; res = []
norm = lambda t: t.replace("ي", "ی").replace("ك", "ک")
for name, fa, t1, t2 in MAP:
    takes = []
    for k, (a, b) in enumerate((t1, t2)):
        s, e = core(a, b); takes.append(dict(k=k, s=s, e=e, d=e - s, c=clip(s, e), h=heard(s, e)))
    ok = [t for t in takes if 0.35 <= t["d"] <= 1.9] or takes
    pick = min(ok, key=lambda t: (norm(t["h"]) != fa, t["c"] > 0, t["c"], t["k"]))
    s, e, d = pick["s"], pick["e"], pick["d"]; tmp = SP + "out/tmp.wav"
    pre = "highpass=f=70" + (",adeclip" if pick["c"] else "")
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{s:.3f}","-to",f"{e:.3f}","-i",SP + "src.wav","-af",pre,"-ac","1","-ar","24000",tmp], check=True)
    Lu = loud(tmp); out = SP + f"out/word_{name}.mp3"
    af = f"volume={TARGET-Lu:.2f}dB,alimiter=limit=0.70:level=disabled,afade=t=in:d=0.02,afade=t=out:st={d-0.06:.3f}:d=0.06"
    subprocess.run(["ffmpeg","-v","error","-y","-i",tmp,"-af",af,"-ac","1","-ar","24000","-b:a","64k",out], check=True)
    res.append(dict(name=name, take=pick["k"] + 1, s=round(s, 2), e=round(e, 2), d=round(d, 2), clip=pick["c"], heard=[t["h"] for t in takes]))
    print(f"{name:<8} take {pick['k']+1} {s:6.2f}-{e:6.2f} ({d:.2f}s) clip {pick['c']:3d} heard {[t['h'] for t in takes]} -> {loud(out):.1f} LUFS")
json.dump(res, open(SP + "cuts.json", "w"), indent=1, ensure_ascii=False)
