// The website server on its own: sign-in by email code (with the optional robot check), free talks, plans with
// Stripe, confirmation codes, daily limits, the setup check and the parents page, against pretend Claude, Stripe,
// Resend and Turnstile and a stand-in database. Version 4: after the second independent review.
import fs from "node:fs";
import http from "node:http";
import crypto from "node:crypto";
import { D1 } from "./d1shim.mjs";
import { state, TURNSTILE, claudeServer, stripeServer, resendServer, turnstileServer } from "./mocks.mjs";
const worker = (await import("/home/claude/alefba-site/_worker.js?v=" + Date.now())).default;
const PARENTS = fs.readFileSync("/home/claude/alefba-site/parents.html", "utf8");
const ADULTS = fs.readFileSync("/home/claude/alefba-site/adults.html", "utf8");
const servers = [claudeServer(19787), stripeServer(19788), resendServer(19789), turnstileServer(19790)];

const db = new D1();
const ETAG = '"parents-v1"';
const ASSETS = { fetch: async (r) => {
  const p = new URL(r.url).pathname;
  if (p === "/parents.html") return new Response(null, { status: 308, headers: { location: "/parents" } });
  if (p === "/adults.html") return new Response(null, { status: 308, headers: { location: "/adults" } });
  if (p === "/adults") return new Response(r.method === "HEAD" ? null : ADULTS, { headers: { "content-type": "text/html; charset=utf-8" } });
  if (p === "/parents") {
    if (r.headers.get("if-none-match") === ETAG) return new Response(null, { status: 304, headers: { etag: ETAG } });
    return new Response(r.method === "HEAD" ? null : PARENTS, { headers: { "content-type": "text/html; charset=utf-8", etag: ETAG } });
  }
  return new Response("file " + p);
} };
const KEY = "sk-ant-" + "test-0123456789abcdef";
const FULL = { ANTHROPIC_API_KEY: KEY, ANTHROPIC_BASE_URL: "http://127.0.0.1:19787", RESEND_API_KEY: "re_" + "test_0123456789abcdefghij", RESEND_BASE_URL: "http://127.0.0.1:19789",
  STRIPE_SECRET_KEY: "sk_" + "test_0123456789abcdefghij", STRIPE_BASE_URL: "http://127.0.0.1:19788", TURNSTILE_BASE_URL: "http://127.0.0.1:19790",
  EMAIL_FROM: "Alefba <hello@alefba.example>", DB: db, ASSETS };
const env = (extra = {}) => ({ ...FULL, ...extra });
const ROBOT = { TURNSTILE_SITE_KEY: TURNSTILE.site, TURNSTILE_SECRET_KEY: TURNSTILE.secret };
const ctx = { waitUntil: p => p };
const FIRST = "You are Sara (سارا), a new classmate, in a Persian practice app for children aged about 7 to 14. Keep it simple.";
const opening = [{ role: "user", content: FIRST }];
// an earlier reply as the app keeps it (the same fields, in the same order, as the server rebuilds it)
const REPLY = JSON.stringify({ fa: "سلام! حالت چطوره؟", translit: "salâm! hâlet chetore?", en: "Hi! How are you?", written: "سلام! حالت چطور است؟", written_translit: "salâm! hâlat chetor ast?", feedback: null,
  suggestions: [{ fa: "خوبم.", translit: "khubam.", en: "I'm good." }], new_words: [], goals_done: [1], pace: "same", done: false });
const later = (text, reply = REPLY) => [...opening, { role: "assistant", content: reply }, { role: "user", content: text }];
const enc8 = new TextEncoder(), mostItCosts = turns => Math.ceil((turns.reduce((n, t) => n + enc8.encode(t.content).length, 0) + 4000) * 0.125 + 1500 * 0.5);

let ipN = 0;
class Agent {
  constructor(cookie = "") { ++ipN; this.ip = `10.${Math.floor(ipN / 250)}.${ipN % 250}.7`; this.cookie = cookie; }
  fresh() { return new Agent(this.cookie); } // the same device from another connection
  async call(e, path, { method = "GET", body, headers = {}, origin = "https://alefba.example", host = "alefba.example" } = {}) {
    const h = new Headers({ "CF-Connecting-IP": this.ip, ...headers });
    if (this.cookie) h.set("cookie", this.cookie);
    if (body !== undefined) h.set("content-type", "application/json");
    if (method === "POST" && origin) h.set("Origin", origin);
    const r = await worker.fetch(new Request("https://" + host + path, { method, headers: h, body: body === undefined ? undefined : JSON.stringify(body) }), e, ctx);
    const sc = r.headers.get("set-cookie");
    if (sc) { const m = /^([^=]+)=([^;]*)/.exec(sc); this.cookie = m[2] ? `${m[1]}=${m[2]}` : ""; }
    const text = await r.text();
    let json = null; try { json = JSON.parse(text); } catch (err) {}
    return { status: r.status, json, text, headers: r.headers, setCookie: sc };
  }
  post(e, path, body, opts = {}) { return this.call(e, path, { method: "POST", body, ...opts }); }
  async signIn(e, email) {
    const s = await this.post(e, "/api/auth/start", { email, agree: true });
    if (s.status !== 200) return s;
    return this.post(e, "/api/auth/verify", { email, code: lastCode(email) });
  }
  talk(e, turns, talk_id, talk_key) { return this.post(e, "/api/talk", { turns, talk_id, talk_key }); }
  // ask for a confirmation code and return it (codes for one address are 20 seconds apart, so the wait is skipped here)
  async confirm(e, email) {
    db.x("UPDATE codes SET sent_at = sent_at - 60000 WHERE email = ?", "confirm:" + email);
    const r = await this.post(e, "/api/confirm", {});
    return r.status === 200 ? lastCode(email) : r;
  }
}
const lastCode = email => { const m = state.emails.filter(x => x.to.includes(email)).pop(); return m ? /(\d{6})/.exec(m.subject)[1] : null; };
const emailsTo = email => state.emails.filter(x => x.to.includes(email)).length;
const otherCode = c => String((Number(c) + 1) % 1e6).padStart(6, "0");
async function pay(url) { const r = await fetch(url, { method: "POST", redirect: "manual" }); return r.headers.get("location"); }
function normal(e) { let [u, d] = e.toLowerCase().split("@"); u = u.split("+")[0]; if (d === "googlemail.com") d = "gmail.com"; if (d === "gmail.com") u = u.replace(/\./g, ""); return u + "@" + d; }
const ledgerKey = email => crypto.createHash("sha256").update("alefba-free:" + normal(email)).digest("hex");
const freeUsed = email => { const r = db.q("SELECT used FROM free_ledger WHERE h = ?", ledgerKey(email))[0]; return r ? r.used : 0; };
const setFreeUsed = (email, n) => db.x("INSERT INTO free_ledger (h, used) VALUES (?, ?) ON CONFLICT(h) DO UPDATE SET used = excluded.used", ledgerKey(email), n);
const famOf = email => db.q("SELECT * FROM families WHERE email = ?", email)[0];
const today = () => new Date().toISOString().slice(0, 10);

let pass = 0, fail = 0;
function check(name, ok, extra) { if (ok) pass++; else fail++; console.log((ok ? "PASS " : "FAIL ") + name + (!ok && extra !== undefined ? "  [" + JSON.stringify(extra).slice(0, 500) + "]" : "")); }

// ---------------- classes (teacher mode) ----------------
const T = new Agent();
let r = await T.post(env(), "/api/class/create", { name: "Saturday Farsi" });
check("making a class needs a signed-in grown-up", r.status === 401 && r.json.error === "sign_in", r.json);
await T.signIn(env(), "teacher@example.com");
r = await T.post(env(), "/api/class/create", { name: "" });
check("a class needs a name", r.status === 400 && r.json.error === "bad_name", r.json);
r = await T.post(env(), "/api/class/create", { name: "email me at x@y.com" });
check("a class name can't be an email address", r.status === 400, r.json);
r = await T.post(env(), "/api/class/create", { name: "Saturday Farsi 2026-2027" });
check("a teacher makes a class and gets a 6-letter code with no 0, O, 1 or I", r.status === 200 && /^[A-HJ-NP-Z2-9]{6}$/.test(r.json.class.code) && r.json.class.members === 0, r.json);
const cls = r.json.class;
r = await T.post(env(), "/api/class/list", {});
check("the teacher sees their class in the list", r.status === 200 && r.json.classes.length === 1 && r.json.classes[0].code === cls.code, r.json);

// a learner joins
const K = new Agent();
r = await K.post(env(), "/api/class/join", { code: "ZZZZZZ", name: "Sara" });
check("a wrong code is refused", r.status === 404 && r.json.error === "bad_code", r.json);
r = await K.post(env(), "/api/class/join", { code: cls.code, name: "" });
check("a learner needs a name", r.status === 400 && r.json.error === "bad_name", r.json);
r = await K.post(env(), "/api/class/join", { code: cls.code, name: "07700 900123" });
check("a phone number isn't accepted as a name", r.status === 400 && r.json.error === "bad_name", r.json);
r = await K.post(env(), "/api/class/join", { code: cls.code.toLowerCase().slice(0, 3) + "-" + cls.code.toLowerCase().slice(3), name: "  Sara   K  " });
check("joining works with a lowercase code and a dash, and the name is tidied", r.status === 200 && r.json.name === "Sara K" && r.json.class.name === "Saturday Farsi 2026-2027" && typeof r.json.token === "string" && r.json.token.length >= 40, r.json);
const tok = r.json.token;
const row = db.q("SELECT * FROM class_members")[0];
check("the learner's key is kept only as a hash", row && row.token_hash !== tok && !JSON.stringify(row).includes(tok), row);

// the teacher assigns lessons
r = await T.post(env(), "/api/class/assign", { id: cls.id, lessons: ["a1-1", "w1-1", "w1-talk", "w1-1", "BAD ID", 42] });
check("assigning keeps valid lesson names once each", r.status === 200 && JSON.stringify(r.json.class.assigned) === JSON.stringify(["a1-1", "w1-1", "w1-talk"]), r.json);
r = await T.post(env(), "/api/class/assign", { id: cls.id, lessons: Array.from({ length: 41 }, (_, i) => "w" + i) });
check("no more than 40 lessons can be assigned at once", r.status === 400, r.json);

// the learner sees them and sends progress
r = await K.post(env(), "/api/class/mine", { token: tok });
check("the learner's device gets the class name and the assigned lessons", r.status === 200 && r.json.class.assigned.length === 3 && r.json.name === "Sara K", r.json);
r = await K.post(env(), "/api/class/progress", { token: tok, progress: { done: ["a1-1", "w1-1", "nope!", "a1-1"], days: ["2026-10-25", "2026-10-26", "bad"], streak: 2, best: 5, letters: 40, words: 12, today: "2026-10-26", talk: "secret chat text", name: "Full Name" } });
check("progress is saved", r.status === 200, r.json);
const saved = JSON.parse(db.q("SELECT progress FROM class_members")[0].progress);
check("only the expected counts and lesson names are kept (bad ones dropped, numbers capped, nothing else)", JSON.stringify(saved.done) === '["a1-1","w1-1"]' && saved.days.length === 2 && saved.letters === 32 && saved.streak === 2 && !("talk" in saved) && !("name" in saved), saved);
r = await K.post(env(), "/api/class/progress", { token: "x".repeat(43), progress: {} });
check("a made-up key can't send progress", r.status === 404 && r.json.error === "not_in_class", r.json);

// the teacher's view
r = await T.post(env(), "/api/class/view", { id: cls.id });
check("the teacher sees each learner's name and progress", r.status === 200 && r.json.class.members.length === 1 && r.json.class.members[0].name === "Sara K" && r.json.class.members[0].progress.done.length === 2, r.json);
check("the teacher's view never shows a learner's key", !r.text.includes(tok) && !r.text.includes("token"), r.text.slice(0, 200));

// another grown-up can't see or change this class
const O = new Agent(); await O.signIn(env(), "other@example.com");
r = await O.post(env(), "/api/class/view", { id: cls.id });
check("another account can't see the class", r.status === 404, r.json);
r = await O.post(env(), "/api/class/assign", { id: cls.id, lessons: [] });
check("another account can't assign lessons", r.status === 404, r.json);
r = await O.post(env(), "/api/class/delete", { id: cls.id });
check("another account can't delete the class", r.status === 404 && db.q("SELECT COUNT(*) AS n FROM classes")[0].n === 1, r.json);
r = await O.post(env(), "/api/class/create", { name: "Hack" }, { origin: "https://elsewhere.example" });
check("another website can't make classes", r.status === 403, r.json);

// removing and leaving
const K2 = new Agent();
r = await K2.post(env(), "/api/class/join", { code: cls.code, name: "Arash" });
const tok2 = r.json.token;
r = await T.post(env(), "/api/class/view", { id: cls.id });
const arash = r.json.class.members.find(m => m.name === "Arash");
r = await T.post(env(), "/api/class/remove", { id: cls.id, member: arash.id });
check("the teacher can remove a learner", r.status === 200 && db.q("SELECT COUNT(*) AS n FROM class_members")[0].n === 1, r.json);
r = await K2.post(env(), "/api/class/mine", { token: tok2 });
check("a removed learner's device is told it's no longer in the class", r.status === 404 && r.json.error === "not_in_class", r.json);
r = await K.post(env(), "/api/class/leave", { token: tok });
check("leaving deletes the learner's name and progress", r.status === 200 && db.q("SELECT COUNT(*) AS n FROM class_members")[0].n === 0, r.json);

// limits
for (let i = 0; i < 25; i++) await T.fresh().post(env(), "/api/class/create", { name: "Class " + i });
r = await T.fresh().post(env(), "/api/class/list", {});
check("a teacher can have at most 20 classes", r.json.classes.length === 20, r.json.classes.length);
const J = new Agent();
let lastJoin;
for (let i = 0; i < 8; i++) lastJoin = await J.post(env(), "/api/class/join", { code: "AAAAAA", name: "x" });
check("guessing codes is slowed down", lastJoin.status === 429, lastJoin.json);

// deleting the teacher's account deletes the classes and everyone's progress in them
const K3 = new Agent();
r = await K3.post(env(), "/api/class/join", { code: cls.code, name: "Neda" });
const code = await T.fresh().confirm(env(), "teacher@example.com");
r = await T.post(env(), "/api/account/delete", { code, endPlan: true });
check("the teacher can delete their account", r.status === 200, r.json);
check("...which deletes their classes and the learners' rows", db.q("SELECT COUNT(*) AS n FROM classes")[0].n === 0 && db.q("SELECT COUNT(*) AS n FROM class_members")[0].n === 0);

// the class deletes itself only for its owner
const T2 = new Agent(); await T2.signIn(env(), "t2@example.com");
r = await T2.post(env(), "/api/class/create", { name: "Evening" });
const c2 = r.json.class;
await new Agent().post(env(), "/api/class/join", { code: c2.code, name: "Leila" });
r = await T2.post(env(), "/api/class/delete", { id: c2.id });
check("deleting a class removes its learners too", r.status === 200 && db.q("SELECT COUNT(*) AS n FROM class_members")[0].n === 0 && db.q("SELECT COUNT(*) AS n FROM classes")[0].n === 0, r.json);

servers.forEach(s => s.close());
console.log(`\n${pass} of ${pass + fail} passed`);
process.exit(fail ? 1 : 0);
