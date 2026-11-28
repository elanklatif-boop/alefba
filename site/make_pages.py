"""Writes the guide pages and the three game pages (taarof, rally, play) as plain HTML, so every word is in the page
itself, not added later by JavaScript. Run it after changing the text here; build_site.py then copies the pages.
Recordings are only linked when the file exists (web/audio/manifest.json)."""
import html, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = set(json.load(open(os.path.join(HERE, "..", "web", "audio", "manifest.json"))))
E = html.escape
SITE = "https://learnalefba.com/"
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%231c3780'/%3E"
           "%3Ctext x='32' y='46' font-size='40' text-anchor='middle' fill='%23f2b23c' font-family='Tahoma,sans-serif'%3E%D8%A7%3C/text%3E%3C/svg%3E")
PLAY_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4l14 8-14 8z" fill="currentColor"/></svg>'

# every guide, for the "More guides" links (each page lists the others it relates to)
GUIDES = {
    "spoken-vs-written-persian": "Why nân becomes nun: spoken and written Persian",
    "spoken-persian-verbs": "How Persian verbs get shorter when people talk",
    "i-miss-you-in-persian": "How to say I miss you in Persian",
    "thank-you-in-persian": "How to say thank you in Persian",
    "what-is-taarof": "What is taarof?",
    "persian-alphabet": "The Persian alphabet",
    "teach-your-child-persian": "How to teach your child Persian at home",
}


def fa(t):
    return f'<span class="fa" lang="fa">{E(t)}</span>'


def play(file, label, small=False):
    if file not in AUDIO:
        return ""
    return f'<button class="play{" sm" if small else ""}" type="button" data-a="audio/{file}" aria-label="{E(label)}">{PLAY_SVG}</button>'


def item(p, t, m, audio=None, alt=None):
    """one phrase: the Persian, how it's said and what it means, a note, and its recording (alt: a second, smaller
    button inside the note, for the book form)"""
    btn = play(audio[0], audio[1]) if audio else ""
    note = m + (" " + play(alt[0], alt[1], True) if alt and play(alt[0], alt[1], True) else "")
    return f'<li><span class="p" lang="fa" dir="rtl">{E(p)}</span>{btn}<span class="t">{t}</span><span class="m">{note}</span></li>'


def page(slug, title, desc, h1, lead, body, faq=None, og_type="article", related=(), cta=None):
    url = SITE + slug
    ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": title, "url": url, "description": desc, "inLanguage": "en",
           "isPartOf": {"@type": "WebSite", "name": "Alefba", "url": SITE}, "about": {"@type": "Language", "name": "Persian", "alternateName": "Farsi"}}]
    if faq:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
    ld_tags = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>\n' for x in ld)
    more = " · ".join(f'<a href="{s}">{E(GUIDES[s])}</a>' for s in related)
    cta_html = cta if cta is not None else (
        '<div class="box"><p><b>Try it in a lesson.</b> Alefba teaches you to read and speak Persian, with every word shown the way it\'s '
        'written and the way people say it, and recordings to hear both. The alphabet and the first 3 levels are free. A plan opens all 16 levels.</p>'
        '<a class="cta" href="./" data-go>Try a free lesson</a></div>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Alefba">
<meta property="og:image" content="https://learnalefba.com/icons/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Alefba: learn to read and speak Persian">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://learnalefba.com/icons/og-image.png">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="fonts/fonts.css">
<link rel="stylesheet" href="guide.css">
{ld_tags}<script src="guide.js" defer></script>
</head>
<body>
<header>
  <div class="wrap">
    <a class="brand" href="./" data-go><b>Alefba</b><span lang="fa">الفبا</span></a>
    <h1>{E(h1)}</h1>
    <p>{lead}</p>
  </div>
</header>
<main>
  <div class="wrap">
{body}
    {cta_html}
    <section>
      <h2>More guides</h2>
      <p>{more}</p>
    </section>
    <p class="trust">Alefba teaches children, teens and adults to read and speak Persian, the way Iranian families really talk. Made by a student in New York, with recordings by his family. No ads and no tracking cookies.</p>
    <footer><p><a href="./" data-go>Alefba</a> · <a href="learn-persian">Persian for kids</a> · <a href="learn-persian-adults">Persian for adults</a> · <a href="parents">For parents</a> · <a href="teachers">For teachers</a> · <a href="about">Who made Alefba</a></p></footer>
  </div>
</main>
</body>
</html>
"""


def write(slug, text):
    open(os.path.join(HERE, slug + ".html"), "w", encoding="utf-8").write(text)


# ---------------------------------------------------------------- guide 1: â before n or m becomes u
PAIRS = [  # written, said, written Finglish, said Finglish, meaning, book recording, said recording
    ("نان", "نون", "nân", "nun", "bread", "word_naan.mp3", "said_nun.mp3"),
    ("خانه", "خونه", "khâne", "khune", "house, home", "word_khaane.mp3", "said_khune.mp3"),
    ("باران", "بارون", "bârân", "bârun", "rain", "word_baaraan.mp3", "said_baarun.mp3"),
    ("آسمان", "آسمون", "âsemân", "âsemun", "sky", "word_aasemaan.mp3", "said_aasemun.mp3"),
    ("دندان", "دندون", "dandân", "dandun", "tooth", "word_dandaan.mp3", "said_dandun.mp3"),
    ("زمستان", "زمستون", "zemestân", "zemestun", "winter", "word_zemestaan.mp3", "said_zemestun.mp3"),
    ("تابستان", "تابستون", "tâbestân", "tâbestun", "summer", "word_taabestaan.mp3", "said_taabestun.mp3"),
    ("ارزان", "ارزون", "arzân", "arzun", "cheap", "word_arzaan.mp3", "said_arzun.mp3"),
    ("گران", "گرون", "gerân", "gerun", "expensive", "word_geraan.mp3", "said_gerun.mp3"),
    ("هندوانه", "هندونه", "hendevâne", "hendune", "watermelon", "word_hendevaane.mp3", "said_hendune.mp3"),
    ("تهران", "تهرون", "tehrân", "tehrun", "Tehran", "word_tehraan.mp3", "said_Tehrun.mp3"),
]
MORE = [
    ("آن", "اون", "ân", "un", "that", None, "said_un.mp3"),
    ("آنجا", "اونجا", "ânjâ", "unjâ", "there", None, "said_unjaa.mp3"),
    ("آمدن", "اومدن", "âmadan", "umadan", "to come", None, "said_umadan.mp3"),
    ("خواندن", "خوندن", "khândan", "khundan", "to read, to sing", None, "said_khundan.mp3"),
]


def pair_items(rows):
    return "".join(item(s, f"{E(st)}: {E(en)}", f"In books: {fa(w)} ({E(wt)})", (sa, f"Hear {st}"), (wa, f"Hear the book form, {wt}") if wa else None)
                   for w, s, wt, st, en, wa, sa in rows)


g1_faq = [
    ("Why do Iranians say nun instead of nân?", "In everyday Persian, especially the Persian of Tehran, a long â followed by n or m is usually said as u. So nân (bread) is said nun, and khâne (house) is said khune. The spelling stays the same: نان is still written نان."),
    ("Does every â before n or m become u?", "No. It happens in common everyday words, but not in all of them. Salâm (hello) and nâm (name) never change, and formal or less common words usually keep their â."),
    ("Should I learn the written or the spoken form?", "Both. Learn to read the written form, because that's how words are spelled in books, on signs and in the news. Say the spoken form in conversation. Saying nân isn't wrong, but in everyday talk it sounds like reading aloud from a book."),
    ("Is this only in Tehran?", "The u sound is typical of Tehran and of the everyday Persian you hear in Iranian films, series and most Iranian families abroad. Other cities have their own accents. Dari, the Persian of Afghanistan, keeps the â, so nân stays nân, and in Tajik it becomes non."),
]
g1 = f"""    <div class="short"><p>In everyday Persian, a long <b>â</b> followed by <b>n</b> or <b>m</b> is usually said <b>u</b>. Books write <b>nân</b> ({fa("نان")}, bread), but people say <b>nun</b> ({fa("نون")}). <b>Khâne</b> (house) becomes <b>khune</b>, and <b>bârân</b> (rain) becomes <b>bârun</b>. The spelling doesn't change: only the sound does.</p></div>
    <section><h2>Why do Iranians say nun instead of nân?</h2><p>{E(g1_faq[0][1])}</p><p>It's one of the first things that surprises people who learned Persian from a textbook, and one of the first things heritage learners notice: the word they hear at home isn't the word in the book. Both are right. They're the written form and the spoken form of the same word.</p></section>
    <section><h2>Everyday words where â becomes u</h2><p class="muted">The big word is how people say it. Tap ▶ to hear it, and the small ▶ to hear the book form.</p><ul class="say">{pair_items(PAIRS)}</ul>
    <p>It happens in short everyday words too:</p><ul class="say">{pair_items(MORE)}</ul>
    <p class="muted">In text messages and chats, people often spell the spoken form the way it sounds, like {fa("نون")} and {fa("خونه")}. In books, newspapers and anything formal, it's always the written form.</p></section>
    <section><h2>Does every â before n or m become u?</h2><p>No. It happens in common everyday words, but not in all of them. {fa("سلام")} <b>salâm</b> (hello) never becomes “salum”, and {fa("نام")} <b>nâm</b> (name) stays nâm. Formal words, religious words and words you mostly meet in writing usually keep their â.</p><p>There's no rule that tells you which words change, so the best way to learn them is to hear them. A good rule of thumb: the more everyday the word, the more likely it is to change.</p></section>
    <section><h2>Should I learn the written or the spoken form?</h2><p>Both. Learn to read the written form, because that's how words are spelled in books, on signs and in the news. Say the spoken form when you talk. Saying nân isn't wrong, but in everyday conversation it sounds like reading aloud from a book, a bit like saying “I do not know” instead of “I don't know”.</p><p>You'll also hear the written forms out loud: in poetry, on the news, in speeches and in songs.</p></section>
    <section><h2>Is this only in Tehran?</h2><p>{E(g1_faq[3][1])}</p></section>
    <section><h2>Other ways spoken Persian is different</h2><p>The â-to-u change is only one difference. Verbs get shorter too: <b>mikhâham</b> (I want) is said <b>mikhâm</b>, and <b>khub ast</b> (it's good) is said <b>khube</b>. See <a href="spoken-persian-verbs">how Persian verbs get shorter when people talk</a>.</p></section>
    <section><h2>Where to hear more everyday Persian</h2><p>The best way to pick up spoken forms is to listen to a lot of them. Once you can follow simple sentences, <a href="https://thefarsipod.com" rel="noopener">The Farsi Pod</a> has short podcasts in everyday colloquial Persian, each with a written guide to follow along.</p></section>
"""
write("spoken-vs-written-persian", page(
    "spoken-vs-written-persian",
    "Spoken vs Written Persian: Why nân Becomes nun | Alefba",
    "Books say nân and khâne, but Iranians say nun and khune. Why the â before n or m turns into u in everyday Persian, which words change, which don't, and which form to learn. With recordings.",
    "Why nân becomes nun: spoken and written Persian",
    "Books say nân, khâne and bârân. Families say nun, khune and bârun. Here's what's going on, which words change, and which form to learn.",
    g1, g1_faq, related=("spoken-persian-verbs", "i-miss-you-in-persian", "thank-you-in-persian", "persian-alphabet")))

# ---------------------------------------------------------------- guide 2: shorter verbs
VERBS = [  # written, said, written Finglish, said Finglish, meaning, book recording, said recording
    ("می‌خواهم", "می‌خوام", "mikhâham", "mikhâm", "I want", "book_mikhaaham.mp3", "said_mikhaam.mp3"),
    ("می‌روم", "می‌رم", "miravam", "miram", "I go", None, "said_miram.mp3"),
    ("می‌گویم", "می‌گم", "miguyam", "migam", "I say", None, "said_migam.mp3"),
    ("می‌دهم", "می‌دم", "midaham", "midam", "I give", None, "said_midam.mp3"),
    ("می‌توانم", "می‌تونم", "mitavânam", "mitunam", "I can", "book_mitavaanam.mp3", "said_mitunam.mp3"),
    ("نمی‌دانم", "نمی‌دونم", "nemidânam", "nemidunam", "I don't know", "book_nemidaanam.mp3", "said_nemidunam.mp3"),
]
HESHE = [
    ("می‌کند", "می‌کنه", "mikonad", "mikone", "he or she does", None, "said_mikone.mp3"),
    ("می‌خورد", "می‌خوره", "mikhorad", "mikhore", "he or she eats", None, "said_mikhore.mp3"),
    ("می‌رود", "می‌ره", "miravad", "mire", "he or she goes", None, "said_mire.mp3"),
    ("می‌آید", "میاد", "miâyad", "miyâd", "he or she comes", None, "said_miyaad.mp3"),
    ("می‌شود", "می‌شه", "mishavad", "mishe", "it becomes, it's possible", None, "said_mishe.mp3"),
]
AST = [
    ("خوب است", "خوبه", "khub ast", "khube", "it's good", None, "said_khube.mp3"),
    ("سرد است", "سرده", "sard ast", "sarde", "it's cold", None, "said_sarde.mp3"),
    ("بزرگ است", "بزرگه", "bozorg ast", "bozorge", "it's big", None, "said_bozorge.mp3"),
]
g2_faq = [
    ("Why does spoken Persian sound so different from the book?", "Many everyday verbs are shortened when people talk. Mikhâham (I want) is said mikhâm, miravam (I go) is said miram, and miguyam (I say) is said migam. The endings change too: mikonad (he or she does) is said mikone."),
    ("What happens to ast (is) in spoken Persian?", "After a word, ast usually shrinks to -e: khub ast (it's good) is said khube, and sard ast (it's cold) is said sarde."),
    ("What is ro in spoken Persian?", "It's the spoken form of râ, the little word that marks the object of a sentence. Ketâb râ bedeh (give the book) is said ketâbo bede: after a consonant it becomes -o, and after a vowel -ro."),
    ("Should I learn the long or the short verbs?", "Both. Use the short forms when you talk, and learn to recognise the long ones, because that's how they're written in books, signs, the news and subtitles."),
]
g2 = f"""    <div class="short"><p>When people talk, many Persian verbs get shorter. <b>Mikhâham</b> (I want) is said <b>mikhâm</b>, <b>miravam</b> (I go) is said <b>miram</b>, and <b>miguyam</b> (I say) is said <b>migam</b>. The written forms are still how they're spelled. The short forms are how everyone talks.</p></div>
    <section><h2>Why does spoken Persian sound so different from the book?</h2><p>Much of the difference is in the verbs. Long written forms lose a syllable, or their ending changes, so a sentence like {fa("نمی‌دانم کجا می‌روم")} <b>nemidânam kojâ miravam</b> (I don't know where I'm going) comes out as {fa("نمی‌دونم کجا می‌رم")} <b>nemidunam kojâ miram</b>. If you only learn the long forms, you'll understand the news but family conversations will feel fast.</p></section>
    <section><h2>“I” verbs: the most common short forms</h2><p class="muted">The big word is how people say it. Tap ▶ to hear it, and the small ▶ to hear the book form where there is one.</p><ul class="say">{pair_items(VERBS)}</ul><p>Some verbs don't change much, like {fa("می‌کنم")} <b>mikonam</b> (I do) and {fa("می‌خورم")} <b>mikhoram</b> (I eat), so you can use them as they are.</p></section>
    <section><h2>“He” and “she” verbs: -ad becomes -e</h2><p>Persian uses the same verb for he and she. In writing it ends in <b>-ad</b>, and when people talk it ends in <b>-e</b>:</p><ul class="say">{pair_items(HESHE)}</ul></section>
    <section><h2>What happens to ast (is) in spoken Persian?</h2><p>{E(g2_faq[1][1])}</p><ul class="say">{pair_items(AST)}</ul></section>
    <section><h2>What is ro in spoken Persian?</h2><p>The little word {fa("را")} <b>râ</b> marks the object of a sentence (the thing something is done to). When people talk, it becomes <b>-o</b> after a consonant and <b>-ro</b> after a vowel:</p><ul class="say">{item("کتابو بده", "ketâbo bede: give (me) the book", f"In books: {fa('کتاب را بده')} (ketâb râ bedeh)")}{item("اینو ببین", "ino bebin: look at this", f"In books: {fa('این را ببین')} (in râ bebin)")}{item("چایی رو بیار", "châyi ro biyâr: bring the tea", f"In books: {fa('چای را بیاور')} (chây râ biyâvar)")}</ul></section>
    <section><h2>Should I learn the long or the short verbs?</h2><p>{E(g2_faq[3][1])} The vowels change in the same way as in nân and nun, which is why mitavânam becomes mitunam: see <a href="spoken-vs-written-persian">why nân becomes nun</a>.</p></section>
"""
write("spoken-persian-verbs", page(
    "spoken-persian-verbs",
    "Spoken Persian Verbs: How mikhâham Becomes mikhâm | Alefba",
    "Why Persian verbs sound shorter in conversation: mikhâham becomes mikhâm, miravam becomes miram, mikonad becomes mikone, khub ast becomes khube, and râ becomes ro. With recordings of both forms.",
    "How Persian verbs get shorter when people talk",
    "Mikhâham becomes mikhâm, miravam becomes miram, and khub ast becomes khube. The short forms you'll hear in every Iranian home, and the book forms they come from.",
    g2, g2_faq, related=("spoken-vs-written-persian", "i-miss-you-in-persian", "what-is-taarof", "teach-your-child-persian")))

# ---------------------------------------------------------------- guide 3: I miss you
g3_faq = [
    ("How do you say I miss you in Persian?", "Say delam barât tang shode (دلم برات تنگ شده). Literally it means “my heart has become tight for you.” In writing it's delam barâye to tang shode ast."),
    ("How do you say I miss you to more than one person, or politely?", "Use barâtun instead of barât: delam barâtun tang shode. It's how you'd say it to your grandparents, to a whole family, or to someone you speak to politely."),
    ("What does jât khâli mean?", "Jât khâli means “your place was empty.” People say it when you missed something good, like a family dinner or a trip: we missed you, we wish you'd been there."),
    ("How do you say I miss Iran in Persian?", "Delam barâye Irân tang shode. The same words work for a place or a thing: delam barâye khune tang shode means I miss home."),
]
g3 = f"""    <div class="short"><p>To say I miss you in Persian, say <b>delam barât tang shode</b> ({fa("دلم برات تنگ شده")}). Literally it means “my heart has become tight for you.” To say it politely, or to more than one person, say <b>delam barâtun tang shode</b> ({fa("دلم براتون تنگ شده")}).</p></div>
    <section><h2>How do you say I miss you in Persian?</h2><p>{E(g3_faq[0][1])}</p><p>Persian talks about missing someone with the heart: {fa("دل")} <b>del</b> is the heart, and {fa("تنگ")} <b>tang</b> means tight or narrow. Your heart gets tight when someone you love is far away.</p>
    <ul class="say">{item("دلم برات تنگ شده", "delam barât tang shode: I miss you", "To one person you're close to: a parent, a friend, a cousin.")}{item("دلم براتون تنگ شده", "delam barâtun tang shode: I miss you (politely, or all of you)", "To grandparents, to a whole family, or to someone you'd call shomâ.")}{item("خیلی دلم برات تنگ شده", "kheyli delam barât tang shode: I miss you so much", "Kheyli means very.")}{item("دلم برات یه ذره شده", "delam barât ye zarre shode: I miss you terribly", "Literally “my heart has shrunk to a tiny speck for you.” Warm and a little dramatic, for family and close friends.")}</ul></section>
    <section><h2>Spoken and written</h2><p>These are the everyday forms. In writing, the same sentence is {fa("دلم برای تو تنگ شده است")} <b>delam barâye to tang shode ast</b>: <b>barât</b> is the spoken form of barâye to (for you), and <b>barâtun</b> of barâye shomâ. The <b>ast</b> at the end is dropped when people talk, the same way <a href="spoken-persian-verbs">many verbs get shorter</a>.</p></section>
    <section><h2>What does jât khâli mean?</h2><p>{E(g3_faq[2][1])}</p><ul class="say">{item("جات خالی", "jât khâli: we missed you (your place was empty)", "When you tell someone about something good they missed: a party, a meal, a trip.")}{item("جاتون خالی", "jâtun khâli: the polite form", "To someone older, or to several people.")}</ul><p>It's a kind thing to say, so you'll often hear it with food: if someone shows you a photo of a big family dinner and says “jât khâli”, they're telling you they thought of you.</p></section>
    <section><h2>How do you say I miss home, or I miss Iran?</h2><p>{E(g3_faq[3][1])}</p><ul class="say">{item("دلم برای خونه تنگ شده", "delam barâye khune tang shode: I miss home", "Khune is the spoken form of khâne (house, home).")}{item("دلم برای ایران تنگ شده", "delam barâye Irân tang shode: I miss Iran", "You'll hear this one a lot from grandparents.")}{item("دلم تنگ شده", "delam tang shode: I miss (them, it, home)", "On its own it means you're missing someone or somewhere, and it can also mean feeling a bit homesick or low.")}</ul></section>
    <section><h2>How do you reply?</h2><p>The simplest reply is <b>manam</b> ({fa("منم")}, me too), or the full <b>manam delam barât tang shode</b>. To be warmer, add <b>azizam</b> (my dear): manam, azizam.</p></section>
"""
write("i-miss-you-in-persian", page(
    "i-miss-you-in-persian",
    "How to Say I Miss You in Persian (Farsi) | Alefba",
    "Delam barât tang shode means I miss you in Persian. The polite form, how to say I miss you so much, what jât khâli means, how to say I miss home or I miss Iran, and how to reply.",
    "How to say I miss you in Persian",
    "Delam barât tang shode: what it means, the polite form, jât khâli, and how to say you miss home.",
    g3, g3_faq, related=("thank-you-in-persian", "spoken-vs-written-persian", "what-is-taarof", "teach-your-child-persian")))


# ---------------------------------------------------------------- the three game pages
def game_page(slug, title, desc, h1, lead, start_href, start_label, body, related, og_type="website"):
    start = (f'    <div class="box start"><a class="cta" href="{start_href}" data-go>{E(start_label)}</a>'
             '<p class="muted">Opens in your browser. No sign-up, nothing to download.</p></div>\n')
    return page(slug, title, desc, h1, lead, start + body, None, og_type=og_type, related=related, cta="")


SCENES = [("🫖", "Tea at Auntie's", "Khale Shirin offers you tea."), ("🍲", "Dinner at Grandma's", "You've had two plates of ghormeh sabzi, and Grandma offers more."),
          ("🚪", "Who goes first?", "You and your neighbour reach the door at the same time."), ("🍦", "Ice cream with Uncle", "Amu Reza takes you to buy ice cream."),
          ("🚕", "The taxi in Tehran", "You ask the driver how much the ride is."), ("🏠", "Stay for dinner!", "It's getting late at your friend's house.")]
taarof_body = f"""    <section><h2>What happens in the taarof test?</h2><p>Six everyday scenes, about two minutes in all. In each one someone offers you something, or insists, and you pick what to say from three answers. After each answer you see the Persian, how to say it, what it means, and why it's the right (or the wrong) thing to say.</p>
    <ul class="say">{"".join(f'<li><span class="t">{e} {E(t)}</span><span class="m">{E(d)}</span></li>' for e, t, d in SCENES)}</ul></section>
    <section><h2>What is taarof?</h2><p>Taarof ({fa("تعارف")}) is the Persian etiquette of offering, refusing and insisting. A host offers, a guest politely says no, the host insists, and only then does the guest accept. A taxi driver may say <b>ghâbel nadâre</b> (it's nothing) when you ask the price, and you're still expected to pay. Read the full guide: <a href="what-is-taarof">what is taarof?</a></p></section>
    <section><h2>Who is it for?</h2><p>Anyone who's ever been offered tea three times at an Iranian home. It's made for kids, teens and adults learning Persian, for heritage learners who know the words but not the rules, and for friends and partners of Iranian families. Teachers can put it on a classroom screen and let the class vote on each answer.</p></section>
    <section><h2>After the test</h2><p>Try the <a href="rally">taarof rally</a>, a fast game where Auntie keeps offering tea and you keep the polite replies going. Or learn the phrases themselves in <a href="thank-you-in-persian">how to say thank you in Persian</a>.</p>
    <div class="box"><p><b>Learn the Persian behind the manners.</b> Alefba teaches you to read and speak Persian the way families really talk. The Taarof pack is free, and so are the alphabet and the first 3 levels. A plan opens all 16 levels.</p><a class="cta" href="./" data-go>Try a free lesson</a></div></section>
"""
write("taarof", game_page(
    "taarof", "The Taarof Test: A Free Game About Persian Politeness | Alefba",
    "Auntie offers you tea. What do you say? Six everyday scenes of taarof, the Persian way of being polite, with the Persian words and why. Free, no sign-up, about 2 minutes.",
    "Can you pass the taarof test?",
    "Auntie offers you tea. What do you say? Six everyday scenes of Persian politeness, in about two minutes.",
    "./#taarof", "Start the taarof test", taarof_body, ("what-is-taarof", "thank-you-in-persian", "i-miss-you-in-persian")))

POLITE = [("زحمت نکشید", "zahmat nakeshid", "Don't trouble yourself!", "word_zahmat_nakeshid.mp3"), ("شرمنده", "sharmande", "You're too kind!", "word_sharmande.mp3"),
          ("مزاحم نمی‌شم", "mozâhem nemisham", "I won't impose!", "said_mozaahem_nemisham.mp3"), ("خواهش می‌کنم", "khâhesh mikonam", "Oh, please!", "word_khaahesh_mikonam.mp3"),
          ("دستت درد نکنه", "dastet dard nakone", "Thank you so much!", "word_dastet_dard_nakone.mp3"), ("قربونت برم", "ghorbunet beram", "Thank you, dear!", "word_ghorbunet_beram.mp3")]
rally_body = f"""    <section><h2>How does the taarof rally work?</h2><p>Auntie keeps offering. Each time, a cup of tea slides toward you, and before it reaches you, you tap a polite reply. Never the same one twice in a row, and never a blunt one, or the tea spills. It gets faster each time. How long can you keep it going?</p></section>
    <section><h2>Your polite replies</h2><p>These are the six things you can say back. They're real phrases you'll hear at any Iranian home. Tap ▶ to hear each one.</p>
    <ul class="say">{"".join(item(p, f"{E(t)}: {E(en)}", "", (au, f"Hear {t}")) for p, t, en, au in POLITE)}</ul>
    <p>Auntie's side of the rally is just as useful: <b>befarmâ</b> (here, have some), <b>taârof nakon</b> (don't be shy), <b>ghâbel nadâre</b> (it's nothing) and <b>nush-e jân</b> (enjoy).</p></section>
    <section><h2>New to taarof?</h2><p>Start with the <a href="taarof">taarof test</a>, six short scenes that explain each answer, or read <a href="what-is-taarof">what taarof is</a>.</p>
    <div class="box"><p><b>Learn the words for real.</b> Alefba teaches you to read and speak Persian the way families really talk. The Taarof pack is free, and so are the alphabet and the first 3 levels. A plan opens all 16 levels.</p><a class="cta" href="./" data-go>Try a free lesson</a></div></section>
"""
write("rally", game_page(
    "rally", "Taarof Rally: How Long Can You Keep the Persian Politeness Going? | Alefba",
    "Auntie keeps offering tea. You keep saying something polite in Persian, never the same thing twice, before the cup reaches you. A free, fast game about taarof, with six real Persian phrases.",
    "How long can you keep the taarof going?",
    "Auntie keeps offering tea, and you keep saying something polite. A fast, free game with six real Persian phrases.",
    "./#rally", "Play the taarof rally", rally_body, ("what-is-taarof", "thank-you-in-persian", "spoken-persian-verbs")))

play_body = """    <section><h2>Two games for a Persian class</h2><p>Put Alefba on the classroom screen and pick a game, then the words to play with.</p>
    <ul class="say"><li><span class="t">🎈 Balloons</span><span class="m">Alefba says a Persian word, and the class shouts which balloon to pop. Play it with pictures for beginners, or with the words written in Persian for readers.</span></li>
    <li><span class="t">🎉 Bingo</span><span class="m">Print a card for every child, each one different, with pictures or with words in Persian. The screen calls a word out loud, then shows it a few seconds later so the class can check. The first full line wins.</span></li></ul></section>
    <section><h2>Which words can we play with?</h2><p>The words from each level of Alefba, like family, food, colours and animals, and the seasonal packs: the Yalda words in December, with watermelon, pomegranate and the fâl of Hafez. The first 3 levels and the seasonal packs are free to play. A plan opens all 16 levels.</p></section>
    <section><h2>How to run it</h2><p>Open learnalefba.com/play on the screen the class can see, choose Balloons or Bingo, then choose Pictures (easier) or Read it (harder), and a level. For bingo, print the cards first. Each set of printed cards has a game code, so you can open the same game again next week.</p><p>Getting ready for Yalda? The <a href="yalda">Yalda page</a> has a Yalda bingo, a balloon game and a short story, all set up for a class.</p></section>
    <section><h2>More for teachers</h2><p>Teacher mode is free: make a class, share one link, assign lessons and see who's practising. There are also printable tracing sheets for every letter. See <a href="teachers">Alefba for Persian teachers</a>.</p>
    <div class="box"><p><b>Try a lesson yourself first.</b> The alphabet and the first 3 levels are free. A plan opens all 16 levels.</p><a class="cta" href="./" data-go>Try a free lesson</a></div></section>
"""
write("play", game_page(
    "play", "Persian Bingo and Balloon Game for the Classroom | Alefba",
    "Two Persian games for the classroom screen: a bingo with printed cards (pictures or words in Persian) where Alefba calls the words, and a balloon game where the class shouts which balloon to pop.",
    "Persian bingo and a balloon game for your class",
    "Two games for the classroom screen: Alefba says the Persian words, and the whole class plays.",
    "./#play", "Open the classroom games", play_body, ("teach-your-child-persian", "persian-alphabet", "what-is-taarof")))
print("pages written")
