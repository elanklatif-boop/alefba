# Alefba (الفبا)

Learn to read, write and speak Persian, for kids, families and adults. Live at **https://learnalefba.com**.

## What's where

| Folder | What it is |
|---|---|
| `web/alefba.html` | The whole app: lessons, words, stories, games, talks, settings. One file. |
| `web/audio/` | Every sound the app plays. `manifest.json` lists them all; `real_voice.json` lists the ones recorded by the family (the rest are a computer voice). |
| `site/` | The website around the app: the server code (`_worker.js`), the offline helper (`sw.js`), the parents, adults and teachers pages, fonts, icons, and `build_site.py`. |
| `recordings/` | The family's original voice recordings, before they were cut into single words. |
| `tools-audio/` | Scripts that find each word in a recording and cut it. |
| `tests/` | Automated checks for the app (`tests/app`, run with Python and Playwright against a local copy of the site) and the server (`tests/server`, run with Node). They were written in a temporary workspace, so file paths at the top of each may need changing. |

## Make the website

```
python3 site/build_site.py
```

This makes the folder `alefba-site/` (not saved in GitHub). Zip what's inside it and upload it to Cloudflare Pages, or drag the folder in.

## Secrets

No keys or passwords are in this repository, and none should ever be added. The Claude, Stripe, Resend, Azure and Turnstile keys live only in Cloudflare (Pages, Settings, Variables and Secrets). If a key is ever pasted anywhere else, make a new one and delete the old one.
