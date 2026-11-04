// The next-day email: asking for it books one email about a day later, each finished lesson moves it, the link in it
// stops them (a browser only sees a button; the mail app's one-click stop works), and limits keep it from being misused.
import { D1 } from "./d1shim.mjs";
import { state, resendServer } from "./mocks.mjs";
const SITE = process.env.SITE || "/home/claude/alefba/alefba-site";
const worker = (await import(SITE + "/_worker.js?v=" + Date.now())).default;
const servers = [resendServer(39789)];
const db = new D1(), ASSETS = { fetch: async () => new Response("asset") };
const FULL = { RESEND_API_KEY: "re_" + "test_0123456789abcdefghij", RESEND_BASE_URL: "http://127.0.0.1:39789", EMAIL_FROM: "hello@alefba.example", DB: db, ASSETS };
const env = (x = {}) => ({ ...FULL, ...x });
let pass = 0, fail = 0;
const check = (n, ok, x = "") => { ok ? pass++ : fail++; console.log((ok ? "PASS " : "FAIL ") + n + (ok ? "" : " " + JSON.stringify(x))); };
let ip = 0;
const call = async (e, path, { method = "POST", body, origin = "https://learnalefba.com", raw, type, sameIp } = {}) => {
  const h = new Headers({ "CF-Connecting-IP": sameIp || "10.9.0." + (++ip) });
  if (body !== undefined) h.set("content-type", "application/json");
  if (type) h.set("content-type", type);
  if (method === "POST" && origin) h.set("Origin", origin);
  const r = await worker.fetch(new Request("https://learnalefba.com" + path, { method, headers: h, body: raw !== undefined ? raw : body === undefined ? undefined : JSON.stringify(body) }), e, { waitUntil: p => p });
  const text = await r.text(); let json = null; try { json = JSON.parse(text); } catch (er) {}
  return { status: r.status, text, json };
};
const next = { t: "Meet the letters", fa: "ج چ ح خ<script>" };

let r = await call(env({ RESEND_API_KEY: "" }), "/api/nudge/start", { body: { email: "a@b.co", agree: true, next } });
check("without Resend it says it's not set up", r.status === 503, r);
r = await call(env(), "/api/nudge/start", { body: { email: "not an email", agree: true, next } });
check("a bad address is refused", r.status === 400 && r.json.error === "bad_email", r);
r = await call(env(), "/api/nudge/start", { body: { email: "mum@example.com", next } });
check("it needs the grown-up's yes", r.status === 400 && r.json.error === "agree", r);
r = await call(env(), "/api/nudge/start", { body: { email: "mum@example.com", agree: true, next }, origin: "https://evil.example" });
check("another website can't ask", r.status === 403, r.status);

const t0 = Date.now();
r = await call(env(), "/api/nudge/start", { body: { email: "Mum@Example.com", agree: true, next } });
const tok = r.json && r.json.token;
check("asking for it gives the device a token", r.status === 200 && /^[A-Za-z0-9_-]{40,}$/.test(tok || ""), r);
let m = state.emails[state.emails.length - 1];
const hrs = (Date.parse(m.scheduled_at) - t0) / 3600e3;
check(`one email is booked for about a day later (${hrs.toFixed(2)} h)`, hrs > 22.9 && hrs < 23.1 && m.to[0] === "mum@example.com", m);
check("it comes from Alefba, with replies going to hello@", m.from === "Alefba <hello@alefba.example>" && m.reply_to === "hello@alefba.example", m);
check("it says what's next, without anything unsafe", m.text.includes("Meet the letters: ج چ ح خ") && !m.html.includes("<script") && m.html.includes("?ref=email"), m.text);
check("it has a one-click stop for the mail app", m.headers["List-Unsubscribe"] === `<https://learnalefba.com/api/nudge/stop?t=${tok}>` && m.headers["List-Unsubscribe-Post"] === "List-Unsubscribe=One-Click", m.headers);
check("and a stop link in the email itself", m.text.includes("/api/nudge/stop?t=" + tok) && m.html.includes("Stop these emails"), "");
const stored = db.q("SELECT * FROM nudges");
check("only the address, a scrambled token and the booking are kept", stored.length === 1 && !JSON.stringify(stored).includes(tok) && !JSON.stringify(stored).includes("Meet") && stored[0].email_id === m.id, stored);

// another lesson finished: the booking moves
r = await call(env(), "/api/nudge", { body: { token: tok, next: { t: "Shapes in words" } } });
const m2 = state.emails[state.emails.length - 1];
check("finishing another lesson moves the email", r.status === 200 && m.canceled === true && m2 !== m && !m2.canceled && m2.text.includes("Shapes in words"), { r, c: m.canceled });
check("still only one waiting", state.emails.filter(x => x.to[0] === "mum@example.com" && !x.canceled).length === 1, "");
r = await call(env(), "/api/nudge", { body: { token: "x".repeat(43), next } });
check("an unknown token: gone, so the app forgets it", r.status === 404 && r.json.error === "gone", r);

// the link in the email: a browser (or a mail scanner) only sees a button
r = await call(env(), "/api/nudge/stop?t=" + tok, { method: "GET" });
check("opening the link shows a button and stops nothing yet", r.status === 200 && r.text.includes("Stop the emails") && !db.q("SELECT stopped FROM nudges")[0].stopped && !m2.canceled, r.status);
// Gmail's one-click: a POST from Google's servers, no Origin, a form body
r = await call(env(), "/api/nudge/stop?t=" + tok, { raw: "List-Unsubscribe=One-Click", type: "application/x-www-form-urlencoded", origin: null });
check("the mail app's one-click stop works, and forgets the address", r.status === 200 && r.text.includes("No more reminder emails") && db.q("SELECT * FROM nudges").length === 0 && m2.canceled === true, r.status);
const before = state.emails.length;
r = await call(env(), "/api/nudge", { body: { token: tok, next } });
check("after stopping, a lesson books nothing", r.status === 404 && state.emails.length === before, r);

// asking again from the app turns them back on, with a new token
r = await call(env(), "/api/nudge/start", { body: { email: "mum@example.com", agree: true, next } });
const tok2 = r.json && r.json.token;
check("asking again turns it back on, one row", r.status === 200 && tok2 !== tok && db.q("SELECT * FROM nudges").length === 1, r);
r = await call(env(), "/api/nudge/stop", { body: { token: tok2 } });
check("the app's own Stop button works, and forgets the address", r.status === 200 && db.q("SELECT * FROM nudges").length === 0 && state.emails[state.emails.length - 1].canceled, r);

// limits: one place can't sign up lots of addresses
let ok = 0;
for (let i = 0; i < 8; i++) { const x = await call(env(), "/api/nudge/start", { body: { email: `kid${i}@example.com`, agree: true, next }, sameIp: "10.77.0.1" }); if (x.status === 200) ok++; }
check(`one place can ask for only a few addresses a day (${ok})`, ok >= 1 && ok <= 4, ok);

// the stats page lists the new events
r = await call(env(), "/api/usage", { body: { e: ["nudge_on", "from_email", "from_email"], d: new Date().toISOString().slice(0, 10) } });
const u = Object.fromEntries(db.q("SELECT name, n FROM usage").map(x => [x.name, x.n]));
check("the stats count who asked and who came from an email", u.nudge_on === 1 && u.from_email === 2, u);

servers.forEach(s => s.close());
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
