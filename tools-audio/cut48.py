# Level 9 words (home and school) from the voice note of 12 Nov 2026, each said twice; the take with no clipping
# (or the least) is used. Only telefon is not in it. Cut from the recording at its own sample rate (full.wav).
import subprocess, re, wave, numpy as np, sys
SP = sys.argv[1]; OUTD = SP + "out/"   # SP holds src.wav (16 kHz mono)
w = wave.open(SP + "full.wav"); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768
PICKS = [("word_kif", 3.47, 4.33), ("word_medaad", 7.90, 8.99), ("word_daftar", 10.11, 11.14), ("word_moallem", 14.79, 16.03),
         ("word_otaagh", 22.19, 23.22), ("word_dar", 24.54, 25.54), ("word_panjere", 28.70, 29.75), ("word_miz", 32.99, 34.00),
         ("word_sandali", 37.27, 38.50), ("word_kelaas", 44.30, 45.51), ("word_tup", 46.88, 47.50), ("word_arusak", 51.12, 52.19),
         ("word_maashin", 55.92, 57.15), ("word_docharkhe", 60.74, 61.85), ("word_takht", 67.42, 68.18)]
def clip(a, b): return int((np.abs(x[int(a * sr):int(b * sr)]) > 0.98).sum())
def loud(p):
    r = subprocess.run(["ffmpeg","-v","info","-i",p,"-af","apad=pad_dur=1,ebur128=framelog=quiet","-f","null","-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
TARGET = -25.5
for name, a, b in PICKS:
    s, e = a - 0.10, b + 0.15; d = e - s; c = clip(s, e); tmp = OUTD + "tmp.wav"
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{s:.3f}","-to",f"{e:.3f}","-i",SP + "full.wav","-af","highpass=f=70" + (",adeclip" if c else ""),"-ac","1","-ar","24000",tmp], check=True)
    Lu = loud(tmp); out = OUTD + name + ".mp3"
    af = f"volume={TARGET-Lu:.2f}dB,alimiter=limit=0.70:level=disabled,afade=t=in:d=0.02,afade=t=out:st={d-0.06:.3f}:d=0.06"
    subprocess.run(["ffmpeg","-v","error","-y","-i",tmp,"-af",af,"-ac","1","-ar","24000","-b:a","64k",out], check=True)
    print(f"{name:<26} {s:6.2f}-{e:6.2f} ({d:.2f}s) clipped {c} -> {loud(out):.1f} LUFS")
