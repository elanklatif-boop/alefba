# Numbers (یک ... ده, عدد, چند) from Elan's voice note of 6 Nov: each word said twice; the take Whisper heard right is used.
import subprocess, re, json, wave, numpy as np
SP = "/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/rec41/"
S=[1.54,4.39,7.48,9.92,12.58,15.10,18.04,20.79,23.34,25.65,28.05,30.33,32.95,35.11,37.46,39.62,41.95,44.21,46.51,48.85,51.83,54.27,56.58,58.79]
D=[.80,.55,.52,.62,.67,.72,.73,.76,.97,.82,.82,.80,.47,.57,.95,.76,.71,.66,.58,.84,.57,.60,.84,.84]
NAMES = ["yek","do","se","chahaar","panj","shesh","haft","hasht","noh","dah","adad","chand"]
WRONG = {("haft",0), ("dah",1)}   # takes Whisper heard as another word
w = wave.open(SP + "src.wav"); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768
h = sr // 100; fr = x[:len(x) // h * h].reshape(-1, h); DB = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
noise = np.percentile(DB, 20)
def edges(a, d):
    s, e = int(a * 100), int((a + d) * 100); lo = max(noise + 10, -50)
    while s > a * 100 - 25 and DB[s - 1] > lo: s -= 1
    while e < (a + d) * 100 + 40 and DB[e] > lo: e += 1
    return s / 100 - 0.08, e / 100 + 0.12
def clip(a, b): return int((np.abs(x[int(a * sr):int(b * sr)]) > 0.98).sum())
def loud(p):
    r = subprocess.run(["ffmpeg","-v","info","-i",p,"-af","apad=pad_dur=1,ebur128=framelog=quiet","-f","null","-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
TARGET = -25.5
for n, name in enumerate(NAMES):
    takes = []
    for k in (0, 1):
        s, e = edges(S[2*n+k], D[2*n+k]); takes.append(dict(k=k, s=s, e=e, c=clip(s, e), bad=(name, k) in WRONG))
    pick = min(takes, key=lambda t: (t["bad"], t["c"] > 0, t["c"], t["k"]))
    s, e = pick["s"], pick["e"]; d = e - s; tmp = SP + "out/tmp.wav"
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{s:.3f}","-to",f"{e:.3f}","-i",SP + "src.wav","-af","highpass=f=70" + (",adeclip" if pick["c"] else ""),"-ac","1","-ar","24000",tmp], check=True)
    Lu = loud(tmp); out = SP + f"out/word_{name}.mp3"
    af = f"volume={TARGET-Lu:.2f}dB,alimiter=limit=0.70:level=disabled,afade=t=in:d=0.02,afade=t=out:st={d-0.06:.3f}:d=0.06"
    subprocess.run(["ffmpeg","-v","error","-y","-i",tmp,"-af",af,"-ac","1","-ar","24000","-b:a","64k",out], check=True)
    print(f"{name:<8} take {pick['k']+1} {s:6.2f}-{e:6.2f} ({d:.2f}s) clipped {pick['c']} -> {loud(out):.1f} LUFS")
