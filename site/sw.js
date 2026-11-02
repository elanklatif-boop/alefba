// Alefba's offline helper (a service worker). It keeps the app's own files on the device, so lessons open without
// internet and sounds play instantly after the first time. Talks, sign-in, payments and the parents pages always go
// to the server. VERSION changes with every upload, which clears the old copy of the app.
const VERSION = "__BUILD__";
const SHELL = "alefba-app-" + VERSION, MEDIA = "alefba-media-v1";
const CORE = ["./", "./index.html", "./manifest.webmanifest", "./fonts/fonts.css"];
const SERVER = p => p.startsWith("/api/") || /^\/(parents|adults)(\.html)?$/.test(p);
const LIVE = p => /\/audio\/(manifest|real_voice)\.json$/.test(p); // the list of recordings: always fresh when online
self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith("alefba-app-") && k !== SHELL).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const r = e.request;
  if (r.method !== "GET") return;
  const url = new URL(r.url);
  if (url.origin !== self.location.origin || SERVER(url.pathname)) return;
  if (LIVE(url.pathname)) { e.respondWith(/real_voice\.json$/.test(url.pathname) ? realList(r) : networkFirst(MEDIA, r)); return; }
  if (/^\/(audio|fonts|icons)\//.test(url.pathname)) { e.respondWith(cacheFirst(MEDIA, r)); return; }
  e.respondWith(networkFirst(SHELL, r)); // the app itself: the newest copy when online, the saved one when not
});
async function cacheFirst(name, r) {
  const c = await caches.open(name);
  const hit = await c.match(r, { ignoreSearch: true });
  if (hit) return hit;
  // not on the device: ask the server, not the browser's own cache, which may still hold a recording that was replaced
  let res; try { res = await fetch(new Request(r, { cache: "no-cache" })); } catch (e) { res = await fetch(r); }
  if (res.ok) c.put(r, res.clone()).catch(() => {});
  return res;
}
// A new family recording replaces the computer voice in the same file, so the old copy saved on this device would
// play forever. Every file that's new on the list of real recordings is dropped here and fetched again when it's
// next played. Each time the mark below changes (now .fresh-2, for a recording that was trimmed), all the real
// recordings are fetched again once.
async function realList(r) {
  const c = await caches.open(MEDIA), at = f => new URL("audio/" + f, self.registration.scope).href;
  const mark = at(".fresh-2"), before = await c.match(r, { ignoreSearch: true }), marked = await c.match(mark);
  let res;
  try { res = await fetch(r); } catch (e) { if (before) return before; throw e; }
  if (!res.ok) return res;
  try {
    const now = await res.clone().json(), was = marked && before ? await before.json() : [];
    if (Array.isArray(now)) await Promise.all(now.filter(f => !was.includes(f)).map(f => c.delete(at(f), { ignoreSearch: true })));
    if (!marked) await c.put(mark, new Response("1"));
  } catch (e) {}
  await c.put(r, res.clone()).catch(() => {});
  return res;
}
async function networkFirst(name, r) {
  const c = await caches.open(name);
  try {
    const res = await fetch(r);
    if (res.ok) c.put(r, res.clone()).catch(() => {});
    return res;
  } catch (e) {
    const hit = await c.match(r, { ignoreSearch: true });
    if (hit) return hit;
    if (r.mode === "navigate") { const home = await c.match("./index.html"); if (home) return home; }
    throw e;
  }
}
