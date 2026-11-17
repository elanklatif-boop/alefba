# The taarof test's lines (the hosts and friends who make you an offer), from the voice note of 17 Nov 2026.
# Each was said twice; the take with no clipping (or the least) is used, checked by transcribing every part.
# "ghâbel nadâre!" was already recorded; "telefon" isn't in this note. Cut at the recording's own rate (full.wav).
import subprocess, re, wave, numpy as np, sys
SP = sys.argv[1]; OUTD = SP + "out/"   # SP holds full.wav (the note, mono)
w = wave.open(SP + "full.wav"); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768
PICKS = [("line_a8643a4f", 4.38, 6.54),    # chây mikhori azizam?
         ("line_85556ff0", 7.86, 11.02),   # zahmati nist! taârof nakon.
         ("line_18befb83", 16.14, 17.90),  # ye kam dige bokhor!
         ("line_b6ff5266", 21.60, 25.40),  # taârof nakon! to ke chizi nakhordi!
         ("line_11ccd3b9", 33.08, 34.22),  # befarmâyid!
         ("line_e3859ba5", 38.82, 41.70),  # na, na, shomâ befarmâyid!
         ("line_3fae522b", 45.90, 48.86),  # bastanit ro man hesâb mikonam!
         ("line_7ceaa0ee", 53.66, 57.12),  # ghâbeli nadâre! taârof nakon.
         ("line_0b4aa404", 60.52, 63.14),  # na, ghâbel nadâre!
         ("line_2a8ff2c3", 65.80, 67.20),  # shâm bemun!
         ("line_f5340af2", 67.98, 70.94)]  # che mozâhemati? khoshhâl mishim!
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
    print(f"{name:<16} {s:6.2f}-{e:6.2f} ({d:.2f}s) clipped {c} -> {loud(out):.1f} LUFS")
