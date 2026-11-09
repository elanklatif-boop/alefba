# Little-mode English lines from Elan's voice note of 9 Nov 2026 (one take each; "Pick a topic" twice).
import subprocess, re, json, wave, numpy as np, sys
SP = sys.argv[1]  # folder with src.wav (16 kHz mono) and segs.json; clips go to SP/out
OUTD = sys.argv[2] if len(sys.argv) > 2 else SP + "out/"
w = wave.open(SP + "src.wav"); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768
segs = json.load(open(SP + "segs.json"))
# (file name, first segment, last segment) - the segments Whisper heard as each line
LINES = [("en_hi", 0, 1), ("en_pick_game", 2, 2), ("en_pick_topic", 3, 3), ("en_pick_topic_alt", 4, 4), ("en_pick_topic_play", 5, 5),
         ("en_tap_picture_hear", 6, 6), ("en_tap_picture_you_hear", 7, 7), ("en_find_pairs", 8, 8), ("en_tap_letter", 9, 9),
         ("en_trace_gray", 10, 10), ("en_trace_finger", 11, 11), ("en_great_job", 12, 12), ("en_wonderful", 13, 13), ("en_you_did_it", 14, 14)]
def clip(a, b): return int((np.abs(x[int(a * sr):int(b * sr)]) > 0.98).sum())
def loud(p):
    r = subprocess.run(["ffmpeg","-v","info","-i",p,"-af","apad=pad_dur=1,ebur128=framelog=quiet","-f","null","-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])
TARGET = -25.5
for name, a, b in LINES:
    s = max(0, segs[a][0] - 0.10); e = segs[b][1] + 0.18; d = e - s; tmp = OUTD + "tmp.wav"
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{s:.3f}","-to",f"{e:.3f}","-i",SP + "src.wav","-af","highpass=f=70","-ac","1","-ar","24000",tmp], check=True)
    Lu = loud(tmp); out = OUTD + name + ".mp3"
    af = f"volume={TARGET-Lu:.2f}dB,alimiter=limit=0.70:level=disabled,afade=t=in:d=0.02,afade=t=out:st={d-0.06:.3f}:d=0.06"
    subprocess.run(["ffmpeg","-v","error","-y","-i",tmp,"-af",af,"-ac","1","-ar","24000","-b:a","64k",out], check=True)
    print(f"{name:<24} {s:6.2f}-{e:6.2f} ({d:.2f}s) clipped {clip(s, e)} -> {loud(out):.1f} LUFS")
