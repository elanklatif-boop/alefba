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
const servers = [claudeServer(29787), stripeServer(29788), resendServer(29789), turnstileServer(29790)];

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
const FULL = { ANTHROPIC_API_KEY: KEY, ANTHROPIC_BASE_URL: "http://127.0.0.1:29787", RESEND_API_KEY: "re_" + "test_0123456789abcdefghij", RESEND_BASE_URL: "http://127.0.0.1:29789",
  STRIPE_SECRET_KEY: "sk_" + "test_0123456789abcdefghij", STRIPE_BASE_URL: "http://127.0.0.1:29788", TURNSTILE_BASE_URL: "http://127.0.0.1:29790",
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


// ================= progress on every device =================
const SA = new Agent(), SB = new Agent(); // the laptop and the tablet, same family
await SA.signIn(env(), "sync@example.com"); await SB.signIn(env(), "sync@example.com");
let r = await SA.call(env(), "/api/me");
check("progress sync starts off", r.json.signedIn && r.json.sync === false, r.json);
const sara = (over = {}) => ({ done: { "a1-1": true }, items: { "w:salâm": { r: 2, w: 0 } }, days: ["2026-10-20", "2026-10-21"], rest: 0, restDays: [], talks: {}, prefs: { lang: "en" }, profile: { name: "Sara", goal: 2, adult: false }, log: { "2026-10-21": 2 }, best: 2, updated: 1000, ...over });
r = await SA.post(env(), "/api/sync", { learners: [{ lid: "main", state: sara() }] });
check("syncing before it's turned on is refused", r.status === 409 && r.json.error === "sync_off", r.json);
r = await SA.post(env(), "/api/sync/on", {});
check("turning it on needs the grown-up's yes", r.status === 400 && r.json.error === "agree", r.json);
r = await SA.post(env(), "/api/sync/on", { agree: true });
check("a grown-up turns it on", r.status === 200 && r.json.sync === true, r.json);
check("and the account says so", (await SB.call(env(), "/api/me")).json.sync === true);
r = await SA.post(env(), "/api/sync", { learners: [{ lid: "main", state: sara() }, { lid: "l2", state: sara({ profile: { name: "Nima", goal: 1 }, done: { "a1-1": true, "a1-2": true } }) }] });
const saraSid = r.json && r.json.learners && (r.json.learners.find(x => x.lid === "main") || {}).sid;
check("the laptop's learners are saved, each with its own id", r.status === 200 && r.json.learners.length === 2 && /^[0-9a-f]{24}$/.test(saraSid || "") && r.json.learners.every(x => x.state.sid === x.sid), r.json);
r = await SB.post(env(), "/api/sync", { learners: [] });
check("the tablet gets both learners", r.status === 200 && r.json.learners.length === 2 && r.json.learners.some(x => x.state.profile.name === "Nima"), r.json);
r = await SB.post(env(), "/api/sync", { learners: [{ lid: "main", state: sara({ done: { "a1-3": true }, items: { "w:salâm": { r: 1, w: 3 } }, days: ["2026-10-22"], log: { "2026-10-21": 1, "2026-10-22": 3 }, best: 1, updated: 2000, prefs: { lang: "fr" } }) }] });
const merged = r.json.learners.find(x => x.state.profile.name === "Sara");
check("a Sara started on the tablet is the same Sara (matched by name), not a third learner", r.json.learners.length === 2 && merged.sid === saraSid && merged.lid === "main", r.json.learners.map(x => [x.sid, x.lid, x.state.profile.name]));
check("lessons from both devices are kept", merged.state.done["a1-1"] === true && merged.state.done["a1-3"] === true, merged.state.done);
check("scores keep the highest of each", merged.state.items["w:salâm"].r === 2 && merged.state.items["w:salâm"].w === 3, merged.state.items);
check("practice days from both, so the streak counts them all", JSON.stringify(merged.state.days) === JSON.stringify(["2026-10-20", "2026-10-21", "2026-10-22"]), merged.state.days);
check("today's lesson counts and the best streak keep the highest", merged.state.log["2026-10-21"] === 2 && merged.state.log["2026-10-22"] === 3 && merged.state.best === 2, [merged.state.log, merged.state.best]);
check("settings come from the copy saved last", merged.state.prefs.lang === "fr", merged.state.prefs);
check("a lesson done for real beats one skipped by the level check", (await SA.post(env(), "/api/sync", { learners: [{ sid: saraSid, state: { ...merged.state, done: { ...merged.state.done, "w1-1": "test" }, updated: 3000 } }] })).json && true);
r = await SB.post(env(), "/api/sync", { learners: [{ sid: saraSid, state: { ...merged.state, done: { ...merged.state.done, "w1-1": true }, updated: 2500 } }] });
check("(done on the tablet, skipped on the laptop: done)", r.json.learners.find(x => x.sid === saraSid).state.done["w1-1"] === true, r.json.learners.find(x => x.sid === saraSid).state.done);
const nimaSid = r.json.learners.find(x => x.state.profile.name === "Nima").sid;
r = await SA.post(env(), "/api/sync/remove", { sid: nimaSid });
check("removing a learner on one device removes the online copy", r.status === 200 && db.q("SELECT COUNT(*) AS n FROM progress WHERE sid = ?", nimaSid)[0].n === 0);
r = await SB.post(env(), "/api/sync", { learners: [{ sid: nimaSid, state: { profile: { name: "Nima" }, done: {}, updated: 9000 } }] });
check("the other device is told it's gone, and can't bring it back", r.json.gone.includes(nimaSid) && !r.json.learners.some(x => x.sid === nimaSid), r.json);
r = await SA.post(env(), "/api/sync", { learners: [{ lid: "big", state: sara({ profile: { name: "Big" }, pad: "x".repeat(120000) }) }] });
check("a record far bigger than any real one is left out (and the others still sync)", r.status === 200 && (r.json.skipped || []).includes("big") && !r.json.learners.some(x => x.state.profile.name === "Big"), r.status);
// review fixes: what's never kept, level-check marks, the month of daily counts, rest days
r = await SA.post(env(), "/api/sync", { learners: [{ sid: saraSid, state: { ...sara(), cls: { token: "T".repeat(43), name: "Sara" }, talks: { park: 3 }, updated: 5000 } }] });
const row = JSON.parse(db.q("SELECT state FROM progress WHERE sid = ?", saraSid)[0].state);
check("the class key and the talk counts are never kept online", !("cls" in row) && !("talks" in row) && !JSON.stringify(row).includes("TTTT"), Object.keys(row));
r = await SA.post(env(), "/api/sync", { learners: [{ sid: saraSid, state: { ...row, done: { ...row.done, "w2-1": "test", "w2-2": "test" }, testAt: 6000, updated: 6000 } }] });
r = await SB.post(env(), "/api/sync", { learners: [{ sid: saraSid, state: { ...row, done: { ...row.done, "w2-1": "test" }, testAt: 7000, updated: 5500 } }] });
let d2 = r.json.learners.find(x => x.sid === saraSid).state.done;
check("a level check taken again later decides the skipped lessons (one taken away stays away)", d2["w2-1"] === "test" && !("w2-2" in d2), d2);
const manyDays = Object.fromEntries(Array.from({ length: 50 }, (_, i) => [`2026-08-${String(i % 31 + 1).padStart(2, "0")}`.replace(/-(3[2-9]|[4-9]\d)$/, "-01"), 1]).concat(Array.from({ length: 40 }, (_, i) => [new Date(Date.UTC(2026, 6, 1 + i)).toISOString().slice(0, 10), 2])));
r = await SA.post(env(), "/api/sync", { learners: [{ sid: saraSid, state: { ...row, log: manyDays, updated: 8000 } }] });
check("only a month of daily lesson counts is kept, so a record can't grow forever", Object.keys(r.json.learners.find(x => x.sid === saraSid).state.log).length <= 31, Object.keys(r.json.learners.find(x => x.sid === saraSid).state.log).length);
r = await SA.post(env(), "/api/sync", { learners: [{ sid: saraSid, state: { ...row, restGot: ["2026-10-07", "2026-10-14"], restDays: ["2026-10-16"], updated: 9000 } }] });
r = await SB.post(env(), "/api/sync", { learners: [{ sid: saraSid, state: { ...row, restGot: ["2026-10-07", "2026-10-14"], restDays: [], rest: 2, updated: 9500 } }] });
const rs = r.json.learners.find(x => x.sid === saraSid).state;
check("a rest day used on one device stays used on the other (it can't be spent twice)", rs.rest === 1 && rs.restDays.length === 1 && rs.restGot.length === 2, [rs.rest, rs.restDays, rs.restGot]);
const nine = Array.from({ length: 9 }, (_, i) => ({ lid: "k" + i, state: sara({ profile: { name: "K" + i } }) }));
r = await SA.post(env(), "/api/sync", { learners: nine });
check("no more than 8 learners at once", r.status === 400, r.status);
r = await SA.post(env(), "/api/sync", { learners: Array.from({ length: 8 }, (_, i) => ({ lid: "k" + i, state: sara({ profile: { name: "K" + i } }) })) });
check("and the family keeps at most 8", r.status === 200 && r.json.learners.length === 8, r.json && r.json.learners && r.json.learners.length);
const other = new Agent(); await other.signIn(env(), "someone@example.com");
r = await other.post(env(), "/api/sync/on", { agree: true });
r = await other.post(env(), "/api/sync", { learners: [] });
check("another family never sees these learners", r.status === 200 && r.json.learners.length === 0, r.json);
r = await new Agent().post(env(), "/api/sync", { learners: [] });
check("signed out: no sync", r.status === 401, r.status);
r = await SA.post(env(), "/api/sync/off", {});
check("turning it off deletes every online copy at once", r.status === 200 && db.q("SELECT COUNT(*) AS n FROM progress WHERE family_id = ?", famOf("sync@example.com").id)[0].n === 0 && !(await SA.call(env(), "/api/me")).json.sync);
await SA.post(env(), "/api/sync/on", { agree: true }); await SA.post(env(), "/api/sync", { learners: [{ lid: "main", state: sara() }] });
const fid = famOf("sync@example.com").id;
let code = await SA.confirm(env(), "sync@example.com");
r = await SA.post(env(), "/api/account/delete", { code });
check("deleting the account deletes the online progress too", r.status === 200 && db.q("SELECT COUNT(*) AS n FROM progress WHERE family_id = ?", fid)[0].n === 0, r.json);

// ================= school plan =================
const T = new Agent(); await T.signIn(env(), "teacher@example.com");
r = await T.post(env(), "/api/class/create", { name: "Saturday beginners" });
const cls = r.json.class;
check("a new class has no school plan", cls.paidUntil === 0 && cls.pending === false, cls);
const kid = new Agent();
r = await kid.post(env(), "/api/class/join", { code: cls.code, name: "Sara" });
const kidToken = r.json.token;
check("a learner joining is told the class has no school plan", r.status === 200 && r.json.class.fullUntil === 0, r.json);
r = await T.call(env(), "/api/me");
check("the account shows the school plan price ($49 by default)", r.json.prices.school === "$49", r.json.prices);
r = await new Agent().post(env(), "/api/class/checkout", { id: cls.id });
check("signed out: no checkout", r.status === 401, r.status);
const T2 = new Agent(); await T2.signIn(env(), "other-teacher@example.com");
r = await T2.post(env(), "/api/class/checkout", { id: cls.id });
check("another teacher can't pay for (or see) this class", r.status === 404, r.status);
r = await T.post(env({ STRIPE_SECRET_KEY: "" }), "/api/class/checkout", { id: cls.id });
check("without Stripe there's no school plan", r.status === 503, r.status);
r = await T.post(env(), "/api/class/checkout", { id: cls.id });
const sessUrl = r.json && r.json.url;
check("the teacher gets a Stripe page to pay", r.status === 200 && /\/pay\/cs_/.test(sessUrl || ""), r.json);
const call = state.stripeCalls.filter(c => c.path === "/v1/checkout/sessions").pop();
check("it's one payment of $49 for this class, not a subscription", call.params.mode === "payment" && call.params["line_items[0][price_data][unit_amount]"] === "4900" && call.params["metadata[class_id]"] === cls.id && /Saturday beginners/.test(call.params["line_items[0][price_data][product_data][name]"]), call.params);
check("and it comes back to the class", call.params.success_url === "https://alefba.example/?school=done&class=" + cls.id, call.params.success_url);
r = await T.post(env(), "/api/class/view", { id: cls.id });
check("before paying: no plan yet, a payment is started", r.json.class.paidUntil === 0 && r.json.class.pending === true, r.json.class);
r = await T.post(env(), "/api/class/checkout", { id: cls.id });
const firstId = /cs_\d+/.exec(sessUrl)[0];
check("starting again closes the first payment page", r.status === 200 && state.stripe.sessions[firstId].status === "expired", state.stripe.sessions[firstId].status);
const loc = await pay(r.json.url);
check("paying returns to the website", /school=done/.test(loc || ""), loc);
r = await T.post(env(), "/api/class/view", { id: cls.id });
const yr = r.json.class.paidUntil - Date.now();
check("after paying, the class has the school plan for a year", yr > 364 * 864e5 && yr < 366 * 864e5 && r.json.class.pending === false, r.json.class);
r = await T.post(env(), "/api/class/view", { id: cls.id });
const yr2 = r.json.class.paidUntil - Date.now();
check("checking again doesn't add another year", yr2 < 366 * 864e5, yr2 / 864e5);
r = await kid.post(env(), "/api/class/progress", { token: kidToken, progress: { done: ["a1-1"], days: [today()], streak: 1, best: 1, letters: 2, words: 0, today: today() } });
check("the learner's device is told the class has the plan, until when", r.status === 200 && r.json.class.fullUntil > Date.now() + 364 * 864e5, r.json);
r = await kid.post(env(), "/api/class/mine", { token: kidToken });
check("(also when it just checks in)", r.json.class.fullUntil > Date.now(), r.json);
r = await T.post(env(), "/api/class/checkout", { id: cls.id });
check("a class with most of its year left can't be paid for again yet", r.status === 409 && r.json.error === "has_plan", r.json);
r = await T.post(env(), "/api/class/list", {});
check("the class list shows the plan", r.json.classes[0].paidUntil > Date.now(), r.json.classes);
db.x("UPDATE classes SET paid_until = ? WHERE id = ?", Date.now() + 20 * 864e5, cls.id);
r = await T.post(env(), "/api/class/checkout", { id: cls.id });
check("near the end of the year, another year can be added", r.status === 200, r.json);
await pay(r.json.url);
r = await T.post(env(), "/api/class/list", {});
const left = (r.json.classes[0].paidUntil - Date.now()) / 864e5;
check(`the new year is added to the days still left (${Math.round(left)} days now)`, left > 384 && left < 386, left);
db.x("UPDATE classes SET paid_until = ? WHERE id = ?", Date.now() - 1000, cls.id);
r = await kid.post(env(), "/api/class/mine", { token: kidToken });
check("once the year is over, learners are told", r.json.class.fullUntil === 0, r.json);
// review fixes: a promotion code that covers it all; a teacher who never comes back; a payment still on its way
r = await T.post(env(), "/api/class/checkout", { id: cls.id });
let cs = state.stripe.sessions[/cs_\d+/.exec(r.json.url)[0]];
cs.status = "complete"; cs.payment_status = "no_payment_required";
r = await kid.post(env(), "/api/class/mine", { token: kidToken });
check("paid with a 100% promotion code: the class gets its year, and the learner's own check-in is enough to apply it", r.json.class.fullUntil > Date.now() + 364 * 864e5, r.json);
db.x("UPDATE classes SET paid_until = ? WHERE id = ?", Date.now() + 10 * 864e5, cls.id);
r = await T.post(env(), "/api/class/checkout", { id: cls.id });
cs = state.stripe.sessions[/cs_\d+/.exec(r.json.url)[0]];
cs.status = "complete"; cs.payment_status = "unpaid"; // a bank payment: done at Stripe, money still on its way
r = await T.post(env(), "/api/class/checkout", { id: cls.id });
check("while a payment is still on its way, a new one can't replace it", r.status === 409 && r.json.error === "pending_payment", r.json);
r = await T.post(env(), "/api/class/delete", { id: cls.id });
check("and the class can't be deleted until it's confirmed", r.status === 409 && r.json.error === "pending_payment", r.json);
cs.payment_status = "paid";
r = await T.post(env(), "/api/class/view", { id: cls.id });
check("once it arrives, the year is added", (r.json.class.paidUntil - Date.now()) / 864e5 > 370, (r.json.class.paidUntil - Date.now()) / 864e5);
db.x("UPDATE classes SET checkout_id = ? WHERE id = ?", "live:cs_999", cls.id);
r = await T.post(env(), "/api/class/view", { id: cls.id });
check("a payment page from Stripe's other mode (live vs test) doesn't stay 'pending' forever", r.json.class.pending === false, r.json.class);
db.x("UPDATE classes SET paid_until = ? WHERE id = ?", Date.now() - 1000, cls.id);
r = await T.post(env(), "/api/class/checkout", { id: cls.id });
const openId = /cs_\d+/.exec(r.json.url)[0];
r = await T.post(env(), "/api/class/delete", { id: cls.id });
check("deleting a class closes a payment page still open for it", r.status === 200 && state.stripe.sessions[openId].status === "expired", state.stripe.sessions[openId].status);

servers.forEach(s => s.close());
console.log(`\n${pass} of ${pass + fail} passed`);
process.exit(fail ? 1 : 0);
