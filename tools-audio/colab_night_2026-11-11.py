# Alefba: the voices for Mehmuni night (27 short lines).
# Same as last time: paste this whole thing into one Colab cell and run it (under a minute),
# then attach the alefba_night.zip it downloads in the chat.

!pip install -q edge-tts

import asyncio, zipfile
from pathlib import Path
import edge_tts
from google.colab import files

VOICES = {"f": "fa-IR-DilaraNeural", "m": "fa-IR-FaridNeural"}
RATE = "-8%"   # a touch slower than normal
OUT = Path("alefba_night")
OUT.mkdir(exist_ok=True)

SOUNDS = [
    ("اول شما!", "line_6b78a509.mp3", "f"),
    ("یه چای که چیزی نیست! جون من!", "line_fd780b8b.mp3", "f"),
    ("نه، مرسی.", "line_8981d06b.mp3", "f"),
    ("نه، مرسی، نمی‌خورم.", "line_4110a57c.mp3", "f"),
    ("آره، مرسی!", "line_5975f13f.mp3", "f"),
    ("باشه، هر جور راحتی.", "line_9dfc34f7.mp3", "f"),
    ("قابل نداره! پیشکش!", "line_32ef3b35.mp3", "f"),
    ("تعارف نمی‌کنم! ببرش.", "line_e5875454.mp3", "f"),
    ("مرسی، صاحبش قابل داره.", "line_dabaeea6.mp3", "f"),
    ("نه، مرسی. همین جا قشنگ‌تره!", "line_335717ea.mp3", "f"),
    ("واقعاً؟ مرسی!", "line_86aad4dc.mp3", "f"),
    ("جون مامان‌بزرگ، یه قاشق!", "line_32585706.mp3", "f"),
    ("دیگه جا ندارم!", "line_5c32421a.mp3", "f"),
    ("نه، مرسی!", "line_8681cbb2.mp3", "f"),
    ("نه، تو بخور! نوش جان!", "line_6b94669e.mp3", "m"),
    ("تعارف نکن، بردار!", "line_aaf1efa5.mp3", "m"),
    ("عمو، شما بفرمایید!", "line_520d9941.mp3", "f"),
    ("نه، شما بخورید!", "line_e90f9e39.mp3", "f"),
    ("نه، مال شما!", "line_059ccb39.mp3", "f"),
    ("ته‌دیگ مال من!", "line_b6daa200.mp3", "f"),
    ("چِشم، مرسی عمو!", "line_b3696904.mp3", "f"),
    ("باشه، پس من می‌خورم!", "line_7fee6f45.mp3", "m"),
    ("کجا؟ تازه سر شبه!", "line_1c8d56c6.mp3", "f"),
    ("چه زحمتی! بمون!", "line_fdf30897.mp3", "f"),
    ("نه دیگه، خیلی زحمت دادم.", "line_215a07b9.mp3", "f"),
    ("مرسی، خیلی خوش گذشت. خداحافظ!", "line_25b3808f.mp3", "f"),
    ("باشه، می‌مونم!", "line_adeada77.mp3", "f"),
]

async def make(sem, text, name, who):
    path = OUT / name
    if path.exists() and path.stat().st_size > 0:
        return True
    async with sem:
        for attempt in range(4):
            try:
                await edge_tts.Communicate(text, VOICES[who], rate=RATE).save(str(path))
                if path.stat().st_size > 0:
                    return True
            except Exception as e:
                await asyncio.sleep(2 + attempt * 3)
    path.unlink(missing_ok=True)
    print("could not make", name, text)
    return False

async def main():
    sem = asyncio.Semaphore(4)
    results = await asyncio.gather(*(make(sem, t, n, w) for t, n, w in SOUNDS))
    made = sum(1 for r in results if r)
    print(f"made {made} of {len(SOUNDS)} files")
    if made < len(SOUNDS):
        print("Some are missing: run the cell once more and it makes only the ones left.")
    with zipfile.ZipFile("alefba_night.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.glob("*.mp3")):
            if p.stat().st_size > 0:
                z.write(p, p.name)
    files.download("alefba_night.zip")

await main()
