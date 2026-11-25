# Alefba: the Yalda fâl couplets, read by the computer voice, in case no one in the family records them.
# Only use this AFTER the family has checked the poems (the PDF), since it reads exactly what's below.
# Open colab.research.google.com, make a new notebook, paste this whole thing into one cell, and run it.
# It zips the files and downloads alefba_yalda.zip. Then attach alefba_yalda.zip in the chat. It takes about a minute.

!pip install -q edge-tts

import asyncio, zipfile
from pathlib import Path
import edge_tts
from google.colab import files

VOICE = "fa-IR-FaridNeural"   # a man's voice, a little slow, like someone reading a fâl to the family
RATE = "-15%"
OUT = Path("alefba_yalda"); OUT.mkdir(exist_ok=True)

# each couplet: the two lines with a pause between them
SOUNDS = [
    ("یوسف گم‌گشته بازآید به کنعان، غم مخور / کلبهٔ احزان شود روزی گلستان، غم مخور", "fal_01.mp3"),
    ("صبح امید که بُد معتکف پردهٔ غیب / گو برون آی که کار شب تار آخر شد", "fal_02.mp3"),
    ("دوش وقت سحر از غصه نجاتم دادند / واندر آن ظلمت شب آب حیاتم دادند", "fal_03.mp3"),
    ("نفس باد صبا مشک‌فشان خواهد شد / عالم پیر دگرباره جوان خواهد شد", "fal_04.mp3"),
    ("ستاره‌ای بدرخشید و ماه مجلس شد / دل رمیدهٔ ما را انیس و مونس شد", "fal_05.mp3"),
    ("سال‌ها دل طلب جام جم از ما می‌کرد / وانچه خود داشت ز بیگانه تمنا می‌کرد", "fal_06.mp3"),
    ("درخت دوستی بنشان که کام دل به بار آرد / نهال دشمنی برکن که رنج بی‌شمار آرد", "fal_07.mp3"),
    ("هر گنج سعادت که خدا داد به حافظ / از یمن دعای شب و ورد سحری بود", "fal_08.mp3"),
    ("فاش می‌گویم و از گفتهٔ خود دلشادم / بندهٔ عشقم و از هر دو جهان آزادم", "fal_09.mp3"),
    ("دلا بسوز که سوز تو کارها بکند / نیاز نیم‌شبی دفع صد بلا بکند", "fal_10.mp3"),
    ("کمتر از ذره نه‌ای، پست مشو، مهر بورز / تا به خلوتگه خورشید رسی چرخ‌زنان", "fal_11.mp3"),
    ("مژده ای دل که مسیحا نفسی می‌آید / که ز انفاس خوشش بوی کسی می‌آید", "fal_12.mp3"),
    ("رسید مژده که ایام غم نخواهد ماند / چنان نماند، چنین نیز هم نخواهد ماند", "fal_13.mp3"),
    ("سحر با باد می‌گفتم حدیث آرزومندی / خطاب آمد که واثق شو به الطاف خداوندی", "fal_14.mp3"),
    ("بر سر آنم که گر ز دست برآید / دست به کاری زنم که غصه سرآید", "fal_15.mp3"),
    ("ز کوی یار می‌آید نسیم باد نوروزی / از این باد ار مدد خواهی، چراغ دل برافروزی", "fal_16.mp3"),
    ("شکرشکن شوند همه طوطیان هند / زین قند پارسی که به بنگاله می‌رود", "fal_17.mp3"),
    ("چو بشنوی سخن اهل دل، مگو که خطاست / سخن‌شناس نه‌ای، جان من، خطا این‌جاست", "fal_18.mp3"),
    ("هرگز نمیرد آن که دلش زنده شد به عشق / ثبت است بر جریدهٔ عالم دوام ما", "fal_19.mp3"),
    ("گفتم غم تو دارم، گفتا غمت سرآید / گفتم که ماه من شو، گفتا اگر برآید", "fal_20.mp3"),
]

async def make(text, name):
    text = text.replace(" / ", "\u060c ... ")
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(OUT / name))

async def main():
    for text, name in SOUNDS:
        await make(text, name)
        print("made", name)

await main()
with zipfile.ZipFile("alefba_yalda.zip", "w") as z:
    for f in sorted(OUT.glob("*.mp3")): z.write(f, f.name)
files.download("alefba_yalda.zip")
