// Your name in Persian (/api/name): anyone can ask, only names are accepted, each name is asked of Claude once and kept,
// and there are limits per visitor and for the whole site each day. Against pretend Claude.
import fs from "node:fs";
import http from "node:http";
import crypto from "node:crypto";
import { D1 } from "./d1shim.mjs";
import { state, TURNSTILE, claudeServer, stripeServer, resendServer, turnstileServer } from "./mocks.mjs";
const worker = (await import("/home/claude/alefba-site/_worker.js?v=" + Date.now())).default;
const PARENTS = fs.readFileSync("/home/claude/alefba-site/parents.html", "utf8");
const ADULTS = fs.readFileSync("/home/claude/alefba-site/adults.html", "utf8");
const servers = [claudeServer(39797), stripeServer(39798), resendServer(39799), turnstileServer(39800)];

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
const FULL = { ANTHROPIC_API_KEY: KEY, ANTHROPIC_BASE_URL: "http://127.0.0.1:39797", RESEND_API_KEY: "re_" + "test_0123456789abcdefghij", RESEND_BASE_URL: "http://127.0.0.1:39799",
  STRIPE_SECRET_KEY: "sk_" + "test_0123456789abcdefghij", STRIPE_BASE_URL: "http://127.0.0.1:39798", TURNSTILE_BASE_URL: "http://127.0.0.1:39800",
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
let pass = 0, fail = 0;
function check(name, ok, extra) { if (ok) pass++; else fail++; console.log((ok ? "PASS " : "FAIL ") + name + (!ok && extra !== undefined ? "  [" + JSON.stringify(extra).slice(0, 500) + "]" : "")); }
const hits = () => state.claudeHits.filter(h => /name in Persian script/.test(String(h.body.system || ""))).length;
const A = new Agent();
let r = await A.post(env(), "/api/name", { name: "Sara" });
check("a name comes back in Persian, with no sign-in", r.status === 200 && r.json.fa === "سارا" && r.json.alt === null && r.json.name === "Sara", r.json);
const h1 = state.claudeHits[state.claudeHits.length - 1];
check("one small Claude call, with only the name sent", hits() === 1 && h1.body.model === "claude-haiku-5-5" && h1.body.max_tokens <= 200 && h1.body.messages.length === 1 && h1.body.messages[0].content === "Sara", h1.body.messages);
r = await new Agent().post(env(), "/api/name", { name: "  sara " });
check("the same name again (any capitals or spaces) costs nothing: no second call", r.status === 200 && r.json.fa === "سارا" && hits() === 1, [r.json, hits()]);
r = await A.post(env(), "/api/name", { name: "Elan" });
check("a second spelling comes too when there is one", r.status === 200 && r.json.fa === "ایلان" && r.json.alt === "الان", r.json);
r = await A.post(env(), "/api/name", { name: "Mary Jane" });
check("a two-part name keeps its space", r.status === 200 && r.json.fa === "مری جین", r.json);
r = await A.post(env(), "/api/name", { name: "Olivia" });
check("Arabic letter forms are turned into Persian ones", r.status === 200 && r.json.fa === "اولیویا", r.json);
r = await A.post(env(), "/api/name", { name: "Noah" });
check("anything that isn't Persian letters is never passed on", r.status === 422 && r.json.error === "not_a_name", r.json);
r = await A.post(env(), "/api/name", { name: "Stupidhead" });
check("not a name: turned away", r.status === 422 && r.json.error === "not_a_name", r.json);
const before = hits();
r = await new Agent().post(env(), "/api/name", { name: "stupidhead" });
check("and remembered, so asking again costs nothing", r.status === 422 && hits() === before, hits());
for (const bad of ["", "a".repeat(25), "hello there, how are you today?", "<b>x</b>", "123", "سارا", "Sara!"]) {
  r = await new Agent().post(env(), "/api/name", { name: bad });
  check(`only short names in English letters are accepted (${JSON.stringify(bad).slice(0, 20)})`, r.status === 400 && r.json.error === "bad_name", r.json);
}
r = await new Agent().post(env(), "/api/name", { name: "José" });
check("accented letters are fine", r.status === 422 || r.status === 200, r.json);
const spent = db.q("SELECT micro FROM spend WHERE k = ?", new Date().toISOString().slice(0, 10) + ":names")[0];
check("names count against their own small daily budget", spent && spent.micro > 0 && spent.micro < 3000, spent);
// one visitor: about 10 names a minute
const B = new Agent(); let limited = false;
for (let i = 0; i < 12; i++) { r = await B.post(env(), "/api/name", { name: "Name" + "abcdefghijkl"[i] }); if (r.status === 429) { limited = true; break; } }
check("one visitor can't ask for names without end", limited && r.json.error === "rate_limited", r.json);
// the whole site: once the day's names budget is used up, it says come back tomorrow
db.x("INSERT INTO spend (k, micro) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET micro = excluded.micro", new Date().toISOString().slice(0, 10) + ":names", 10 ** 9);
r = await new Agent().post(env(), "/api/name", { name: "Ava" });
check("when the day's budget is used up: come back tomorrow", r.status === 429 && r.json.error === "busy_today", r.json);
r = await new Agent().post(env(), "/api/name", { name: "Sara" });
check("but names already asked still work", r.status === 200 && r.json.fa === "سارا", r.json);
r = await new Agent().post(env(), "/api/usage", { e: ["name_open", "name_made", "name_share", "name_start"], d: new Date().toISOString().slice(0, 10) });
const u = db.q("SELECT name, n FROM usage WHERE name LIKE 'name_%' ORDER BY name");
check("the name page's visits and shares are counted", u.length === 4, u);
servers.forEach(s => s.close());
console.log(`${pass} of ${pass + fail} passed`);
process.exit(fail ? 1 : 0);
