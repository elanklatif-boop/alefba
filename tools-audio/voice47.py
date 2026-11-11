# The computer-voice files from Colab: trim the silence at each end, bring them to the loudness of the family's
# recordings, and save as 24 kHz mono mp3 like the rest.
import subprocess, sys, os, re, json, numpy as np
IN, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True); SR = 24000; TARGET = -25.5
def dec(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)
def loud(p):
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", p, "-af", "apad=pad_dur=1,ebur128=framelog=quiet", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
rep = []
for f in sorted(os.listdir(IN)):
    x = dec(IN + f); n = len(x); w = int(0.02 * SR)
    e = np.sqrt(np.convolve(x ** 2, np.ones(w) / w, "same")); thr = max(e.max() * 10 ** (-38 / 20), 1e-4)
    idx = np.nonzero(e > thr)[0]
    if not len(idx): rep.append((f, "SILENT")); continue
    a, b = max(0, idx[0] - int(0.08 * SR)), min(n, idx[-1] + int(0.20 * SR)); y = x[a:b]
    tmp = OUT + "tmp.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f64le", "-ar", str(SR), "-ac", "1", "-i", "-", tmp], input=y.tobytes(), check=True)
    L0 = loud(tmp); d = len(y) / SR
    af = f"volume={TARGET - L0:.2f}dB,alimiter=limit=0.70:level=disabled,afade=t=in:d=0.015,afade=t=out:st={d - 0.05:.3f}:d=0.05"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", af, "-ac", "1", "-ar", str(SR), "-b:a", "64k", OUT + f], check=True)
    rep.append((f, round(n / SR, 2), round(d, 2), round(a / SR, 2), round((n - b) / SR, 2), L0))
os.remove(OUT + "tmp.wav"); json.dump(rep, open(OUT + "../report.json", "w"))
