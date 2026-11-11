# Taarof phrases from the voice note of 11 Nov 2026 (each said twice; the clearer take is used). taârof nakon, dastet dard nakone,
# ghorbunet beram and cheshm are in it too, but they already had recordings (4 Nov), so those are left as they are.
import subprocess, re, wave, numpy as np, sys
SP = sys.argv[1]; OUTD = SP + "out/"   # SP holds src.wav (16 kHz mono)
w = wave.open(SP + "src.wav"); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768
PICKS = [("word_befarmaa", 1.35, 2.42), ("word_ghaabel_nadaare", 7.61, 9.24), ("word_zahmat_nakeshid", 23.62, 25.63),
         ("word_sharmande", 29.20, 30.60), ("said_mozaahem_nemisham", 31.88, 33.65), ("word_khaahesh_mikonam", 53.11, 54.81)]
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
