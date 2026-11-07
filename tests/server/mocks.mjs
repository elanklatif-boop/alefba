// Pretend versions of Claude, Stripe and Resend for testing the website without real accounts or money.
import http from "node:http";

export const state = {
  claudeMode: null,            // null = answer by message content (BREAK, REFUSE, LIMIT); or a fixed failure mode
  claudeHits: [], broke: false,
  stripeKeyPrefix: "sk_test_", chargesEnabled: true,
  stripe: { products: {}, prices: {}, customers: {}, sessions: {}, subs: {}, configs: {}, portals: {}, idem: {} },
  stripeCalls: [], failUpgrade: false, failCancel: false, failList: false, failExpire: false, failDeleteCustomer: false, claudeDelay: 0,
  emails: [], verifiedDomains: ["alefba.example"], resendFail: false,
  turnstileCalls: [],
};
export const TURNSTILE = { site: "1x00000000000000000000AA", secret: "1x0000000000000000000000000000000AA", token: "XXXX.DUMMY.TOKEN.XXXX" };
let n = 0;
const nid = p => `${p}_${String(++n).padStart(5, "0")}`;
const body = req => new Promise(r => { let b = ""; req.on("data", c => (b += c)); req.on("end", () => r(b)); });
const send = (res, status, obj, headers = {}) => { res.writeHead(status, { "content-type": "application/json", ...headers }); res.end(JSON.stringify(obj)); };
// like the real API with stream set: server-sent events, the text in small pieces (a pause between them if asked)
async function sse(res, msg, gap = 0) {
  res.writeHead(200, { "content-type": "text/event-stream" });
  const ev = (type, o) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...o })}\n\n`);
  ev("message_start", { message: { id: "msg_test", type: "message", role: "assistant", content: [], usage: { input_tokens: (msg.usage || {}).input_tokens || 10, output_tokens: 1 } } });
  const text = ((msg.content || [])[0] || {}).text;
  if (text != null) {
    ev("content_block_start", { index: 0, content_block: { type: "text", text: "" } });
    for (let i = 0; i < text.length; i += 7) { ev("content_block_delta", { index: 0, delta: { type: "text_delta", text: text.slice(i, i + 7) } }); if (gap) await new Promise(r => setTimeout(r, gap)); }
    ev("content_block_stop", { index: 0 });
  }
  if (state.claudeStreamCut) { res.end(); return; } // ends early, without the closing events
  ev("message_delta", { delta: { stop_reason: msg.stop_reason }, usage: { output_tokens: (msg.usage || {}).output_tokens || 10 } });
  ev("message_stop", {});
  res.end();
}
const err = (type, message, details) => ({ type: "error", error: { type, message, ...(details ? { details } : {}) }, request_id: "req_test" });

// ---------- Claude ----------
export function claudeServer(port = 9787) {
  return http.createServer(async (req, res) => {
    const raw = await body(req), b = JSON.parse(raw || "{}");
    state.claudeHits.push({ headers: { auth: req.headers["authorization"], xkey: req.headers["x-api-key"], ws: req.headers["anthropic-workspace-id"], version: req.headers["anthropic-version"] }, body: b });
    const last = (b.messages || []).slice(-1)[0], text = typeof (last && last.content) === "string" ? last.content : "";
    const n = (b.messages || []).filter(m => m.role === "user").length;
    if (state.claudeDelay) await new Promise(r => setTimeout(r, state.claudeDelay));
    const mode = state.claudeMode || (text.includes("LIMIT") ? "my_limit" : text.includes("REFUSE") ? "refusal" : text.includes("BREAK") && !state.broke ? "break" : "ok");
    if (mode === "break") { state.broke = true; return send(res, 500, err("api_error", "Internal server error")); }
    const fail = {
      my_limit: [400, err("invalid_request_error", "You have reached your specified API usage limits. You will regain access on 2026-11-01 at 00:00 UTC.")],
      tier_cap: [429, err("rate_limit_error", "You have reached your API usage limits: your organization has crossed its monthly API usage threshold.", { error_code: "enforced_spend_limit_reached" })],
      rate: [429, err("rate_limit_error", "This request would exceed your organization's rate limit.")],
      credit: [400, err("invalid_request_error", "Your credit balance is too low to access the Anthropic API.")],
      bad_key: [401, err("authentication_error", "invalid x-api-key")],
      ws_required: [400, err("invalid_request_error", "anthropic-workspace-id is required when authenticating with an identity-linked API key; send the id of the workspace this request acts in.")],
      overloaded: [529, err("overloaded_error", "Overloaded")],
      not_found: [404, err("not_found_error", "model: claude-haiku-5-5")],
    }[mode];
    if (fail) return send(res, fail[0], fail[1]);
    if (mode === "refusal") return b.stream ? sse(res, { content: [], stop_reason: "refusal" }) : send(res, 200, { content: [], stop_reason: "refusal" });
    if (mode === "garbled") return send(res, 200, { content: [{ type: "text", text: "{not json" }], stop_reason: "end_turn" });
    // a name in Persian (learnalefba.com/name)
    if (/name in Persian script/.test(String(b.system || ""))) {
      const N = { sara: { ok: true, fa: "سارا", alt: "" }, elan: { ok: true, fa: "ایلان", alt: "الان" }, olivia: { ok: true, fa: "اولیويا", alt: "" }, "mary jane": { ok: true, fa: "مری جین", alt: "" }, noah: { ok: true, fa: "نوح<script>", alt: "" } }[text.toLowerCase()] || { ok: false, fa: "", alt: "" };
      return send(res, 200, { content: [{ type: "text", text: JSON.stringify(N) }], stop_reason: "end_turn", usage: { input_tokens: 90, output_tokens: 20 } });
    }
    // a gloss (what did I just say?): a tiny request with its own system prompt
    if (/Finglish/.test(String(b.system || "")) && /"translit"/.test(String(b.system || "")) && !Array.isArray(b.system)) {
      const lang = (/in (English|French|German|Swedish|Mandarin Chinese[^,.]*)/.exec(String(b.system)) || [])[1] || "English";
      return send(res, 200, { content: [{ type: "text", text: JSON.stringify({ translit: "man ghahve dust dâram", meaning: lang === "French" ? "J'aime le café" : "I like coffee" }) }], stop_reason: "end_turn", usage: { input_tokens: 60, output_tokens: 20 } });
    }
    const reply = { fa: "آفرین! خیلی خوب بود.", translit: "âfarin! kheyli khub bud.", en: "Well done!", written: "آفرین! خیلی خوب بود.", written_translit: "âfarin! kheyli khub bud.",
      feedback: n === 2 ? { note: "Nice! People often say it like this:", better_fa: "خوبم، مرسی.", better_translit: "khubam, mersi." } : null,
      suggestions: [{ fa: "مرسی!", translit: "mersi!", en: "Thanks!" }, { fa: "خوبم.", translit: "khubam.", en: "I'm good." }, { fa: "خداحافظ!", translit: "khodâhâfez!", en: "Bye!" }],
      new_words: [], goals_done: n >= 3 ? [1, 2] : [1], pace: "same", done: n >= 4 };
    // like the real API: a field the reply shape doesn't allow can't appear, and a required one always does
    const shape = ((b.output_config || {}).format || {}).schema || {};
    if ((shape.required || []).includes("you_said")) reply.you_said = n > 1 ? { translit: "salâm!", en: "Hello!" } : null;
    const msg = { id: "msg_test", type: "message", role: "assistant", content: [{ type: "text", text: JSON.stringify(reply) }], stop_reason: "end_turn", usage: { input_tokens: 10, output_tokens: 10 } };
    if (b.stream) return sse(res, msg, state.claudeStreamGap || 0);
    send(res, 200, msg);
  }).listen(port, "127.0.0.1");
}

// ---------- Stripe ----------
export function stripeServer(port = 9788) {
  const S = state.stripe;
  const page = (res, html) => { res.writeHead(200, { "content-type": "text/html; charset=utf-8" }); res.end(`<!doctype html><meta name="viewport" content="width=device-width"><body style="font-family:sans-serif;padding:20px">${html}</body>`); };
  return http.createServer(async (req, res) => {
    const u = new URL(req.url, `http://127.0.0.1:${port}`), raw = await body(req);
    // the pretend checkout and billing pages a parent would see
    let m;
    if ((m = /^\/pay\/(cs_\d+)$/.exec(u.pathname))) {
      const cs = S.sessions[m[1]];
      if (!cs) return page(res, "No such checkout");
      if (cs.status !== "open") return page(res, `<h1 id="closed">This checkout has ${cs.status === "expired" ? "expired" : "been paid"}</h1>`);
      if (cs.mode === "payment") { // a one-time payment (the school plan)
        if (req.method === "GET") return page(res, `<h1>Pretend Stripe checkout</h1><p id="what">${cs.name}: $${(cs.amount / 100).toFixed(2)}</p><form method="post"><button id="payBtn">Pay</button></form><a id="backLink" href="${cs.cancel_url}">Back</a>`);
        cs.status = "complete"; cs.payment_status = "paid";
        res.writeHead(303, { location: cs.success_url }); return res.end();
      }
      if (req.method === "GET") return page(res, `<h1>Pretend Stripe checkout</h1><p id="what">${S.prices[cs.price].nickname}: $${(S.prices[cs.price].unit_amount / 100).toFixed(2)} a month</p><form method="post"><button id="payBtn">Subscribe</button></form><a id="backLink" href="${cs.cancel_url}">Back</a>`);
      const sub = { id: nid("sub"), object: "subscription", customer: cs.customer, status: "active", cancel_at_period_end: false, metadata: { ...cs.sub_meta }, items: { object: "list", data: [{ id: nid("si"), price: S.prices[cs.price] }] } };
      S.subs[sub.id] = sub; cs.status = "complete";
      res.writeHead(303, { location: cs.success_url }); return res.end();
    }
    if ((m = /^\/portal\/(bps_\d+)(\/cancel|\/end)?$/.exec(u.pathname))) {
      const ps = S.portals[m[1]];
      if (!ps) return page(res, "No such portal session");
      const subs = Object.values(S.subs).filter(x => x.customer === ps.customer && x.status !== "canceled");
      if (req.method === "POST") { for (const x of subs) { if (m[2] === "/end") x.status = "canceled"; else x.cancel_at_period_end = true; } res.writeHead(303, { location: `/portal/${ps.id}` }); return res.end(); }
      return page(res, `<h1>Pretend Stripe billing</h1><p id="subs">${subs.map(x => `${x.items.data[0].price.nickname}${x.cancel_at_period_end ? " (cancels at the end of the month)" : ""}`).join(", ") || "No plan"}</p>` +
        `<form method="post" action="/portal/${ps.id}/cancel"><button id="cancelBtn">Cancel plan</button></form><form method="post" action="/portal/${ps.id}/end"><button id="endBtn">End now (test)</button></form><a id="returnLink" href="${ps.return_url}">Return to Alefba</a>`);
    }
    if (!u.pathname.startsWith("/v1/")) { res.writeHead(404); return res.end(); }
    const auth = String(req.headers["authorization"] || "");
    state.stripeCalls.push({ method: req.method, path: u.pathname, auth, idem: req.headers["idempotency-key"] || null, params: Object.fromEntries(new URLSearchParams(req.method === "GET" || req.method === "DELETE" ? u.search : raw)) });
    if (!auth.startsWith("Bearer " + state.stripeKeyPrefix)) return send(res, 401, { error: { type: "invalid_request_error", message: "Invalid API Key provided" } });
    const p = new URLSearchParams(req.method === "GET" || req.method === "DELETE" ? u.search : raw);
    const path = u.pathname.slice(3);
    const list = data => ({ object: "list", data, has_more: false });
    if (req.method === "GET" && path === "/account") return send(res, 200, { id: "acct_test", object: "account", charges_enabled: state.chargesEnabled, details_submitted: true });
    if (req.method === "GET" && path === "/prices") {
      const keys = [...p.entries()].filter(([k]) => k.startsWith("lookup_keys")).map(([, v]) => v);
      return send(res, 200, list(Object.values(S.prices).filter(x => x.active && keys.includes(x.lookup_key))));
    }
    if (req.method === "POST" && path === "/products") { const pr = { id: nid("prod"), object: "product", name: p.get("name") }; S.products[pr.id] = pr; return send(res, 200, pr); }
    if (req.method === "POST" && path === "/prices") {
      const key = p.get("lookup_key"), holder = Object.values(S.prices).find(x => x.lookup_key === key);
      if (holder && p.get("transfer_lookup_key") !== "true") return send(res, 400, { error: { type: "invalid_request_error", message: "A price with this lookup_key already exists." } });
      if (holder) holder.lookup_key = null;
      if (!S.products[p.get("product")]) return send(res, 400, { error: { type: "invalid_request_error", message: "No such product" } });
      const pr = { id: nid("price"), object: "price", active: true, product: p.get("product"), currency: p.get("currency"), unit_amount: Number(p.get("unit_amount")), recurring: { interval: p.get("recurring[interval]") }, lookup_key: key, nickname: p.get("nickname"), metadata: { alefba_plan: p.get("metadata[alefba_plan]") } };
      S.prices[pr.id] = pr; return send(res, 200, pr);
    }
    if (req.method === "POST" && path === "/customers") {
      const key = req.headers["idempotency-key"];
      if (key && S.idem[key]) return send(res, 200, S.customers[S.idem[key]]); // the same request again gets the same customer
      const c = { id: nid("cus"), object: "customer", email: p.get("email"), metadata: { family_id: p.get("metadata[family_id]") } }; S.customers[c.id] = c;
      if (key) S.idem[key] = c.id;
      return send(res, 200, c);
    }
    if (req.method === "POST" && path === "/checkout/sessions" && p.get("mode") === "payment") {
      const cust = p.get("customer"), amount = Number(p.get("line_items[0][price_data][unit_amount]"));
      if (!S.customers[cust] || !(amount > 0) || p.get("line_items[0][price_data][currency]") !== "usd" || !p.get("line_items[0][price_data][product_data][name]") || !p.get("success_url") || !p.get("cancel_url")) return send(res, 400, { error: { type: "invalid_request_error", message: "Bad checkout request" } });
      const cs = { id: nid("cs"), object: "checkout.session", mode: "payment", url: `http://127.0.0.1:${port}/pay/`, customer: cust, amount, name: p.get("line_items[0][price_data][product_data][name]"), metadata: { class_id: p.get("metadata[class_id]"), ...(p.get("metadata[alefba_kind]") ? { alefba_kind: p.get("metadata[alefba_kind]") } : {}) }, success_url: p.get("success_url"), cancel_url: p.get("cancel_url"), status: "open", payment_status: "unpaid" };
      cs.url += cs.id; S.sessions[cs.id] = cs; return send(res, 200, cs);
    }
    if (req.method === "GET" && (m = /^\/checkout\/sessions\/(cs_\d+)$/.exec(path))) {
      const cs = S.sessions[m[1]];
      return cs ? send(res, 200, cs) : send(res, 404, { error: { type: "invalid_request_error", message: "No such checkout.session" } });
    }
    if (req.method === "POST" && path === "/checkout/sessions") {
      const price = p.get("line_items[0][price]"), cust = p.get("customer");
      if (p.get("mode") !== "subscription" || !S.prices[price] || !S.customers[cust] || !p.get("success_url") || !p.get("cancel_url")) return send(res, 400, { error: { type: "invalid_request_error", message: "Bad checkout request" } });
      const exp = Number(p.get("expires_at"));
      if (p.get("expires_at") && (exp < Date.now() / 1000 + 1800 || exp > Date.now() / 1000 + 86400)) return send(res, 400, { error: { type: "invalid_request_error", message: "expires_at must be between 30 minutes and 24 hours from now" } });
      const cs = { id: nid("cs"), object: "checkout.session", url: `http://127.0.0.1:${port}/pay/`, customer: cust, price, success_url: p.get("success_url"), cancel_url: p.get("cancel_url"), promo: p.get("allow_promotion_codes"), sub_meta: { family_id: p.get("subscription_data[metadata][family_id]") }, status: "open", expires_at: exp || null };
      cs.url += cs.id; S.sessions[cs.id] = cs; return send(res, 200, cs);
    }
    if ((m = /^\/checkout\/sessions\/(cs_\d+)\/expire$/.exec(path)) && req.method === "POST") {
      if (state.failExpire) return send(res, 500, { error: { type: "api_error", message: "Something went wrong" } });
      const cs = S.sessions[m[1]];
      if (!cs) return send(res, 404, { error: { type: "invalid_request_error", message: "No such checkout.session" } });
      if (cs.status !== "open") return send(res, 400, { error: { type: "invalid_request_error", message: "Only Checkout Sessions with a status of open can be expired." } });
      cs.status = "expired"; return send(res, 200, cs);
    }
    if ((m = /^\/customers\/(cus_\d+)$/.exec(path)) && req.method === "DELETE") {
      if (state.failDeleteCustomer) return send(res, 500, { error: { type: "api_error", message: "Something went wrong" } });
      const c = S.customers[m[1]];
      if (!c || c.deleted) return send(res, 404, { error: { type: "invalid_request_error", message: "No such customer" } });
      c.deleted = true; for (const x of Object.values(S.subs)) if (x.customer === c.id) x.status = "canceled";
      return send(res, 200, { id: c.id, object: "customer", deleted: true });
    }
    if (req.method === "GET" && path === "/subscriptions" && state.failList) return send(res, 500, { error: { type: "api_error", message: "Something went wrong" } });
    if (req.method === "GET" && path === "/subscriptions") return send(res, 200, list(Object.values(S.subs).filter(x => x.customer === p.get("customer") && (p.get("status") === "all" || x.status !== "canceled"))));
    if ((m = /^\/subscriptions\/(sub_\d+)$/.exec(path))) {
      const sub = S.subs[m[1]];
      if (!sub) return send(res, 404, { error: { type: "invalid_request_error", message: "No such subscription" } });
      if (req.method === "GET") return send(res, 200, sub);
      if (req.method === "DELETE") {
        if (state.failCancel) return send(res, 500, { error: { type: "api_error", message: "Something went wrong" } });
        sub.status = "canceled"; return send(res, 200, sub);
      }
      if (req.method === "POST") {
        const item = sub.items.data.find(i => i.id === p.get("items[0][id]")), price = S.prices[p.get("items[0][price]")];
        if (!item || !price) return send(res, 400, { error: { type: "invalid_request_error", message: "Bad update" } });
        sub.proration = p.get("proration_behavior"); sub.payment_behavior = p.get("payment_behavior");
        // a declined card with a pending update: nothing changes until it's paid
        if (state.failUpgrade && sub.payment_behavior === "pending_if_incomplete") return send(res, 200, { ...sub, pending_update: { expires_at: Math.floor(Date.now() / 1000) + 82800, subscription_items: [{ id: item.id, price: price.id }] } });
        item.price = price; return send(res, 200, { ...sub, pending_update: null });
      }
    }
    if (req.method === "POST" && path === "/billing_portal/configurations") { const c = { id: nid("bpc"), object: "billing_portal.configuration", cancel_mode: p.get("features[subscription_cancel][mode]") }; S.configs[c.id] = c; return send(res, 200, c); }
    if (req.method === "POST" && path === "/billing_portal/sessions") {
      if (!S.configs[p.get("configuration")]) return send(res, 400, { error: { type: "invalid_request_error", message: "No configuration provided and your live mode default configuration has not been created." } });
      if (!S.customers[p.get("customer")]) return send(res, 400, { error: { type: "invalid_request_error", message: "No such customer" } });
      const ps = { id: nid("bps"), object: "billing_portal.session", customer: p.get("customer"), return_url: p.get("return_url"), url: `http://127.0.0.1:${port}/portal/` };
      ps.url += ps.id; S.portals[ps.id] = ps; return send(res, 200, ps);
    }
    send(res, 404, { error: { type: "invalid_request_error", message: "Unrecognized request URL" } });
  }).listen(port, "127.0.0.1");
}

// ---------- Resend ----------
export function resendServer(port = 9789) {
  return http.createServer(async (req, res) => {
    const u = new URL(req.url, `http://127.0.0.1:${port}`), raw = await body(req);
    if (u.pathname === "/last") { // test helper: the latest code sent to an address
      const e = state.emails.filter(x => x.to.includes(u.searchParams.get("to"))).pop();
      return send(res, 200, { code: e ? (/(\d{6})/.exec(e.subject) || [])[1] : null, count: state.emails.length });
    }
    if (!String(req.headers["authorization"] || "").startsWith("Bearer re_")) return send(res, 401, { statusCode: 401, message: "API key is invalid", name: "validation_error" });
    if (u.pathname === "/domains") return send(res, 200, { data: state.verifiedDomains.map((d, i) => ({ id: "d" + i, name: d, status: "verified" })) });
    if (u.pathname === "/emails" && req.method === "POST") {
      const b = JSON.parse(raw), dom = (/@([^\s@>]+)>?$/.exec(b.from) || [])[1];
      if (state.resendFail || !state.verifiedDomains.includes(dom)) return send(res, 403, { statusCode: 403, message: `The ${dom} domain is not verified.`, name: "validation_error" });
      const id = nid("email");
      state.emails.push({ id, from: b.from, to: b.to, subject: b.subject, text: b.text, html: b.html, scheduled_at: b.scheduled_at, headers: b.headers, reply_to: b.reply_to });
      return send(res, 200, { id });
    }
    let cm;
    if ((cm = /^\/emails\/([^/]+)\/cancel$/.exec(u.pathname)) && req.method === "POST") { // a booked email called off
      const e = state.emails.find(x => x.id === cm[1]);
      if (!e || !e.scheduled_at || e.canceled) return send(res, 422, { statusCode: 422, message: "This email can't be canceled", name: "validation_error" });
      e.canceled = true;
      return send(res, 200, { object: "email", id: e.id });
    }
    send(res, 404, { message: "not found" });
  }).listen(port, "127.0.0.1");
}

// ---------- Cloudflare Turnstile (the robot check) ----------
export function turnstileServer(port = 9790) {
  return http.createServer(async (req, res) => {
    const u = new URL(req.url, `http://127.0.0.1:${port}`), raw = await body(req);
    if (u.pathname !== "/turnstile/v0/siteverify" || req.method !== "POST") return send(res, 404, { success: false });
    let b = {};
    try { b = /json/.test(req.headers["content-type"] || "") ? JSON.parse(raw) : Object.fromEntries(new URLSearchParams(raw)); } catch (e) {}
    state.turnstileCalls.push(b);
    if (b.secret !== TURNSTILE.secret) return send(res, 200, { success: false, "error-codes": ["invalid-input-secret"] });
    if (b.response !== TURNSTILE.token) return send(res, 200, { success: false, "error-codes": ["invalid-input-response"] });
    send(res, 200, { success: true, "error-codes": [], challenge_ts: new Date().toISOString(), hostname: "alefba.example" });
  }).listen(port, "127.0.0.1");
}
