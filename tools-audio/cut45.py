# Days, months and time words from the voice note of 10 Nov 2026 (each said twice; the clearer, unclipped take is used).
import subprocess, re, wave, numpy as np, sys
SP = sys.argv[1]; OUTD = SP + "out/"   # SP holds src.wav (16 kHz mono)
w = wave.open(SP + "src.wav"); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768
PICKS = [("word_shanbe", 4.50, 5.47), ("word_yekshanbe", 7.49, 8.49), ("word_doshanbe", 13.23, 14.39), ("word_seshanbe", 18.59, 19.85),
         ("word_chahaarshanbe", 23.93, 25.57), ("word_panjshanbe", 32.29, 33.68), ("word_jome", 37.31, 38.86), ("word_taabestaan", 40.21, 41.68),
         ("word_farvardin", 45.71, 47.10), ("word_bist", 51.48, 52.30), ("word_si", 56.26, 57.04), ("word_sad", 61.19, 62.55),
         ("word_saaat_chande", 69.51, 71.13), ("word_nim", 72.90, 73.68), ("word_tavallod", 76.74, 77.81),
         ("word_chand_saalete", 83.59, 85.13)]
def clip(a, b): return int((np.abs(x[int(a * sr):int(b * sr)]) > 0.98).sum())
def loud(p):
    r = subprocess.run(["ffmpeg","-v","info","-i",p,"-af","apad=pad_dur=1,ebur128=framelog=quiet","-f","null","-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
TARGET = -25.5
for name, a, b in PICKS:
    s, e = a - 0.10, b + 0.15; d = e - s; c = clip(s, e); tmp = OUTD + "tmp.wav"
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{s:.3f}","-to",f"{e:.3f}","-i",SP + "src.wav","-af","highpass=f=70" + (",adeclip" if c else ""),"-ac","1","-ar","24000",tmp], check=True)
    Lu = loud(tmp); out = OUTD + name + ".mp3"
    af = f"volume={TARGET-Lu:.2f}dB,alimiter=limit=0.70:level=disabled,afade=t=in:d=0.02,afade=t=out:st={d-0.06:.3f}:d=0.06"
    subprocess.run(["ffmpeg","-v","error","-y","-i",tmp,"-af",af,"-ac","1","-ar","24000","-b:a","64k",out], check=True)
    print(f"{name:<26} {s:6.2f}-{e:6.2f} ({d:.2f}s) clipped {c} -> {loud(out):.1f} LUFS")
