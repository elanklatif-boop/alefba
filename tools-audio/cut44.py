# Polite phrases from Elan's voice note of 4 Nov 2026 (each said twice; the clearer, unclipped take is used).
import subprocess, re, wave, numpy as np, sys
SP = sys.argv[1]; OUTD = SP + "out/"   # SP holds src.wav (16 kHz mono)
w = wave.open(SP + "src.wav"); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768
PICKS = [("word_ghorbunet_beram", 5.47, 7.34), ("word_dastet_dard_nakone", 9.36, 11.51), ("word_khaste_nabaashi", 19.65, 21.59),
         ("word_nushe_jaan", 22.80, 24.05), ("word_taaarof_nakon", 29.02, 30.48)]
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
