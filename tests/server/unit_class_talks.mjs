// The school plan with talks: learners in a class talk (and say answers out loud) with their class key, without
// signing in, 5 talks a month each, after the teacher agrees for the class and pays. Against pretend Claude and Stripe.
import fs from "node:fs";
import http from "node:http";
import crypto from "node:crypto";
import { D1 } from "./d1shim.mjs";
import { state, TURNSTILE, claudeServer, stripeServer, resendServer, turnstileServer } from "./mocks.mjs";
const worker = (await import("/home/claude/alefba-site/_worker.js?v=" + Date.now())).default;
const PARENTS = fs.readFileSync("/home/claude/alefba-site/parents.html", "utf8");
const ADULTS = fs.readFileSync("/home/claude/alefba-site/adults.html", "utf8");
const servers = [claudeServer(39787), stripeServer(39788), resendServer(39789), turnstileServer(39790)];

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
const FULL = { ANTHROPIC_API_KEY: KEY, ANTHROPIC_BASE_URL: "http://127.0.0.1:39787", RESEND_API_KEY: "re_" + "test_0123456789abcdefghij", RESEND_BASE_URL: "http://127.0.0.1:39789",
  STRIPE_SECRET_KEY: "sk_" + "test_0123456789abcdefghij", STRIPE_BASE_URL: "http://127.0.0.1:39788", TURNSTILE_BASE_URL: "http://127.0.0.1:39790",
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
const AI = { run: async () => ({ text: "سلام" }) }; // pretend speech-to-text
const asLearner = token => ({ headers: { "x-alefba-class": token } });
const lines = r => r.text.trim().split("\n").filter(Boolean).map(l => JSON.parse(l));

// ================= the school plan with talks =================
const T = new Agent(); await T.signIn(env(), "talkteacher@example.com");
let r = await T.call(env(), "/api/me");
check("the account shows the price of the plan with talks ($59.99) and 5 talks per learner", r.json.prices.schoolTalks === "$59.99" && r.json.classTalks === 5 && r.json.prices.schoolUpgrade === "$10.99", r.json.prices);
r = await T.post(env(), "/api/class/create", { name: "Saturday class" });
const cls = r.json.class;
const kid = new Agent();
r = await kid.post(env(), "/api/class/join", { code: cls.code, name: "Sara" });
const tok = r.json.token;
check("a learner in a class without talks is told there are none", r.json.class.talks === null, r.json.class);
r = await kid.post(env(), "/api/talk", { turns: opening, talk_key: "kid-key-00000001" }, asLearner(tok));
check("without the plan, a learner can't talk with their class key", r.status === 402 && r.json.error === "needs_plan", r.json);
r = await kid.post(env(), "/api/talk", { turns: opening, talk_key: "kid-key-00000001" });
check("and without the key or signing in, nothing", r.status === 401, r.json);
r = await T.post(env(), "/api/class/checkout", { id: cls.id, kind: "talks" });
check("buying talks needs the teacher to agree for the class", r.status === 400 && r.json.error === "needs_agree", r.json);
r = await T.post(env(), "/api/class/checkout", { id: cls.id, kind: "talks", agree: true });
let call = state.stripeCalls.filter(c => c.path === "/v1/checkout/sessions").pop();
check("then it's one payment of $59.99 for a year, with talks", r.status === 200 && call.params["line_items[0][price_data][unit_amount]"] === "5999" && call.params["metadata[alefba_kind]"] === "school_talks" && /with talks/.test(call.params["line_items[0][price_data][product_data][name]"]), call.params);
check("the time the teacher agreed is kept with the class", Number(db.q("SELECT agreed_at FROM classes WHERE id = ?", cls.id)[0].agreed_at) > Date.now() - 60e3);
await pay(r.json.url);
r = await T.post(env(), "/api/class/view", { id: cls.id });
const yr = (r.json.class.talksUntil - Date.now()) / 864e5, yrL = (r.json.class.paidUntil - Date.now()) / 864e5;
check("after paying, the class has all the levels and talks for a year", yr > 364 && yr < 366 && yrL > 364 && yrL < 366, r.json.class);
r = await kid.post(env(), "/api/class/mine", { token: tok });
check("the learner is told: 5 talks left this month", r.json.class.talks && r.json.class.talks.left === 5 && r.json.class.talks.per === 5 && r.json.class.fullUntil > Date.now(), r.json.class);

// talks with the class key, no signing in
r = await kid.post(env(), "/api/talk", { turns: opening, talk_key: "kid-key-00000002", stream: true }, asLearner(tok));
let L = lines(r);
check("a learner talks with just their class key (streamed)", r.status === 200 && L[0].early && L[1].reply && L[1].reply.fa, L);
const tid = L[1].reply.talk_id;
check("the reply says how many talks are left now", L[1].reply.class && L[1].reply.class.talks.left === 4 && !L[1].reply.account, L[1].reply);
r = await kid.post(env(), "/api/talk", { turns: later("salam"), talk_id: tid }, asLearner(tok));
check("the talk goes on, and the next messages don't count as new talks", r.status === 200 && r.json.fa, r.json);
r = await kid.post(env(), "/api/class/mine", { token: tok });
check("(still 4 left)", r.json.class.talks.left === 4, r.json.class.talks);
const spentKid = db.q("SELECT micro FROM spend WHERE k LIKE ?", "%:m:%")[0];
check("what the learner's talks cost is counted under the learner, for the daily limits", spentKid && spentKid.micro > 0, spentKid);
for (let i = 3; i <= 7; i++) r = await kid.post(env(), "/api/talk", { turns: opening, talk_key: "kid-key-0000000" + i }, asLearner(tok));
check("a 6th talk in a month isn't allowed", r.status === 402 && r.json.error === "no_talks" && r.json.class.talks.left === 0, r.json);
r = await kid.post(env(), "/api/talk", { turns: opening, talk_key: "kid-key-00000002" }, asLearner(tok));
check("a retry of a talk already started still goes on (not a new talk)", r.status === 200, r.json);
const kid2 = new Agent();
r = await kid2.post(env(), "/api/class/join", { code: cls.code, name: "Arash" });
const tok2 = r.json.token;
check("another learner has their own 5", r.json.class.talks.left === 5, r.json.class);
r = await kid2.post(env(), "/api/talk", { turns: opening, talk_key: "kid2-key-0000001" }, asLearner(tok2));
check("and can talk", r.status === 200, r.json);
// the whole class's limit
r = await kid2.post(env({ CLASS_TALKS_CAP: "6" }), "/api/talk", { turns: opening, talk_key: "kid2-key-0000002" }, asLearner(tok2));
check("a class can't go over its monthly total (CLASS_TALKS_CAP)", r.status === 402 && r.json.error === "class_talks_used", r.json);
r = await kid2.post(env({ CLASS_TALKS_CAP: "6" }), "/api/class/mine", { token: tok2 });
check("and its learners are told none are left", r.json.class.talks.left === 0 && r.json.class.talks.classUsedUp === true, r.json.class.talks);

// speaking practice and the gloss with the class key
const wav = new Uint8Array(2000); wav.set([0x52, 0x49, 0x46, 0x46, 0, 0, 0, 0, 0x57, 0x41, 0x56, 0x45]);
const hearAs = async (token) => { const h = new Headers({ "CF-Connecting-IP": "10.9.9.9", "content-type": "audio/wav", Origin: "https://alefba.example" }); if (token) h.set("x-alefba-class", token); const x = await worker.fetch(new Request("https://alefba.example/api/hear", { method: "POST", headers: h, body: wav }), env({ AI }), ctx); return { status: x.status, json: await x.json() }; };
r = await hearAs(tok);
check("a learner with talks can say their answers out loud", r.status === 200 && r.json.text === "سلام", r);
r = await hearAs("x".repeat(43));
check("a key that isn't anyone's can't", r.status === 404 && r.json.error === "not_in_class", r);
r = await kid.post(env(), "/api/gloss", { text: "من قهوه دوست دارم" }, asLearner(tok));
check("and what they said is put into Finglish for them", r.status === 200 && r.json.translit, r.json);

// a class that has the school plan already: talks are added for the difference
const T3 = new Agent(); await T3.signIn(env(), "upgrade@example.com");
r = await T3.post(env(), "/api/class/create", { name: "Evening class" });
const c3 = r.json.class;
r = await T3.post(env(), "/api/class/checkout", { id: c3.id }); await pay(r.json.url);
r = await T3.post(env(), "/api/class/view", { id: c3.id });
const paidUntil = r.json.class.paidUntil;
check("a class with the school plan has no talks", paidUntil > Date.now() && !(r.json.class.talksUntil > Date.now()), r.json.class);
r = await T3.post(env(), "/api/class/checkout", { id: c3.id, kind: "talks", agree: true });
call = state.stripeCalls.filter(c => c.path === "/v1/checkout/sessions").pop();
check("adding talks costs the difference ($10.99), until the plan ends", r.status === 200 && call.params["line_items[0][price_data][unit_amount]"] === "1099" && call.params["metadata[alefba_kind]"] === "talks_upgrade", call.params);
await pay(r.json.url);
r = await T3.post(env(), "/api/class/view", { id: c3.id });
check("after paying, talks last as long as the school plan", r.json.class.talksUntil === paidUntil && r.json.class.paidUntil === paidUntil, r.json.class);
r = await T3.post(env(), "/api/class/checkout", { id: c3.id, kind: "talks", agree: true });
check("with most of the year left, talks can't be bought again yet", r.status === 409 && r.json.error === "has_plan", r.json);
// once the talks are over
db.x("UPDATE classes SET talks_until = ? WHERE id = ?", Date.now() - 1000, cls.id);
r = await kid.post(env(), "/api/talk", { turns: opening, talk_key: "kid-key-00000009" }, asLearner(tok));
check("once the year with talks is over, a learner's key doesn't start talks", r.status === 402 && r.json.error === "needs_plan", r.json);
r = await kid.post(env(), "/api/class/mine", { token: tok });
check("and the learner is told", r.json.class.talks === null, r.json.class);
// families are unchanged
const F = new Agent(); await F.signIn(env(), "family@example.com");
r = await F.talk(env(), opening, null, "fam-key-00000001");
check("a family still talks as before (a free talk)", r.status === 200 && r.json.account && r.json.account.left === 2, r.json.account);

servers.forEach(s => s.close());
console.log(`\n${pass} of ${pass + fail} passed`);
process.exit(fail ? 1 : 0);
