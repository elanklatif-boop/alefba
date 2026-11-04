// Alefba website server (Cloudflare Pages, "advanced mode": this file sits in the root of the uploaded folder).
// It serves the app's files, signs grown-ups in with a code sent by email, counts each family's talks
// against their plan, takes payments through Stripe, and answers the app's live talks by asking Claude.
// Keys live only here, as encrypted settings, and never reach anyone's browser. Chats are never saved.
//
// Settings (Cloudflare: the project → Settings → Variables and Secrets), then upload the site again:
//   ANTHROPIC_API_KEY   Secret: the key from the Claude Console (talks)
//   RESEND_API_KEY      Secret: the key from Resend (sign-in emails)
//   STRIPE_SECRET_KEY   Secret: the secret key from Stripe (plans and payments; without it there are free talks only)
//   TURNSTILE_SITE_KEY, TURNSTILE_SECRET_KEY   Text and Secret: Cloudflare's robot check before sign-in emails
//   EMAIL_FROM          Text: who sign-in emails come from, like Alefba <hello@alefba.app>
//   CONTACT_EMAIL       Text, optional: the email address shown on the parents page
//   Optional plan and safety settings: FREE_TALKS, BASIC_TALKS, PRICE_BASIC, PRICE_UNLIMITED, PRICE_YEARLY (unlimited for a year, default 39), UNLIMITED_PER_DAY,
//     DAILY_BUDGET (dollars of Claude use a day for everyone, default 5), FREE_DAILY_BUDGET (for all free talks together,
//     default 2, so free use can never pause paying families), FAMILY_DAILY_BUDGET (per family, default 0.40),
//     EMAIL_DAILY_LIMIT (sign-in emails a day, default 90), ANTHROPIC_WORKSPACE_ID (only if the key isn't tied to a workspace)
//   HEAR_PER_DAY        Text, optional: how many times one family can say something out loud a day (default 300)
//   AZURE_SPEECH_KEY, AZURE_SPEECH_REGION   Secret and Text, optional: Microsoft's Persian voices (Dilara and Farid) for
//     spoken conversations, and Microsoft's Persian speech-to-text for the microphone (better than Whisper at short
//     Persian phrases; Whisper stays as the back-up). The region is the one the Speech resource was made in, like eastus.
//     Without them, talks are read aloud only on devices that have their own Persian voice.
//   SAY_PER_DAY         Text, optional: how many lines one family can have read aloud a day (default 600)
// Bindings (Settings → Bindings): a D1 database with the variable name DB, and Workers AI with the variable
//   name AI (speaking practice for families with a plan: their voice is turned into text, then forgotten).
// To check the setup, open /api/check on the website.
//
// Progress on every device: once a signed-in grown-up turns it on, each learner's progress (their first name or
// nickname, lessons, scores and practice days, never anything from the talks) is kept with the family's account, so it
// shows on any device where they sign in. Turning it off deletes those copies. PRICE_SCHOOL (default 49) is the price of a
// school plan: one class, every learner in it gets all the levels, for a year, paid once (it doesn't renew by itself).
//
// Reminder emails: after a lesson, a grown-up can ask for one email the next day when the next lesson is ready (see
// "the next-day email" below). They come only the day after a lesson, and every one has a one-click way to stop them.
//
// Classes (teacher mode): a signed-in grown-up can make a class, which gets a 6-letter code. Learners join with the
// code and a first name or nickname, after a grown-up says yes on the device. The class then keeps that name and a
// summary of progress (which lessons are done, which days had practice, the streak), so the teacher can see it and
// assign lessons. Nothing from the talks is ever shared. Leaving the class deletes the learner's row.

const MODEL = "claude-haiku-5-5";
const LIMITS = {
  turns: 24,            // messages in one request (a talk has at most 19)
  childChars: 400,      // one message from a child
  firstChars: 12000,    // the app's instructions for the character (the longest is about 8,400)
  firstPersian: 2500,   // Persian letters in those instructions (at most about 900)
  firstOther: 200,      // letters from other alphabets in them (at most about 10)
  assistantChars: 6000, // one earlier reply, as the app sends it back (they're usually about 1,500)
  assistantOther: 40,   // letters in a reply from alphabets the app doesn't use
  totalChars: 60000,    // the whole request (a long talk is usually under 30,000)
  totalBytes: 80000,    // the whole request in bytes, which keeps it far below Claude's long-prompt prices
  perMinute: 20,        // requests from one connection per minute
  perHour: 150,         // requests from one connection per hour
  signinsPerDay: 10,    // sign-in emails asked for from one internet address (or IPv6 network) a day
};
const FREE_LEVELS = 3;          // levels of lessons free without a plan (the alphabet is always free); the app has the same number
const HEAR_MODEL = "@cf/openai/whisper-large-v3-turbo"; // Cloudflare's own speech-to-text, run inside Cloudflare
const HEAR_MAX_BYTES = 400000;  // one clip: about 12 seconds of the app's recording format, far more than one sentence
const HEAR_MICRO = 120;         // what one clip can cost at most, in millionths of a dollar ($0.0005 a minute)
const SAY_VOICES = { f: "fa-IR-DilaraNeural", m: "fa-IR-FaridNeural" }; // Microsoft's Persian voices: the app's recordings use Dilara
const SAY_MAX_CHARS = 300;      // one line read aloud (a character's reply is usually under 120)
const SAY_MICRO_PER_CHAR = 16;  // Azure's neural voices cost $15 for a million letters; counted a little high
const SAY_CACHE_DAYS = 30;      // a line that was read aloud once is kept, so the same line costs nothing the next time
const MAX_TOKENS = 1500;       // the longest reply Claude may write
const PROMPT_EXTRA = 4000;     // tokens for the server's rules and the reply shape, generously
const TALK_REQUESTS = 16;      // requests one talk may make: up to 9 messages, plus retries
const TALK_HOURS = 3;          // how long one talk stays open
const CODE_MINUTES = 10, CODE_TRIES = 5, CODES_PER_HOUR = 5, CODE_GAP_MS = 20e3;
const SESSION_DAYS = 400;      // a device stays signed in this long after its last visit
const PLAN_CHECK_HOURS = 6;    // how often a family's plan is checked with Stripe
const LIVE_STATUSES = ["active", "trialing", "past_due"];                                // a plan that gives talks
const OPEN_STATUSES = ["active", "trialing", "past_due", "unpaid", "incomplete", "paused"]; // anything that could still charge
const LOOKUP = { basic: "alefba_basic_monthly", unlimited: "alefba_unlimited_monthly", yearly: "alefba_unlimited_yearly" };
const PLAN_NAMES = ["basic", "unlimited", "yearly"];
const isPlan = p => PLAN_NAMES.includes(p);
// What a plan gives: the yearly plan is the unlimited one, paid once a year.
const talksOf = plan => (plan === "yearly" ? "unlimited" : plan);
const RANK = { basic: 1, unlimited: 2, yearly: 3 };
// Claude Haiku 5.5 prices, dollars per million tokens, for prompts up to 100,000 tokens (above that, five times as much)
const PRICE = { in: 0.10, write: 0.125, read: 0.01, out: 0.50 };

// The plans and safety limits, with defaults that the settings can change.
function plans(env) {
  const money = (v, d) => { const n = Math.round(parseFloat(String(v == null ? "" : v).replace(/[$\s]/g, "")) * 100); return Number.isFinite(n) && n >= 50 && n <= 100000 ? n : d; };
  const micro = (v, d) => { const n = Math.round(parseFloat(String(v == null ? "" : v).replace(/[$\s]/g, "")) * 1e6); return Number.isFinite(n) && n > 0 && n <= 1e10 ? n : d; };
  const count = (v, d, max) => { const n = parseInt(v, 10); return Number.isFinite(n) && n >= 0 && n <= max ? n : d; };
  return {
    free: count(env.FREE_TALKS, 3, 100),
    basicTalks: count(env.BASIC_TALKS, 20, 1000),
    perDay: count(env.UNLIMITED_PER_DAY, 30, 1000),
    basic: money(env.PRICE_BASIC, 500),
    unlimited: money(env.PRICE_UNLIMITED, 649),
    yearly: money(env.PRICE_YEARLY, 3900),                  // unlimited talks, paid once a year
    school: money(env.PRICE_SCHOOL, 4900),                  // one class: all the levels for every learner in it, for a year
    dailyBudget: micro(env.DAILY_BUDGET, 5e6),            // millionths of a dollar a day, everyone together
    freeBudget: micro(env.FREE_DAILY_BUDGET, 2e6),        // millionths of a dollar a day, all free talks together
    familyBudget: micro(env.FAMILY_DAILY_BUDGET, 4e5),    // millionths of a dollar a day, one family (a talk costs under a cent)
    emailsPerDay: count(env.EMAIL_DAILY_LIMIT, 90, 1e6),
  };
}
const dollars = c => "$" + (c % 100 ? (c / 100).toFixed(2) : String(c / 100));

// The server's own rules for every reply, on top of the app's instructions. They can't be changed from the browser.
const SYSTEM = [
  "You are a friendly character in Alefba, an app where children aged about 7 to 14, and adult heritage learners, practice speaking Persian. The app tells you which one you're talking to.",
  "Always keep everything suitable for young children, whoever you're talking to: no violence, scary or adult topics, no romance, no unkind words, nothing about drugs, weapons or self-harm. If the learner brings up something unsafe or upsetting, respond kindly and steer back to the scene.",
  "Protect the learner's privacy: never ask for, or encourage sharing, personal details such as their surname, address, school name, phone number, email, passwords, photos or where they live. If they share something like that, don't repeat it; say kindly that they don't need to share it.",
  "Never pretend to be a real person, never suggest meeting, and never give links.",
  "Stay in the role and scene the app describes, and reply only in the JSON shape it asks for.",
].join("\n");

// The exact shape of a reply, so the app can always read it.
const item = { type: "object", properties: { fa: { type: "string" }, translit: { type: "string" }, en: { type: "string" } }, required: ["fa", "translit", "en"], additionalProperties: false };
const SCHEMA = {
  type: "object",
  properties: {
    fa: { type: "string" }, translit: { type: "string" }, en: { type: "string" },
    written: { type: "string" }, written_translit: { type: "string" },
    feedback: { anyOf: [{ type: "null" }, { type: "object", properties: { note: { type: "string" }, better_fa: { type: "string" }, better_translit: { type: "string" } }, required: ["note", "better_fa", "better_translit"], additionalProperties: false }] },
    suggestions: { type: "array", items: item },
    new_words: { type: "array", items: item },
    goals_done: { type: "array", items: { type: "integer" } },
    pace: { type: "string", enum: ["harder", "same", "easier"] },
    done: { type: "boolean" },
    // the learner's own last message in Finglish and in their language, shown under it so they understand what they said
    you_said: { anyOf: [{ type: "null" }, { type: "object", properties: { translit: { type: "string" }, en: { type: "string" } }, required: ["translit", "en"], additionalProperties: false }] },
  },
  required: ["fa", "translit", "en", "written", "written_translit", "feedback", "suggestions", "new_words", "goals_done", "pace", "done", "you_said"],
  additionalProperties: false,
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/")) {
      try { return await api(request, env, url, ctx); }
      catch (e) { return reply({ error: "server_error" }, 500); }
    }
    if (url.pathname === "/stats") { // the usage totals: a page with a password box
      try { return await api(new Request(new URL("/api/stats", url), request), env, new URL("/api/stats", url), ctx); }
      catch (e) { return reply({ error: "server_error" }, 500); }
    }
    if (["/parents", "/parents.html", "/adults", "/adults.html", "/teachers", "/teachers.html"].includes(url.pathname)) {
      try { return await parentsPage(request, env); }
      catch (e) { /* fall back to the page as uploaded */ }
    }
    return env.ASSETS.fetch(request);
  },
};

// ---------- which services are set up ----------
function services(env) {
  const key = s => typeof s === "string" && s.trim().length > 20;
  return {
    claude: key(env.ANTHROPIC_API_KEY),
    db: !!(env.DB && typeof env.DB.prepare === "function"),
    email: key(env.RESEND_API_KEY),
    stripe: /^(sk|rk)_(test|live)_\S{8,}$/.test(String(env.STRIPE_SECRET_KEY || "").trim()),
    turnstile: key(env.TURNSTILE_SECRET_KEY) && /^[0-9A-Za-z_-]{10,100}$/.test(String(env.TURNSTILE_SITE_KEY || "").trim()),
    ai: !!(env.AI && typeof env.AI.run === "function"),
    voice: key(env.AZURE_SPEECH_KEY) && /^[a-z0-9]{3,40}$/.test(String(env.AZURE_SPEECH_REGION || "").trim().toLowerCase()),
  };
}
const talksReady = s => s.claude && s.db && s.email;
const plansReady = s => s.db && s.stripe;
const stripeMode = env => (/_live_/.test(String(env.STRIPE_SECRET_KEY || "")) ? "live" : "test");
// A local address is allowed only for testing on one's own computer, so keys can't be sent anywhere else.
function serviceURL(test, real) {
  const t = String(test || "");
  return /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(t) ? t : real;
}

async function api(request, env, url, ctx) {
  const path = url.pathname, method = request.method, s = services(env);
  if (path === "/api/check" || (path === "/api/talk" && method === "GET" && url.searchParams.has("check"))) return checkPage(request, env, url, s);
  if (method === "POST") {
    // only this website's own pages may ask
    const origin = request.headers.get("Origin");
    if (origin && origin !== url.origin) return reply({ error: "forbidden" }, 403);
  }
  if (path === "/api/reminder.ics" && method === "GET") return reminderIcs(url);
  if (s.db) await ensureSchema(env);
  if (path === "/api/nudge/stop" && (method === "GET" || url.searchParams.has("t"))) return nudgeStopPage(request, env, url, s); // the link in the email, and Gmail's one-click unsubscribe
  if (path === "/api/talk" && method === "GET") return reply({ ok: talksReady(s) });
  if (path === "/api/stats") return statsPage(request, env, url, s);
  if (path === "/api/me") return method === "GET" ? me(request, env, url, s) : reply({ error: "method_not_allowed" }, 405);
  const routes = {
    "/api/talk": talk, "/api/auth/start": authStart, "/api/auth/verify": authVerify, "/api/auth/signout": signOut,
    "/api/confirm": confirmStart, "/api/checkout": checkout, "/api/plan": changePlan, "/api/portal": portal, "/api/account/delete": deleteAccount,
    "/api/hear": hear, "/api/say": say, "/api/gloss": gloss,
    "/api/class/create": classCreate, "/api/class/list": classList, "/api/class/view": classView, "/api/class/assign": classAssign,
    "/api/class/remove": classRemove, "/api/class/delete": classDelete,
    "/api/class/join": classJoin, "/api/class/mine": classMine, "/api/class/progress": classProgress, "/api/class/leave": classLeave,
    "/api/class/checkout": classCheckout,
    "/api/usage": countUsage,
    "/api/nudge/start": nudgeStart, "/api/nudge": nudgeMove, "/api/nudge/stop": nudgeStop,
    "/api/sync": syncProgress, "/api/sync/on": syncOn, "/api/sync/off": syncOff, "/api/sync/remove": syncRemove,
  };
  const fn = routes[path];
  if (!fn) return reply({ error: "not_found" }, 404);
  if (method !== "POST") return reply({ error: "method_not_allowed" }, 405);
  const res = await fn(request, env, url, s);
  // old codes, signed-out devices and talks from months ago are cleared away now and then, by signed-in visits
  if (s.db && ctx && typeof ctx.waitUntil === "function" && res.status < 400 && Math.random() < 0.02) ctx.waitUntil(prune(env).catch(() => {}));
  return res;
}

// ---------- usage totals ----------
// How many people open the app each day, how many come back, and how many lessons are started and finished. Only
// daily totals are kept: no names, no addresses, nothing that says who did what. The page that shows them needs the
// STATS_KEY secret set in Cloudflare; without it the page doesn't exist.
const USAGE_EVENTS = ["open", "open_child", "open_adult", "open_unset", "new", "back_1", "back_2_7", "back_8_30", "back_31", "lesson_start", "lesson_done", "practice_done", "review_done", "game_done", "talk_start", "nudge_on", "from_email"];
async function countUsage(request, env, url, s) {
  if (!s.db || tooMany(request, "usage", 20, 300)) return reply({ ok: true }); // too many from one place: quietly not counted
  const body = await readJson(request, 2000), now = Date.now();
  const ev = Array.isArray(body && body.e) ? body.e.filter(x => USAGE_EVENTS.includes(x)).slice(0, 20) : [];
  if (!ev.length) return reply({ ok: true });
  // the visitor's own date, so an evening in New York isn't counted as tomorrow; it must be within a day of now
  const d = String((body && body.d) || ""), near = [-1, 0, 1].map(k => dayKey(now + k * 864e5));
  const day = near.includes(d) ? d : dayKey(now), tally = {};
  ev.forEach(e => (tally[e] = (tally[e] || 0) + 1));
  await env.DB.batch(Object.entries(tally).map(([k, n]) => env.DB.prepare("INSERT INTO usage (day, name, n) VALUES (?, ?, ?) ON CONFLICT(day, name) DO UPDATE SET n = n + excluded.n").bind(day, k, n)));
  return reply({ ok: true });
}
async function statsPage(request, env, url, s) {
  const want = String(env.STATS_KEY || "").trim();
  if (want.length < 12 || !s.db) return reply({ error: "not_found" }, 404);
  const page = (inner, status = 200) => new Response(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Alefba usage</title>
<style>body{font-family:system-ui,sans-serif;margin:16px;color:#13213f;background:#fbf7ef}h1{font-size:1.3rem}p{color:#4a5268;max-width:640px}.wrap{overflow-x:auto}table{border-collapse:collapse;font-size:.9rem}th,td{border:1px solid #d8d2c3;padding:6px 8px;text-align:right;white-space:nowrap}th{background:#efe9dc;position:sticky;top:0}td:first-child,th:first-child{text-align:left}.t td{font-weight:700;background:#f4efe4}
form{display:flex;flex-wrap:wrap;gap:8px;max-width:420px}input{flex:1;min-width:0;font:inherit;padding:10px 12px;border:1.5px solid #c9c1ae;border-radius:10px}button{font:inherit;font-weight:600;padding:10px 16px;border:0;border-radius:10px;background:#1f3d8a;color:#fff}.err{color:#a3262f}
@media (prefers-color-scheme:dark){body{background:#0b1820;color:#e4eef1}p{color:#a9bfca}th{background:#15303d}td,th{border-color:#23404e}.t td{background:#112430}input{background:#112430;color:#e4eef1;border-color:#23404e}}</style></head><body>${inner}</body></html>`,
    { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-robots-tag": "noindex", "referrer-policy": "same-origin", "x-frame-options": "DENY" } });
  const form = msg => page(`<h1>Alefba: how the app is used</h1>${msg ? `<p class=err>${msg}</p>` : ""}<form method="post" action="/stats"><input type="password" name="key" autocomplete="current-password" placeholder="Your STATS_KEY password" aria-label="Password" required><button>Show the numbers</button></form>`, msg ? 403 : 200);
  if (request.method !== "POST") return form("");
  if (tooMany(request, "stats", 10, 60)) return form("Too many tries. Wait a minute, then try again.");
  let got = "";
  try { const f = await request.formData(); got = String(f.get("key") || "").trim().slice(0, 200); } catch (e) {}
  const a = new TextEncoder().encode(await sha256(got)), b = new TextEncoder().encode(await sha256(want));
  let diff = a.length ^ b.length; for (let i = 0; i < Math.min(a.length, b.length); i++) diff |= a[i] ^ b[i];
  if (diff) return form("That's not the password. It has to match STATS_KEY in Cloudflare exactly.");
  const since = dayKey(Date.now() - 30 * 864e5);
  const rows = (await env.DB.prepare("SELECT day, name, n FROM usage WHERE day >= ? ORDER BY day DESC").bind(since).all()).results || [];
  const days = {}; rows.forEach(r => ((days[r.day] = days[r.day] || {})[r.name] = r.n));
  const cols = [["open", "Opened the app"], ["new", "New"], ["back_1", "Back the next day"], ["back_2_7", "Back after 2–7 days"], ["back_8_30", "Back after 8–30 days"], ["back_31", "Back after a month+"],
    ["open_child", "Children"], ["open_adult", "Adults"], ["open_unset", "Not chosen yet"], ["lesson_start", "Lessons started"], ["lesson_done", "Lessons finished"], ["practice_done", "Writing practice"], ["review_done", "Reviews"], ["game_done", "Games"], ["talk_start", "Talks started"], ["nudge_on", "Asked for the email"], ["from_email", "Came from the email"]];
  const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const total = k => Object.values(days).reduce((t, d) => t + (d[k] || 0), 0);
  const head = "<tr><th>Day</th>" + cols.map(c => `<th>${esc(c[1])}</th>`).join("") + "</tr>";
  const body = Object.keys(days).sort().reverse().map(d => `<tr><td>${esc(d)}</td>` + cols.map(c => `<td>${days[d][c[0]] || 0}</td>`).join("") + "</tr>").join("");
  const foot = "<tr class=t><td>Last 30 days</td>" + cols.map(c => `<td>${total(c[0])}</td>`).join("") + "</tr>";
  return page(`<h1>Alefba: how the app is used</h1><p>Daily totals only, by each learner's own date. "Opened the app" counts each learner once a day. "Back" says how long since that learner first opened it. Nothing here identifies anyone.</p>
<div class=wrap><table>${head}${foot}${body || ""}</table></div>${body ? "" : "<p>Nothing counted yet.</p>"}`);
}

// ---------- a daily reminder for the family's calendar ----------
// The app's "Add to my calendar" opens this: an event at the chosen time (the phone's own time zone), repeating every
// day, with an alert. Phones open it straight in their calendar app. Nothing is stored.
function reminderIcs(url) {
  const t = String(url.searchParams.get("t") || ""), d = String(url.searchParams.get("d") || "");
  const hm = /^([01]\d|2[0-3])([0-5]\d)$/.exec(t) ? t : "1700";
  const day = /^20\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$/.test(d) ? d : new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const now = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+/, "");
  const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Alefba//Daily reminder//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
    `UID:alefba-${crypto.randomUUID()}@learnalefba.com`, `DTSTAMP:${now}`, `DTSTART:${day}T${hm}00`, "DURATION:PT10M", "RRULE:FREQ=DAILY",
    "SUMMARY:Persian practice with Alefba", `DESCRIPTION:A few minutes of Persian today: ${url.origin}/?ref=reminder`, `URL:${url.origin}/?ref=reminder`,
    "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Time for a little Persian!", "TRIGGER:PT0M", "END:VALARM", "END:VEVENT", "END:VCALENDAR", ""].join("\r\n");
  return new Response(ics, { headers: { "content-type": "text/calendar; charset=utf-8", "content-disposition": 'inline; filename="alefba-reminder.ics"', "cache-control": "no-store" } });
}

// ---------- the next-day email ----------
// After a lesson, a grown-up can ask for an email when the next one is ready. Each finished lesson books one email for
// about a day later (Resend sends it at that time); finishing another lesson before then moves it to a day after that
// one. So nothing comes unless they practised the day before, and it stops by itself when they stop. Every email has a
// one-click way to stop them. Kept: the address, a scrambled code of the token the device holds, and the booked email's
// id and time, deleted when they stop the emails, or 60 days after the last one. Nothing about the learner.
const NUDGE_HOURS = 23;
const nudgeTimes = { perNetDay: 4, perDay: 300, movesPerDay: 30 };
const cleanNext = n => {
  n = n && typeof n === "object" ? n : {};
  const t = String(n.t || "").replace(/[<>\r\n]/g, "").trim().slice(0, 60);
  const fa = String(n.fa || "").replace(/[^؀-ۿ‌ ]/g, "").replace(/\s+/g, " ").trim().slice(0, 30);
  return { t, fa };
};
async function nudgeStart(request, env, url, s) {
  if (!s.db || !s.email) return reply({ error: "not_configured" }, 503);
  if (tooMany(request, "nudge", 3, 12)) return reply({ error: "too_many" }, 429);
  const body = await readJson(request, 2000);
  const email = cleanEmail(body && body.email);
  if (!email) return reply({ error: "bad_email" }, 400);
  if (body.agree !== true) return reply({ error: "agree" }, 400);
  const net = (await sha256("alefba-net:" + netOf(request.headers.get("CF-Connecting-IP")))).slice(0, 24), now = Date.now();
  if (!(await bump(env, `${dayKey(now)}:nudgenet:${net}`, nudgeTimes.perNetDay))) return reply({ error: "too_many" }, 429);
  const old = await env.DB.prepare("SELECT * FROM nudges WHERE email = ?").bind(email).first();
  const token = randomToken(), h = await sha256("nudge:" + token);
  // the same address asked again (another device, or after stopping): one row, a new token, and the old booking dropped
  if (old && old.email_id && old.send_at > now) await resendCancel(env, old.email_id);
  await env.DB.prepare("INSERT INTO nudges (h, email, created_at) VALUES (?, ?, ?) ON CONFLICT(email) DO UPDATE SET h = excluded.h, stopped = 0, email_id = NULL, send_at = NULL").bind(h, email, now).run();
  const row = await env.DB.prepare("SELECT * FROM nudges WHERE h = ?").bind(h).first();
  const booked = await bookNudge(env, url, row, token, cleanNext(body.next));
  if (!booked) return reply({ error: "email_failed" }, 502);
  return reply({ ok: true, token });
}
async function nudgeMove(request, env, url, s) {
  if (!s.db || !s.email) return reply({ error: "not_configured" }, 503);
  if (tooMany(request, "nudge-move", 10, 60)) return reply({ error: "too_many" }, 429);
  const body = await readJson(request, 2000);
  const token = String((body && body.token) || "");
  if (!/^[A-Za-z0-9_-]{30,60}$/.test(token)) return reply({ error: "gone" }, 404);
  const row = await env.DB.prepare("SELECT * FROM nudges WHERE h = ?").bind(await sha256("nudge:" + token)).first();
  if (!row || row.stopped) return reply({ error: "gone" }, 404);
  if (!(await bump(env, `${dayKey(Date.now())}:nudgemove:${row.h.slice(0, 20)}`, nudgeTimes.movesPerDay))) return reply({ ok: true, kept: true });
  const booked = await bookNudge(env, url, row, token, cleanNext(body.next));
  return booked ? reply({ ok: true }) : reply({ error: "email_failed" }, 502);
}
async function bookNudge(env, url, row, token, next) {
  const now = Date.now();
  if (!(await bump(env, `${dayKey(now)}:nudges`, nudgeTimes.perDay))) return false;
  if (row.email_id && row.send_at > now) await resendCancel(env, row.email_id); // the one booked after an earlier lesson
  const at = now + NUDGE_HOURS * 3600e3, stop = `${url.origin}/api/nudge/stop?t=${token}`;
  const m = nudgeMail(url, stop, next);
  let id = null;
  try {
    const res = await fetch(serviceURL(env.RESEND_BASE_URL, "https://api.resend.com") + "/emails", {
      method: "POST",
      headers: { authorization: "Bearer " + env.RESEND_API_KEY.trim(), "content-type": "application/json" },
      body: JSON.stringify({ from: nudgeFrom(env, url), to: [row.email], reply_to: bareAddress(fromAddress(env, url)), subject: m.subject, text: m.text, html: m.html,
        scheduled_at: new Date(at).toISOString(),
        headers: { "List-Unsubscribe": `<${stop}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" } }),
    });
    if (res.ok) { const j = await res.json().catch(() => ({})); id = j && typeof j.id === "string" ? j.id.slice(0, 100) : null; }
  } catch (e) {}
  await env.DB.prepare("UPDATE nudges SET email_id = ?, send_at = ? WHERE h = ?").bind(id, id ? at : null, row.h).run();
  return !!id;
}
async function resendCancel(env, id) {
  try { await fetch(serviceURL(env.RESEND_BASE_URL, "https://api.resend.com") + "/emails/" + encodeURIComponent(id) + "/cancel", { method: "POST", headers: { authorization: "Bearer " + env.RESEND_API_KEY.trim() } }); } catch (e) {}
}
const bareAddress = f => (/<([^<>]+)>/.exec(f) || [null, f])[1];
const nudgeFrom = (env, url) => { const f = fromAddress(env, url); return f.includes("<") ? f : `Alefba <${f}>`; };
function nudgeMail(url, stop, next) {
  const h = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const go = `${url.origin}/?ref=email`;
  const what = next.t || "Your next lesson";
  const subject = "Your next Persian lesson is ready";
  const text = [
    "Hi! Your next Persian lesson is ready:",
    what + (next.fa ? ": " + next.fa : ""),
    "It only takes a few minutes. Pick up where you left off:\n" + go,
    "A little every day is the fastest way to learn.",
    "Alefba",
    "You're getting this because you asked for a reminder after a lesson on Alefba. It only comes the day after a lesson. To stop these emails: " + stop,
  ].join("\n\n");
  const html = `<div style="font-family:system-ui,-apple-system,sans-serif;font-size:16px;line-height:1.5;color:#13293a;max-width:520px">` +
    `<p>Hi! Your next Persian lesson is ready:</p>` +
    `<p style="font-size:18px;font-weight:700;margin:6px 0">${h(what)}${next.fa ? ` <span dir="rtl" lang="fa" style="font-size:24px">${h(next.fa)}</span>` : ""}</p>` +
    `<p>It only takes a few minutes.</p>` +
    `<p><a href="${h(go)}" style="display:inline-block;background:#1f3d8a;color:#ffffff;text-decoration:none;font-weight:600;padding:12px 20px;border-radius:10px">Start my next lesson</a></p>` +
    `<p>A little every day is the fastest way to learn.</p><p>Alefba</p>` +
    `<p style="font-size:13px;color:#5a6577;margin-top:24px">You're getting this because you asked for a reminder after a lesson on Alefba. It only comes the day after a lesson. <a href="${h(stop)}" style="color:#5a6577">Stop these emails</a></p></div>`;
  return { subject, text, html };
}
async function stopNudges(env, token) {
  if (!/^[A-Za-z0-9_-]{30,60}$/.test(token)) return false;
  const row = await env.DB.prepare("SELECT * FROM nudges WHERE h = ?").bind(await sha256("nudge:" + token)).first();
  if (!row) return false;
  if (row.email_id && row.send_at > Date.now()) await resendCancel(env, row.email_id);
  await env.DB.prepare("DELETE FROM nudges WHERE h = ?").bind(row.h).run(); // stopping forgets the address
  return true;
}
async function nudgeStop(request, env, url, s) { // from the app's settings
  if (!s.db) return reply({ error: "not_configured" }, 503);
  const body = await readJson(request, 1000);
  await stopNudges(env, String((body && body.token) || ""));
  return reply({ ok: true });
}
async function nudgeStopPage(request, env, url, s) {
  const token = String(url.searchParams.get("t") || "").slice(0, 100);
  const page = inner => new Response(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Alefba emails</title>
<style>body{font-family:system-ui,sans-serif;margin:24px 16px;color:#13213f;background:#fbf7ef;max-width:520px}h1{font-size:1.3rem}button{font:inherit;font-weight:600;padding:12px 18px;border:0;border-radius:10px;background:#1f3d8a;color:#fff}a{color:#1f3d8a}
@media (prefers-color-scheme:dark){body{background:#0b1820;color:#e4eef1}a{color:#9cc3ff}}</style></head><body>${inner}</body></html>`,
    { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-robots-tag": "noindex", "referrer-policy": "no-referrer", "x-frame-options": "DENY" } });
  if (!s.db) return page("<h1>Alefba</h1><p>Something went wrong. Please try again later.</p>");
  // a link opened in a browser (or checked by a mail scanner) only shows a button; the button, or the mail app's
  // one-click unsubscribe, stops them
  if (request.method === "GET") {
    const t = token.replace(/[^A-Za-z0-9_-]/g, "");
    return page(`<h1>Stop the Alefba reminder emails?</h1><p>You won't get any more emails about the next lesson.</p><form method="post" action="/api/nudge/stop?t=${t}"><button>Stop the emails</button></form>`);
  }
  await stopNudges(env, token);
  return page(`<h1>Done. No more reminder emails.</h1><p>You can still practise any time at <a href="${url.origin}/">learnalefba.com</a>.</p>`);
}

// ---------- the family's account, as the app sees it ----------
async function me(request, env, url, s) {
  const base = { talks: talksReady(s), plans: plansReady(s), hearReady: s.ai, voiceReady: s.voice, signedIn: false, free: plans(env).free, turnstile: s.turnstile ? String(env.TURNSTILE_SITE_KEY).trim() : null };
  if (!s.db) return reply(base);
  let fam = await currentFamily(request, env);
  if (!fam) return reply(base);
  if (s.stripe) {
    // ?refresh (after coming back from Stripe's pages) checks the plan with Stripe now, but not over and over
    const asked = url.searchParams.has("refresh") && !tooMany(request, "refresh", 10, 120);
    fam = await refreshPlan(env, fam, asked || quickCheck(env, fam));
  }
  return reply(await accountView(env, fam, s));
}
// A family that has started paying but has no plan yet is checked with Stripe again after a minute, not hours.
const quickCheck = (env, fam) => !activePlan(fam) && !!customerId(env, fam) && Date.now() - Number(fam.plan_checked || 0) > 60e3;
async function accountView(env, fam, s) {
  const p = plans(env), al = await allowance(env, fam, p);
  return {
    talks: talksReady(s), plans: plansReady(s), signedIn: true,
    turnstile: s.turnstile ? String(env.TURNSTILE_SITE_KEY).trim() : null,
    email: maskEmail(fam.email),
    plan: activePlan(fam),
    canTalk: al.ok, kind: al.kind, left: al.left, today: al.today == null ? null : al.today,
    managed: !!(s.stripe && customerId(env, fam)),
    hear: !!(s.ai && activePlan(fam)), hearReady: s.ai,
    voice: !!(s.voice && activePlan(fam)), voiceReady: s.voice, // spoken conversations: the character's lines read aloud
    free: p.free, basicTalks: p.basicTalks, perDay: p.perDay,
    prices: { basic: dollars(p.basic), unlimited: dollars(p.unlimited), yearly: dollars(p.yearly), school: dollars(p.school) },
    sync: !!fam.sync_on, fam: (await sha256("alefba-fam:" + fam.id)).slice(0, 16), // which family a device's learners belong to
  };
}
const activePlan = fam => (LIVE_STATUSES.includes(fam.plan_status) && isPlan(fam.plan) ? fam.plan : null);
const monthKey = t => new Date(t).toISOString().slice(0, 7);
const dayKey = t => new Date(t).toISOString().slice(0, 10);
async function countTalks(env, familyId, where, arg) {
  const r = await env.DB.prepare(`SELECT COUNT(*) AS n FROM talks WHERE family_id = ? AND ${where}`).bind(familyId, arg).first();
  return r ? Number(r.n) : 0;
}
// Free talks are counted against a one-way code made from the email address, so deleting the account
// or adding +something to the address doesn't bring them back.
function normalEmail(e) {
  let [u, d] = e.split("@");
  u = u.split("+")[0];
  if (d === "googlemail.com") d = "gmail.com";
  if (d === "gmail.com") u = u.replace(/\./g, "");
  return u + "@" + d;
}
const freeKey = email => sha256("alefba-free:" + normalEmail(email));
async function freeUsed(env, email) {
  const r = await env.DB.prepare("SELECT used FROM free_ledger WHERE h = ?").bind(await freeKey(email)).first();
  return r ? Number(r.used) : 0;
}
// How many talks the family can still start: free ones, this month's on the basic plan, or today's on unlimited.
async function allowance(env, fam, p) {
  const plan = talksOf(activePlan(fam)), now = Date.now();
  if (plan === "unlimited") {
    const n = await countTalks(env, fam.id, "started_at > ?", now - 864e5);
    return { ok: n < p.perDay, kind: "unlimited", left: null, today: Math.max(0, p.perDay - n) };
  }
  if (plan === "basic") {
    const n = await countTalks(env, fam.id, "month = ? AND kind != 'free'", monthKey(now)); // every paid talk this month, whichever plan it was taken on (the free ones don't count against the 20)
    return { ok: n < p.basicTalks, kind: "basic", left: Math.max(0, p.basicTalks - n) };
  }
  const left = Math.max(0, p.free - (await freeUsed(env, fam.email)));
  return { ok: left > 0, kind: "free", left };
}
// A new talk is held first, so two at once can't go over the limit. It is given back only if Claude
// didn't answer at all (an answer, even a refused one, is paid for).
async function reserveTalk(env, fam, clientKey) {
  const p = plans(env), kind = activePlan(fam) || "free", now = Date.now(), id = randomId();
  // a key from a talk that's long over can be used again
  if (clientKey) await env.DB.prepare("UPDATE talks SET client_key = NULL WHERE family_id = ? AND client_key = ? AND started_at <= ?").bind(fam.id, clientKey, now - TALK_HOURS * 3600e3).run();
  if (kind === "free") {
    if (p.free < 1) return { ok: false };
    const u = await env.DB.prepare("INSERT INTO free_ledger (h, used) VALUES (?, 1) ON CONFLICT(h) DO UPDATE SET used = used + 1 WHERE free_ledger.used < ?").bind(await freeKey(fam.email), p.free).run();
    if (!u.meta || u.meta.changes !== 1) return { ok: false };
  }
  try {
    await env.DB.prepare("INSERT INTO talks (id, family_id, started_at, month, kind, requests, client_key) VALUES (?, ?, ?, ?, ?, 1, ?)").bind(id, fam.id, now, monthKey(now), kind, clientKey || null).run();
  } catch (e) {
    if (kind === "free") await giveBackFree(env, fam);
    return { ok: false, duplicate: true }; // the same talk was just started by a retry
  }
  if (kind !== "free") {
    const n = kind === "basic" ? await countTalks(env, fam.id, "month = ? AND kind != 'free'", monthKey(now)) : await countTalks(env, fam.id, "started_at > ?", now - 864e5);
    if (n > (kind === "basic" ? p.basicTalks : p.perDay)) { await env.DB.prepare("DELETE FROM talks WHERE id = ?").bind(id).run(); return { ok: false }; }
  }
  return { ok: true, id, kind };
}
async function giveBackFree(env, fam) {
  await env.DB.prepare("UPDATE free_ledger SET used = MAX(used - 1, 0) WHERE h = ?").bind(await freeKey(fam.email)).run();
}
async function releaseTalk(env, fam, id, kind) {
  await env.DB.prepare("DELETE FROM talks WHERE id = ?").bind(id).run();
  if (kind === "free") await giveBackFree(env, fam);
}
// What Claude costs, in millionths of a dollar, from what it reports it read and wrote.
function costMicro(u) {
  if (!u) return 0;
  const i = Number(u.input_tokens) || 0, w = Number(u.cache_creation_input_tokens) || 0, rd = Number(u.cache_read_input_tokens) || 0, o = Number(u.output_tokens) || 0;
  const big = i + w + rd > 100000 ? 5 : 1;
  return Math.ceil((i * PRICE.in + w * PRICE.write + rd * PRICE.read + o * PRICE.out) * big);
}
async function addSpend(env, familyId, micro) {
  if (!micro) return;
  const day = dayKey(Date.now()), up = "INSERT INTO spend (k, micro) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET micro = micro + excluded.micro";
  await env.DB.batch([env.DB.prepare(up).bind(day + ":*", micro), ...(familyId ? [env.DB.prepare(up).bind(day + ":" + familyId, micro)] : [])]);
}
// The most one request could cost: every byte of it counted as a token at the cache-writing price, plus the
// longest reply. Before Claude is asked, that much is held against the day's limits in one step each, so many
// requests at once can't go over them. Afterwards the hold is swapped for what Claude actually charged.
const utf8 = s => enc.encode(s).length;
function mostItCosts(bytes) { return Math.ceil((bytes + PROMPT_EXTRA) * PRICE.write + MAX_TOKENS * PRICE.out); }
async function holdBudget(env, fam, free, amount) {
  const p = plans(env), day = dayKey(Date.now());
  const limits = [[day + ":*", p.dailyBudget, "paused"], ...(free ? [[day + ":free", p.freeBudget, "free_resting"]] : []), [day + ":" + fam.id, p.familyBudget, "resting"]];
  const held = [];
  for (const [k, limit, why] of limits) {
    const r = amount <= limit && await env.DB.prepare("INSERT INTO spend (k, micro) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET micro = micro + excluded.micro WHERE spend.micro + excluded.micro <= ?").bind(k, amount, limit).run();
    if (!r || !r.meta || r.meta.changes !== 1) { await settleBudget(env, held, -amount); return { ok: false, why }; }
    held.push(k);
  }
  return { ok: true, keys: held, amount };
}
async function settleBudget(env, keys, change) {
  if (!keys.length || !change) return;
  await env.DB.prepare(`UPDATE spend SET micro = MAX(micro + ?, 0) WHERE k IN (${keys.map(() => "?").join(", ")})`).bind(change, ...keys).run();
}

// ---------- talks ----------
async function talk(request, env, url, s) {
  if (!talksReady(s)) return reply({ error: "not_configured" }, 503);
  let fam = await currentFamily(request, env);
  if (!fam) return reply({ error: "sign_in" }, 401);
  if (tooMany(request, "talk")) return reply({ error: "rate_limited" }, 429);
  const body = await readJson(request, 160000);
  const turns = checkTurns(body && body.turns);
  if (!turns) return reply({ error: "bad_request" }, 400);
  const now = Date.now();
  const clientKey = typeof body.talk_key === "string" && /^[A-Za-z0-9_-]{8,64}$/.test(body.talk_key) ? body.talk_key : null;
  const openSince = now - TALK_HOURS * 3600e3;
  let talkId = null, kind = null, isNew = false;
  if (turns.length === 1) {
    // a retry of the same opening (for example after a lost connection) goes on with the talk already counted
    const again = clientKey && (await env.DB.prepare("SELECT id FROM talks WHERE family_id = ? AND client_key = ? AND started_at > ?").bind(fam.id, clientKey, openSince).first());
    if (again) talkId = again.id;
    else {
      if (s.stripe) fam = await refreshPlan(env, fam, quickCheck(env, fam));
      const held = await reserveTalk(env, fam, clientKey);
      if (held.ok) { talkId = held.id; kind = held.kind; isNew = true; }
      else if (held.duplicate) {
        const twin = await env.DB.prepare("SELECT id FROM talks WHERE family_id = ? AND client_key = ?").bind(fam.id, clientKey).first();
        if (!twin) return reply({ error: "server_error" }, 500);
        talkId = twin.id;
      } else return reply({ error: "no_talks", account: await accountView(env, fam, s) }, 402);
    }
  } else talkId = typeof body.talk_id === "string" ? body.talk_id.slice(0, 64) : "";
  if (!isNew) {
    const u = await env.DB.prepare("UPDATE talks SET requests = requests + 1 WHERE id = ? AND family_id = ? AND requests < ? AND started_at > ? RETURNING kind")
      .bind(talkId, fam.id, TALK_REQUESTS, openSince).first();
    if (!u) return reply({ error: "talk_over" }, 409);
    kind = u.kind;
  }
  // The day's limits on Claude use: everyone together, all free talks together (so free use can never
  // pause paying families), and each family. The most this request could cost is held first.
  const hold = await holdBudget(env, fam, kind === "free", mostItCosts(turns.bytes));
  if (!hold.ok) {
    if (isNew) await releaseTalk(env, fam, talkId, kind);
    else await env.DB.prepare("UPDATE talks SET requests = requests - 1 WHERE id = ? AND requests > 0").bind(talkId).run();
    return reply({ error: hold.why }, hold.why === "paused" ? 503 : 429);
  }
  const r = await askClaude(env, {
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: SYSTEM,
    thinking: { type: "disabled" },
    output_config: { effort: "low", format: { type: "json_schema", schema: SCHEMA } },
    messages: turns,
  });
  await settleBudget(env, hold.keys, (r.ok ? costMicro(r.data.usage) : 0) - hold.amount);
  if (!r.ok) {
    if (isNew) await releaseTalk(env, fam, talkId, kind); // Claude didn't answer, so nothing was paid for
    // out of credit, over the monthly spending limit, or the key was switched off: talks rest until a grown-up fixes it
    if (["billing", "limit_reached", "key_rejected", "workspace"].includes(r.why)) return reply({ error: "paused" }, 503);
    if (r.status === 429) return reply({ error: "rate_limited" }, 429);
    return reply({ error: "server_error" }, 502);
  }
  if (r.data.stop_reason === "refusal") return reply({ error: "refused", talk_id: talkId }, 422);
  const text = (r.data.content || []).filter(b => b.type === "text").map(b => b.text).join("");
  let out;
  try { out = JSON.parse(text); } catch (e) { out = null; }
  if (!out || typeof out !== "object" || Array.isArray(out)) return reply({ error: "invalid_json", talk_id: talkId }, 502);
  out.talk_id = talkId;
  if (turns.length === 1) out.account = await accountView(env, (await familyById(env, fam.id)) || fam, s);
  return reply(out);
}

// ---------- speaking practice ----------
// A child says a word or a sentence; Cloudflare's speech-to-text writes down what it heard, and the app compares
// that with what the child was asked to say. Only for families with a plan. The recording is never saved or logged:
// it exists only while this request runs, which is what the US children's privacy rule asks of voice recordings.
async function hear(request, env, url, s) {
  if (!s.ai || !s.db) return reply({ error: "not_configured" }, 503);
  let fam = await currentFamily(request, env);
  if (!fam) return reply({ error: "sign_in" }, 401);
  if (s.stripe) fam = await refreshPlan(env, fam, quickCheck(env, fam));
  if (!activePlan(fam)) return reply({ error: "needs_plan" }, 402);
  if (tooMany(request, "hear", 30, 400)) return reply({ error: "rate_limited" }, 429);
  const type = String(request.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
  if (type !== "audio/wav") return reply({ error: "bad_request" }, 400);
  const buf = await readBounded(request, HEAR_MAX_BYTES);
  if (!buf) return reply({ error: "too_long" }, 413);
  if (buf.length < 1000) return reply({ error: "too_short" }, 400);
  // a real WAV file: "RIFF....WAVE"
  if (!(buf[0] === 0x52 && buf[1] === 0x49 && buf[2] === 0x46 && buf[3] === 0x46 && buf[8] === 0x57 && buf[9] === 0x41 && buf[10] === 0x56 && buf[11] === 0x45)) return reply({ error: "bad_request" }, 400);
  const day = dayKey(Date.now());
  if (!(await bump(env, `${day}:hear:${fam.id}`, Math.max(1, Math.min(5000, parseInt(env.HEAR_PER_DAY, 10) || 300))))) return reply({ error: "resting" }, 429);
  const hold = await holdBudget(env, fam, false, HEAR_MICRO);
  if (!hold.ok) return reply({ error: hold.why }, hold.why === "paused" ? 503 : 429);
  // What the learner was asked to say, or in a talk what's being talked about: telling the speech-to-text what to expect
  // helps it pick the right word among sound-alikes. Only short Persian text is passed on; anything else is ignored.
  const expect = String(url.searchParams.get("expect") || "").normalize("NFC").trim();
  const prompt = expect.length <= 300 && /^[\u0600-\u06FF\u200c\s.,!?؟،]+$/.test(expect) && /[\u0621-\u06CC]/.test(expect) ? expect : "یک کلمه یا یک جمله‌ی کوتاه فارسی.";
  let text = "";
  // Azure's Persian speech recognition is much better than Whisper at short Persian phrases, so it goes first when the
  // Azure voice is set up; Whisper is the back-up if Azure is down or hears nothing.
  if (s.voice) {
    const az = await azureHear(env, buf);
    if (az) return reply({ text: az });
  }
  try {
    const r = await env.AI.run(HEAR_MODEL, {
      audio: base64(buf), language: "fa", task: "transcribe", vad_filter: true,
      condition_on_previous_text: false, initial_prompt: prompt,
    });
    text = String((r && (r.text || (r.transcription_info && r.transcription_info.text))) || "");
  } catch (e) {
    await settleBudget(env, hold.keys, -hold.amount);
    return reply({ error: "hear_failed" }, 502);
  }
  return reply({ text: cleanHeard(text) });
}
// Whisper sometimes makes up stray Latin letters when it isn't sure; the learner is speaking Persian, so drop them.
function cleanHeard(t) { return String(t || "").replace(/[A-Za-z]+/g, " ").replace(/\s+/g, " ").trim().replace(/[.。]+$/, "").slice(0, 300); }
// Azure speech to text for a short clip (about 12 seconds at most). Returns the Persian text, or "" to fall back.
async function azureHear(env, wav) {
  const region = String(env.AZURE_SPEECH_REGION).trim().toLowerCase();
  try {
    const res = await fetch(serviceURL(env.AZURE_BASE_URL, `https://${region}.stt.speech.microsoft.com`) + "/speech/recognition/conversation/cognitiveservices/v1?language=fa-IR&format=simple", {
      method: "POST",
      headers: { "Ocp-Apim-Subscription-Key": String(env.AZURE_SPEECH_KEY).trim(), "content-type": "audio/wav; codecs=audio/pcm; samplerate=16000", accept: "application/json", "user-agent": "Alefba" },
      body: wav,
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return "";
    const j = await res.json().catch(() => null);
    return j && j.RecognitionStatus === "Success" ? cleanHeard(j.DisplayText) : "";
  } catch (e) { return ""; }
}
// ---------- what did I just say? /api/gloss ----------
// After the microphone hears a Persian line, the learner sees it in Finglish and in their own language before sending,
// so they can tell whether it heard them right. One tiny Claude call, cached for a month per line and language.
const GLOSS_MICRO = 400;        // what one gloss can cost at most, in millionths of a dollar (it's usually under 100)
const GLOSS_LANGS = { en: "English", fr: "French", de: "German", sv: "Swedish", zh: "Mandarin Chinese (simplified characters)" };
const GLOSS_SCHEMA = { type: "object", properties: { translit: { type: "string" }, meaning: { type: "string" } }, required: ["translit", "meaning"], additionalProperties: false };
async function gloss(request, env, url, s) {
  if (!s.claude || !s.db) return reply({ error: "not_configured" }, 503);
  let fam = await currentFamily(request, env);
  if (!fam) return reply({ error: "sign_in" }, 401);
  if (s.stripe) fam = await refreshPlan(env, fam, quickCheck(env, fam));
  if (!activePlan(fam)) return reply({ error: "needs_plan" }, 402);
  if (tooMany(request, "gloss", 40, 600)) return reply({ error: "rate_limited" }, 429);
  const body = await readJson(request, 4000);
  const text = String((body && body.text) || "").normalize("NFC").replace(/\s+/g, " ").trim();
  if (!text || text.length > SAY_MAX_CHARS || !SAY_TEXT.test(text) || !/[ء-ی]/.test(text)) return reply({ error: "bad_request" }, 400);
  const lang = GLOSS_LANGS[String(body.lang || "en")] ? String(body.lang) : "en";
  const cacheKey = new Request(url.origin + "/api/gloss/" + (await sha256(`${lang}|${text}`)), { method: "GET" });
  const cache = typeof caches !== "undefined" && caches.default;
  if (cache) { const hit = await cache.match(cacheKey).catch(() => null); if (hit) return new Response(hit.body, { headers: { "content-type": "application/json", "cache-control": "private, max-age=3600" } }); }
  const hold = await holdBudget(env, fam, false, GLOSS_MICRO);
  if (!hold.ok) return reply({ error: hold.why }, hold.why === "paused" ? 503 : 429);
  const r = await askClaude(env, {
    model: MODEL, max_tokens: 200, thinking: { type: "disabled" },
    system: `A learner of Persian just said a line out loud and it was written down in Persian script. Give "translit", the line in Finglish (Persian in Latin letters: â for the long a as in mâdar, kh, gh, sh, ch, zh, for example salâm, khodâhâfez, chetori), and "meaning", what it means in ${GLOSS_LANGS[lang]}, short and natural. If the line is garbled or isn't Persian, still give your best reading. Answer with the JSON only.`,
    output_config: { effort: "low", format: { type: "json_schema", schema: GLOSS_SCHEMA } },
    messages: [{ role: "user", content: text }],
  });
  await settleBudget(env, hold.keys, (r.ok ? costMicro(r.data.usage) : 0) - hold.amount);
  if (!r.ok) return reply({ error: r.status === 429 ? "rate_limited" : "server_error" }, r.status === 429 ? 429 : 502);
  let out = null;
  try { out = JSON.parse((r.data.content || []).filter(b => b.type === "text").map(b => b.text).join("")); } catch (e) {}
  if (!out || typeof out !== "object") return reply({ error: "server_error" }, 502);
  const res = reply({ translit: String(out.translit || "").trim().slice(0, 300), meaning: String(out.meaning || "").trim().slice(0, 300) });
  if (cache) { try { const keep = new Response(res.clone().body, { headers: { "content-type": "application/json", "cache-control": `public, max-age=${30 * 86400}` } }); await cache.put(cacheKey, keep); } catch (e) {} }
  return res;
}
function base64(bytes) {
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

// ---------- spoken conversations ----------
// A character's line is read aloud by Microsoft's Persian voice, for families with a plan. Only short Persian text is
// accepted, nothing is saved, and a line that was read once is kept in Cloudflare's cache for a month, so hearing it
// again (Play again, Slower, or another family getting the same greeting) costs nothing.
const SAY_TEXT = /^[؀-ۿ‌\s0-9.,!?؟،:;()"'«»…-]+$/;
async function say(request, env, url, s) {
  if (!s.voice || !s.db) return reply({ error: "not_configured" }, 503);
  let fam = await currentFamily(request, env);
  if (!fam) return reply({ error: "sign_in" }, 401);
  if (s.stripe) fam = await refreshPlan(env, fam, quickCheck(env, fam));
  if (!activePlan(fam)) return reply({ error: "needs_plan" }, 402);
  if (tooMany(request, "say", 40, 600)) return reply({ error: "rate_limited" }, 429);
  const body = await readJson(request, 4000);
  const text = String((body && body.text) || "").normalize("NFC").replace(/\s+/g, " ").trim();
  if (!text || text.length > SAY_MAX_CHARS || !SAY_TEXT.test(text) || !/[ء-ی]/.test(text)) return reply({ error: "bad_request" }, 400);
  const slow = body.rate === "slow", voice = SAY_VOICES[body.voice === "m" ? "m" : "f"];
  // the same line, speed and voice always has the same cache address
  const cacheKey = new Request(url.origin + "/api/say/" + (await sha256(`${voice}|${slow ? "slow" : "normal"}|${text}`)), { method: "GET" });
  const cache = typeof caches !== "undefined" && caches.default;
  if (cache) { const hit = await cache.match(cacheKey).catch(() => null); if (hit) return audioReply(hit, true); }
  const day = dayKey(Date.now());
  if (!(await bump(env, `${day}:say:${fam.id}`, Math.max(1, Math.min(20000, parseInt(env.SAY_PER_DAY, 10) || 600))))) return reply({ error: "resting" }, 429);
  const hold = await holdBudget(env, fam, false, Math.max(200, text.length * SAY_MICRO_PER_CHAR));
  if (!hold.ok) return reply({ error: hold.why }, hold.why === "paused" ? 503 : 429);
  const r = await azureSpeak(env, text, voice, slow);
  if (!r.ok) { await settleBudget(env, hold.keys, -hold.amount); return reply({ error: r.status === 401 || r.status === 403 ? "voice_key" : "say_failed" }, 502); }
  const res = new Response(r.body, { headers: { "content-type": "audio/mpeg", "cache-control": `public, max-age=${SAY_CACHE_DAYS * 86400}` } });
  if (cache) { try { await cache.put(cacheKey, res.clone()); } catch (e) {} }
  return audioReply(res, false);
}
function audioReply(res, cached) {
  const h = new Headers(res.headers);
  h.set("cache-control", "private, max-age=3600"); // the family's own device may keep it for an hour
  h.set("x-content-type-options", "nosniff");
  h.set("x-alefba-cached", cached ? "1" : "0");
  return new Response(res.body, { status: 200, headers: h });
}
const xmlSafe = t => t.replace(/[<>&'"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&apos;", '"': "&quot;" }[c]));
async function azureSpeak(env, text, voice, slow) {
  const region = String(env.AZURE_SPEECH_REGION).trim().toLowerCase();
  const ssml = `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="fa-IR"><voice name="${voice}"><prosody rate="${slow ? "-35%" : "-8%"}">${xmlSafe(text)}</prosody></voice></speak>`;
  try {
    const res = await fetch(serviceURL(env.AZURE_BASE_URL, `https://${region}.tts.speech.microsoft.com`) + "/cognitiveservices/v1", {
      method: "POST",
      headers: { "Ocp-Apim-Subscription-Key": String(env.AZURE_SPEECH_KEY).trim(), "content-type": "application/ssml+xml", "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3", "user-agent": "Alefba" },
      body: ssml,
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return { ok: false, status: res.status };
    const body = await res.arrayBuffer();
    if (body.byteLength < 200) return { ok: false, status: 502 };
    return { ok: true, body };
  } catch (e) { return { ok: false, status: 0 }; }
}

// ---------- codes by email: signing in, and confirming changes to a plan or the account ----------
async function authStart(request, env, url, s) {
  if (!s.db || !s.email) return reply({ error: "not_configured" }, 503);
  if (tooMany(request, "auth", 6, 20)) return reply({ error: "too_many" }, 429);
  const body = await readJson(request, 4000);
  const email = cleanEmail(body && body.email);
  if (!email) return reply({ error: "bad_email" }, 400);
  if (body.agree !== true) return reply({ error: "agree" }, 400);
  if (s.turnstile && !(await robotCheck(env, body.turnstile, request))) return reply({ error: "robot_check" }, 400);
  // a few sign-in emails a day from one internet address (or one IPv6 network), counted under a scrambled code of it,
  // so one person can't use up the day's emails for everyone
  const net = (await sha256("alefba-net:" + netOf(request.headers.get("CF-Connecting-IP")))).slice(0, 24);
  if (!(await bump(env, `${dayKey(Date.now())}:net:${net}`, LIMITS.signinsPerDay))) return reply({ error: "too_many" }, 429);
  return sendCodeTo(env, url, email, email, "signin");
}
// An IPv4 address as it is; an IPv6 address cut to its first 56 bits, which is usually one home or one phone.
function netOf(ip) {
  ip = String(ip || "").trim().toLowerCase();
  if (!ip) return "unknown";
  if (!ip.includes(":") || ip.includes(".")) return ip.slice(ip.lastIndexOf(":") + 1);
  const [head, tail] = ip.split("::");
  const h = head ? head.split(":") : [], t = tail === undefined ? null : tail ? tail.split(":") : [];
  const g = (t ? [...h, ...Array(Math.max(0, 8 - h.length - t.length)).fill("0"), ...t] : h).map(x => (x || "0").padStart(4, "0"));
  return g.slice(0, 3).join(":") + ":" + (g[3] || "0000").slice(0, 2);
}
// Adds one to a counter unless it has reached its limit, in one step. False when it's full.
async function bump(env, k, limit) {
  const r = await env.DB.prepare("INSERT INTO counters (k, n) VALUES (?, 1) ON CONFLICT(k) DO UPDATE SET n = n + 1 WHERE counters.n < ?").bind(k, limit).run();
  return !!(r.meta && r.meta.changes === 1);
}
async function confirmStart(request, env, url, s) {
  if (!s.db || !s.email) return reply({ error: "not_configured" }, 503);
  const fam = await currentFamily(request, env);
  if (!fam) return reply({ error: "sign_in" }, 401);
  if (tooMany(request, "auth", 6, 20)) return reply({ error: "too_many" }, 429);
  return sendCodeTo(env, url, "confirm:" + fam.email, fam.email, "confirm");
}
// One code per address at a time: at most one every 20 seconds and 5 an hour, checked and saved in one step,
// and a cap on emails a day for the whole site.
async function sendCodeTo(env, url, key, email, purpose) {
  const now = Date.now(), code = sixDigits(), salt = randomId(), p = plans(env), hourAgo = now - 3600e3;
  // the day's cap on sign-in emails is checked first, so hitting it never touches a code that's still valid (codes to
  // confirm a change go only to a signed-in family's own address, so they don't count, and no one can use up the cap
  // to stop a parent ending a plan or deleting the account)
  if (purpose === "signin") {
    const r = await env.DB.prepare("SELECT n FROM counters WHERE k = ?").bind(`${dayKey(now)}:emails`).first();
    if (r && Number(r.n) >= p.emailsPerDay) return reply({ error: "too_many" }, 429);
  }
  const saved = await env.DB.prepare(
    "INSERT INTO codes (email, salt, hash, expires, tries, sent_at, sends, window_start) VALUES (?, ?, ?, ?, 0, ?, 1, ?) " +
    "ON CONFLICT(email) DO UPDATE SET salt = excluded.salt, hash = excluded.hash, expires = excluded.expires, tries = 0, sent_at = excluded.sent_at, " +
    "sends = CASE WHEN codes.window_start > ? THEN codes.sends + 1 ELSE 1 END, " +
    "window_start = CASE WHEN codes.window_start > ? THEN codes.window_start ELSE excluded.window_start END " +
    "WHERE codes.sent_at <= ? AND (codes.window_start <= ? OR codes.sends < ?)")
    .bind(key, salt, await sha256(salt + code), now + CODE_MINUTES * 60e3, now, now, hourAgo, hourAgo, now - CODE_GAP_MS, hourAgo, CODES_PER_HOUR).run();
  if (!saved.meta || saved.meta.changes !== 1) {
    const row = await env.DB.prepare("SELECT sent_at FROM codes WHERE email = ?").bind(key).first();
    return reply({ error: row && now - row.sent_at < CODE_GAP_MS ? "wait" : "too_many" }, 429);
  }
  if (purpose === "signin" && !(await bump(env, `${dayKey(now)}:emails`, p.emailsPerDay))) {
    // the cap was reached by another request in the meantime: this code won't be emailed, so it can't be used
    await env.DB.prepare("UPDATE codes SET expires = 0 WHERE email = ? AND salt = ?").bind(key, salt).run();
    return reply({ error: "too_many" }, 429);
  }
  const sent = await sendEmail(env, url, email, code, purpose);
  if (!sent.ok) return reply({ error: "email_failed" }, 502);
  return reply({ ok: true });
}
// A guess uses up a try before it is compared, in one step, so guesses sent all at once can't get past 5.
async function checkCode(env, key, rawCode) {
  const code = latinDigits(String(rawCode || "")).replace(/\D/g, "");
  if (code.length !== 6) return { error: "wrong_code", left: null };
  const now = Date.now();
  const row = await env.DB.prepare("UPDATE codes SET tries = tries + 1 WHERE email = ? AND tries < ? AND expires > ? RETURNING salt, hash, tries").bind(key, CODE_TRIES, now).first();
  if (!row) {
    const there = await env.DB.prepare("SELECT expires FROM codes WHERE email = ?").bind(key).first();
    return { error: !there || there.expires <= now ? "expired" : "too_many" };
  }
  if ((await sha256(row.salt + code)) !== row.hash) {
    const left = CODE_TRIES - Number(row.tries);
    return left > 0 ? { error: "wrong_code", left } : { error: "too_many" };
  }
  const used = await env.DB.prepare("DELETE FROM codes WHERE email = ? AND hash = ?").bind(key, row.hash).run();
  return used.meta && used.meta.changes === 1 ? { ok: true } : { error: "expired" };
}
const codeReply = c => reply(c.error === "wrong_code" ? { error: "wrong_code", left: c.left } : { error: c.error }, c.error === "too_many" ? 429 : 400);
async function authVerify(request, env, url, s) {
  if (!s.db) return reply({ error: "not_configured" }, 503);
  if (tooMany(request, "verify", 15, 60)) return reply({ error: "too_many" }, 429);
  const body = await readJson(request, 2000);
  const email = cleanEmail(body && body.email);
  if (!email) return reply({ error: "wrong_code", left: null }, 400);
  const c = await checkCode(env, email, body.code);
  if (!c.ok) return codeReply(c);
  const now = Date.now();
  await env.DB.prepare("INSERT INTO families (id, email, created_at) VALUES (?, ?, ?) ON CONFLICT(email) DO NOTHING").bind(randomId(), email, now).run();
  let fam = await env.DB.prepare("SELECT * FROM families WHERE email = ?").bind(email).first();
  const token = randomToken();
  await env.DB.prepare("INSERT INTO sessions (hash, family_id, created_at, seen_at) VALUES (?, ?, ?, ?)").bind(await sha256(token), fam.id, now, now).run();
  if (s.stripe) fam = await refreshPlan(env, fam, true); // a returning family may already have a plan
  const res = reply({ ok: true, account: await accountView(env, fam, s) });
  res.headers.append("set-cookie", sessionCookie(url, token));
  return res;
}
async function signOut(request, env, url, s) {
  const token = readCookie(request, url);
  if (token && s.db) await env.DB.prepare("DELETE FROM sessions WHERE hash = ?").bind(await sha256(token)).run();
  const res = reply({ ok: true });
  res.headers.append("set-cookie", clearCookie(url));
  return res;
}
async function deleteAccount(request, env, url, s) {
  if (!s.db) return reply({ error: "not_configured" }, 503);
  const fam = await currentFamily(request, env);
  if (!fam) return reply({ error: "sign_in" }, 401);
  if (tooMany(request, "plans", 10, 60)) return reply({ error: "too_many" }, 429);
  const body = (await readJson(request, 1000)) || {};
  // Nothing is deleted unless Stripe has said for certain that nothing can charge the family afterwards.
  // A real (live) customer can only be dealt with using the live key, so without it the account stays for now.
  if (fam.stripe_live && (!s.stripe || stripeMode(env) !== "live")) return reply({ error: "payment_error" }, 409);
  if (!s.stripe && fam.sub_id) return reply({ error: "payment_error" }, 502);
  let open = [];
  const cust = s.stripe ? customerId(env, fam) : null;
  if (cust) {
    // a checkout left open in another tab is closed first, so it can't be paid after the account is gone
    const mode = stripeMode(env), prev = String(fam.checkout_id || "");
    if (prev.startsWith(mode + ":") && !(await expireCheckout(env, prev.slice(mode.length + 1)))) return reply({ error: "payment_error" }, 502);
    const subs = await stripeSubs(env, cust);
    if (!subs) return reply({ error: "payment_error" }, 502);
    open = subs.filter(x => OPEN_STATUSES.includes(x.status));
    if (open.length && body.endPlan !== true) return reply({ error: "has_plan" }, 409);
  }
  const c = await checkCode(env, "confirm:" + fam.email, body.code);
  if (!c.ok) return codeReply(c);
  for (const sub of open) {
    const end = await stripe(env, "DELETE", `/subscriptions/${encodeURIComponent(sub.id)}`);
    if (!end.ok) return reply({ error: "payment_error" }, 502);
  }
  if (cust) {
    // and the customer itself, with the parent's email (Stripe keeps its records of past payments)
    const gone = await stripe(env, "DELETE", `/customers/${encodeURIComponent(cust)}`);
    if (!gone.ok && gone.status !== 404) return reply({ error: "payment_error" }, 502);
  }
  if (cust) { // a school plan checkout left open is closed too, so it can't be paid for a class that's gone
    const mode = stripeMode(env);
    const pend = (await env.DB.prepare("SELECT checkout_id FROM classes WHERE teacher_id = ? AND checkout_id IS NOT NULL").bind(fam.id).all()).results || [];
    for (const r of pend) { const v = String(r.checkout_id); if (v.startsWith(mode + ":") && !(await expireCheckout(env, v.slice(mode.length + 1)))) return reply({ error: "payment_error" }, 502); }
  }
  const nd = await env.DB.prepare("SELECT email_id, send_at FROM nudges WHERE email = ?").bind(fam.email).first();
  if (nd && nd.email_id && nd.send_at > Date.now() && s.email) await resendCancel(env, nd.email_id); // a reminder email still booked
  await env.DB.batch([
    env.DB.prepare("DELETE FROM progress WHERE family_id = ?").bind(fam.id),
    env.DB.prepare("DELETE FROM talks WHERE family_id = ?").bind(fam.id),
    env.DB.prepare("DELETE FROM class_members WHERE class_id IN (SELECT id FROM classes WHERE teacher_id = ?)").bind(fam.id),
    env.DB.prepare("DELETE FROM classes WHERE teacher_id = ?").bind(fam.id),
    env.DB.prepare("DELETE FROM sessions WHERE family_id = ?").bind(fam.id),
    env.DB.prepare("DELETE FROM codes WHERE email = ? OR email = ?").bind(fam.email, "confirm:" + fam.email),
    env.DB.prepare("DELETE FROM families WHERE id = ?").bind(fam.id),
    env.DB.prepare("DELETE FROM nudges WHERE email = ?").bind(fam.email),
  ]);
  const res = reply({ ok: true });
  res.headers.append("set-cookie", clearCookie(url));
  return res;
}
async function currentFamily(request, env) {
  const token = readCookie(request, new URL(request.url));
  if (!token) return null;
  const h = await sha256(token);
  const row = await env.DB.prepare("SELECT f.*, s.seen_at AS session_seen FROM sessions s JOIN families f ON f.id = s.family_id WHERE s.hash = ?").bind(h).first();
  if (!row) return null;
  const now = Date.now();
  if (now - row.session_seen > SESSION_DAYS * 864e5) { await env.DB.prepare("DELETE FROM sessions WHERE hash = ?").bind(h).run(); return null; }
  if (now - row.session_seen > 864e5) await env.DB.prepare("UPDATE sessions SET seen_at = ? WHERE hash = ?").bind(now, h).run();
  return row;
}
const familyById = (env, id) => env.DB.prepare("SELECT * FROM families WHERE id = ?").bind(id).first();

async function sendEmail(env, url, to, code, purpose) {
  const confirm = purpose === "confirm";
  const subject = confirm ? `${code} is your code to confirm a change in Alefba` : `${code} is your Alefba code`;
  const lines = confirm
    ? ["Someone signed in to Alefba with this email asked to change your plan or delete your account.", "To go ahead, enter this code:", code, `It works for ${CODE_MINUTES} minutes. If you didn't ask for this, ignore this email and nothing will change.`]
    : ["Your Alefba sign-in code is", code, `It works for ${CODE_MINUTES} minutes. If you didn't ask for it, you can ignore this email.`];
  const html = `<div style="font-family:system-ui,-apple-system,sans-serif;font-size:16px;line-height:1.5;color:#13293a">` +
    lines.map(l => (l === code ? `<p style="font-size:30px;font-weight:700;letter-spacing:6px;margin:8px 0">${code}</p>` : `<p>${l}</p>`)).join("") + `</div>`;
  try {
    const res = await fetch(serviceURL(env.RESEND_BASE_URL, "https://api.resend.com") + "/emails", {
      method: "POST",
      headers: { authorization: "Bearer " + env.RESEND_API_KEY.trim(), "content-type": "application/json" },
      body: JSON.stringify({ from: fromAddress(env, url), to: [to], subject, text: lines.join("\n\n"), html }),
    });
    return { ok: res.ok, status: res.status };
  } catch (e) { return { ok: false, status: 0 }; }
}
function fromAddress(env, url) {
  const f = String(env.EMAIL_FROM || "").trim();
  if (/^[^<>\r\n]{0,60}<[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+>$/.test(f) || /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(f)) return f;
  return `Alefba <hello@${url.hostname.replace(/^www\./, "")}>`;
}
// Cloudflare Turnstile: a quick robot check before a sign-in email is sent, when it's set up.
async function robotCheck(env, token, request) {
  if (typeof token !== "string" || !token || token.length > 2048) return false;
  try {
    const res = await fetch(serviceURL(env.TURNSTILE_BASE_URL, "https://challenges.cloudflare.com") + "/turnstile/v0/siteverify", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ secret: String(env.TURNSTILE_SECRET_KEY).trim(), response: token, remoteip: request.headers.get("CF-Connecting-IP") || undefined }),
    });
    const d = await res.json();
    return !!(d && d.success === true);
  } catch (e) { return false; }
}

// ---------- plans and payments (Stripe) ----------
// Stripe keeps test and live data apart, so each family has a customer for each.
const customerColumn = env => (stripeMode(env) === "live" ? "stripe_live" : "stripe_test");
const customerId = (env, fam) => fam[customerColumn(env)] || null;
async function stripe(env, method, path, params, extraHeaders) {
  const body = params ? form(params) : "";
  const u = serviceURL(env.STRIPE_BASE_URL, "https://api.stripe.com") + "/v1" + path + (method === "GET" && body ? "?" + body : "");
  try {
    const res = await fetch(u, {
      method,
      headers: { authorization: "Bearer " + String(env.STRIPE_SECRET_KEY).trim(), "content-type": "application/x-www-form-urlencoded", ...(extraHeaders || {}) },
      body: method === "GET" || method === "DELETE" ? undefined : body,
    });
    let data = null;
    try { data = await res.json(); } catch (e) {}
    return { ok: res.ok, status: res.status, data, message: String((data && data.error && data.error.message) || "") };
  } catch (e) { return { ok: false, status: 0, data: null, message: "network" }; }
}
function form(obj) {
  return Object.entries(obj).filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => encodeURIComponent(k).replace(/%5B/gi, "[").replace(/%5D/gi, "]") + "=" + encodeURIComponent(String(v))).join("&");
}
// Which plan a Stripe subscription is for, read from its price.
function planOf(sub) {
  for (const it of (sub.items && sub.items.data) || []) {
    const pr = it.price || {};
    const m = (pr.metadata && pr.metadata.alefba_plan) || PLAN_NAMES.find(k => pr.lookup_key === LOOKUP[k]) || null;
    if (isPlan(m)) return m;
  }
  return null;
}
async function stripeSubs(env, cust) {
  const r = await stripe(env, "GET", "/subscriptions", { customer: cust, status: "all", limit: 100 });
  return r.ok && r.data && Array.isArray(r.data.data) ? r.data.data : null;
}
// The family's plan, from Stripe now and then (and right after paying), so cancelling or a failed payment is noticed.
async function refreshPlan(env, fam, force) {
  const cust = customerId(env, fam);
  if (!cust) {
    if (fam.plan || fam.plan_status) {
      await env.DB.prepare("UPDATE families SET plan = NULL, plan_status = NULL, sub_id = NULL WHERE id = ?").bind(fam.id).run();
      return { ...fam, plan: null, plan_status: null, sub_id: null };
    }
    return fam;
  }
  if (!force && Date.now() - Number(fam.plan_checked || 0) < PLAN_CHECK_HOURS * 3600e3) return fam;
  const subs = await stripeSubs(env, cust);
  if (!subs) return fam;
  let best = null;
  for (const sub of subs) {
    if (!LIVE_STATUSES.includes(sub.status)) continue;
    const plan = planOf(sub);
    if (plan && (!best || RANK[plan] > RANK[best.plan])) best = { plan, sub };
  }
  const next = { plan: best ? best.plan : null, plan_status: best ? best.sub.status : null, sub_id: best ? best.sub.id : null, plan_checked: Date.now() };
  await env.DB.prepare("UPDATE families SET plan = ?, plan_status = ?, sub_id = ?, plan_checked = ? WHERE id = ?").bind(next.plan, next.plan_status, next.sub_id, next.plan_checked, fam.id).run();
  return { ...fam, ...next };
}
async function ensureCustomer(env, fam) {
  const have = customerId(env, fam);
  if (have) return have;
  // the same request twice (a double tap) gets the same customer back
  const r = await stripe(env, "POST", "/customers", { email: fam.email, "metadata[family_id]": fam.id }, { "Idempotency-Key": `alefba-customer-${stripeMode(env)}-${fam.id}` });
  if (!r.ok) return null;
  await env.DB.prepare(`UPDATE families SET ${customerColumn(env)} = ? WHERE id = ?`).bind(r.data.id, fam.id).run();
  return r.data.id;
}
// The two monthly prices, made in Stripe the first time they're needed (and again if a price setting changes).
async function ensurePrices(env) {
  const p = plans(env), key = "prices:" + stripeMode(env);
  const cached = await getSetting(env, key);
  if (cached && PLAN_NAMES.every(k => cached[k] && cached[k].cents === p[k])) return cached;
  const list = await stripe(env, "GET", "/prices", { "lookup_keys[0]": LOOKUP.basic, "lookup_keys[1]": LOOKUP.unlimited, "lookup_keys[2]": LOOKUP.yearly, active: "true", limit: 10 });
  if (!list.ok) return null;
  const found = {};
  for (const pr of (list.data && list.data.data) || []) found[pr.lookup_key] = pr;
  const out = {};
  for (const plan of PLAN_NAMES) {
    const cents = p[plan], pr = found[LOOKUP[plan]], interval = plan === "yearly" ? "year" : "month";
    const productOf = x => (x ? (typeof x.product === "string" ? x.product : x.product && x.product.id) : null);
    if (pr && pr.unit_amount === cents && pr.currency === "usd" && pr.recurring && pr.recurring.interval === interval) { out[plan] = { id: pr.id, cents, product: productOf(pr) }; continue; }
    let product = productOf(pr);
    if (!product && plan === "yearly" && out.unlimited) product = out.unlimited.product || null; // the same product as unlimited, billed yearly
    if (!product) {
      const made = await stripe(env, "POST", "/products", { name: plan === "basic" ? `Alefba: ${p.basicTalks} talks a month` : "Alefba: unlimited talks", "metadata[alefba_plan]": plan });
      if (!made.ok) return null;
      product = made.data.id;
    }
    const np = await stripe(env, "POST", "/prices", {
      product, currency: "usd", unit_amount: cents, "recurring[interval]": interval,
      lookup_key: LOOKUP[plan], transfer_lookup_key: "true", "metadata[alefba_plan]": plan,
      nickname: plan === "basic" ? `${p.basicTalks} talks a month` : plan === "yearly" ? "Unlimited talks, yearly" : "Unlimited talks",
    });
    if (!np.ok) return null;
    out[plan] = { id: np.data.id, cents, product };
  }
  await setSetting(env, key, out);
  return out;
}
// Stripe's page where parents can update their card, see receipts or cancel.
async function ensurePortalConfig(env, fresh) {
  const key = "portal:" + stripeMode(env);
  const c = fresh ? null : await getSetting(env, key);
  if (c && c.id) return c.id;
  const r = await stripe(env, "POST", "/billing_portal/configurations", {
    "business_profile[headline]": "Alefba: your plan",
    "features[invoice_history][enabled]": "true",
    "features[payment_method_update][enabled]": "true",
    "features[subscription_cancel][enabled]": "true",
    "features[subscription_cancel][mode]": "at_period_end",
  });
  if (!r.ok) return null;
  await setSetting(env, key, { id: r.data.id });
  return r.data.id;
}
async function signedInForPlans(request, env, s) {
  if (!plansReady(s)) return { res: reply({ error: "not_configured" }, 503) };
  const fam = await currentFamily(request, env);
  if (!fam) return { res: reply({ error: "sign_in" }, 401) };
  if (tooMany(request, "plans", 10, 60)) return { res: reply({ error: "too_many" }, 429) };
  return { fam };
}
async function checkout(request, env, url, s) {
  const g = await signedInForPlans(request, env, s);
  if (g.res) return g.res;
  const body = await readJson(request, 1000), plan = body && body.plan;
  if (!isPlan(plan)) return reply({ error: "bad_request" }, 400);
  const fam = await refreshPlan(env, g.fam, true);
  if (activePlan(fam)) return reply({ error: "has_plan", account: await accountView(env, fam, s) }, 409);
  const customer = await ensureCustomer(env, fam), prices = customer && (await ensurePrices(env));
  if (!prices) return reply({ error: "payment_error" }, 502);
  // a subscription that isn't live but could still charge (unpaid, incomplete, paused) is ended first, so a new one
  // can never bill alongside it
  const subs = await stripeSubs(env, customer);
  if (!subs) return reply({ error: "payment_error" }, 502);
  for (const sub of subs) {
    if (!OPEN_STATUSES.includes(sub.status)) continue;
    if (LIVE_STATUSES.includes(sub.status)) return reply({ error: "has_plan", account: await accountView(env, await refreshPlan(env, fam, true), s) }, 409);
    const c = await stripe(env, "DELETE", `/subscriptions/${encodeURIComponent(sub.id)}`);
    if (!c.ok && c.status !== 404) return reply({ error: "payment_error" }, 502);
  }
  // an earlier checkout that was never finished is closed first, so two can't both be paid
  const mode = stripeMode(env), prevRaw = fam.checkout_id || null, prev = String(prevRaw || "");
  if (prev.startsWith(mode + ":") && !(await expireCheckout(env, prev.slice(mode.length + 1)))) return reply({ error: "payment_error" }, 502);
  const r = await stripe(env, "POST", "/checkout/sessions", {
    mode: "subscription", customer, client_reference_id: fam.id,
    "line_items[0][price]": prices[plan].id, "line_items[0][quantity]": 1,
    allow_promotion_codes: "true",
    "subscription_data[metadata][family_id]": fam.id,
    expires_at: Math.floor(Date.now() / 1000) + 31 * 60,
    success_url: url.origin + "/?checkout=done", cancel_url: url.origin + "/?checkout=cancel",
  });
  if (!r.ok || !r.data || !/^https?:\/\//.test(String(r.data.url))) return reply({ error: "payment_error" }, 502);
  // saved only if no other checkout was started meanwhile (a double tap); if one was, this one is closed again
  const saved = await env.DB.prepare("UPDATE families SET checkout_id = ? WHERE id = ? AND checkout_id IS ?").bind(mode + ":" + r.data.id, fam.id, prevRaw).run();
  if (!saved.meta || saved.meta.changes !== 1) { await expireCheckout(env, r.data.id); return reply({ error: "busy" }, 409); }
  return reply({ url: r.data.url });
}
// Closes a Checkout Session. True if it's closed now or was already finished; false if Stripe couldn't be asked.
async function expireCheckout(env, id) {
  const r = await stripe(env, "POST", `/checkout/sessions/${encodeURIComponent(id)}/expire`);
  return r.ok || r.status === 400 || r.status === 404;
}
// Switching plans needs a code from the grown-up's email, because Stripe doesn't ask for the card again.
async function changePlan(request, env, url, s) {
  const g = await signedInForPlans(request, env, s);
  if (g.res) return g.res;
  const body = await readJson(request, 1000), plan = body && body.plan;
  if (!isPlan(plan)) return reply({ error: "bad_request" }, 400);
  let fam = await refreshPlan(env, g.fam, true);
  const now = activePlan(fam);
  if (!now) return reply({ error: "no_plan", account: await accountView(env, fam, s) }, 409);
  if (now === plan) return reply({ ok: true, account: await accountView(env, fam, s) });
  const sub = await stripe(env, "GET", `/subscriptions/${encodeURIComponent(fam.sub_id)}`);
  const first = sub.ok && sub.data && sub.data.items && sub.data.items.data && sub.data.items.data[0];
  const prices = first && (await ensurePrices(env));
  if (!prices) return reply({ error: "payment_error" }, 502);
  const c = await checkCode(env, "confirm:" + fam.email, body.code);
  if (!c.ok) return codeReply(c);
  const up = RANK[plan] > RANK[now]; // to unlimited, or from monthly to yearly
  // moving up is charged at once (and only happens if that payment works); moving down is credited on the next bill
  const u = await stripe(env, "POST", `/subscriptions/${encodeURIComponent(fam.sub_id)}`, {
    "items[0][id]": first.id, "items[0][price]": prices[plan].id,
    proration_behavior: up ? "always_invoice" : "create_prorations",
    ...(up ? { payment_behavior: "pending_if_incomplete" } : {}),
  });
  if (!u.ok) return reply({ error: "payment_error" }, 502);
  fam = await refreshPlan(env, fam, true);
  if (u.data && u.data.pending_update) return reply({ error: "payment_failed", account: await accountView(env, fam, s) }, 402);
  return reply({ ok: true, account: await accountView(env, fam, s) });
}
async function portal(request, env, url, s) {
  const g = await signedInForPlans(request, env, s);
  if (g.res) return g.res;
  const cust = customerId(env, g.fam);
  if (!cust) return reply({ error: "no_plan" }, 409);
  let conf = await ensurePortalConfig(env, false);
  const open = c => stripe(env, "POST", "/billing_portal/sessions", { customer: cust, return_url: url.origin + "/?portal=back", configuration: c });
  let r = conf ? await open(conf) : { ok: false, message: "configuration" };
  if (!r.ok && /configuration/i.test(r.message)) { conf = await ensurePortalConfig(env, true); r = conf ? await open(conf) : r; }
  if (!r.ok || !r.data || !/^https?:\/\//.test(String(r.data.url))) return reply({ error: "payment_error" }, 502);
  return reply({ url: r.data.url });
}

// ---------- Claude ----------
async function askClaude(env, body) {
  let res;
  try { res = await fetch(serviceURL(env.ANTHROPIC_BASE_URL, "https://api.anthropic.com") + "/v1/messages", { method: "POST", headers: claudeHeaders(env), body: JSON.stringify(body) }); }
  catch (e) { return { ok: false, status: 0, why: "busy", type: "" }; }
  if (res.ok) return { ok: true, data: await res.json() };
  let err = {};
  try { err = (await res.json()).error || {}; } catch (e) {}
  const msg = String(err.message || ""), code = String((err.details && err.details.error_code) || "");
  let why = "problem";
  if (res.status === 402 || /credit balance/i.test(msg)) why = "billing";
  else if (/usage limits/i.test(msg) || /spend_limit/i.test(code)) why = "limit_reached";
  else if (/workspace/i.test(msg) && (res.status === 400 || res.status === 404)) why = "workspace";
  else if (res.status === 401 || res.status === 403) why = "key_rejected";
  else if (res.status === 429 || res.status === 529 || res.status >= 500) why = "busy";
  return { ok: false, status: res.status, why, type: String(err.type || "").replace(/[^a-z_]/g, "") };
}
function claudeHeaders(env) {
  const h = { "content-type": "application/json", authorization: "Bearer " + env.ANTHROPIC_API_KEY.trim(), "anthropic-version": "2023-06-01" };
  const ws = String(env.ANTHROPIC_WORKSPACE_ID || "").trim();
  if (/^wrkspc_[A-Za-z0-9]+$/.test(ws)) h["anthropic-workspace-id"] = ws;
  return h;
}

// ---------- the setup check: /api/check ----------
const CLAUDE_SAYS = {
  working: "Talks are working: the key is set up and Claude answered.",
  no_key: "There's no ANTHROPIC_API_KEY yet. Add it in Cloudflare (the project, then Settings, then Variables and Secrets), then upload the site again.",
  key_rejected: "Claude didn't accept the key. Check that the whole key was pasted with nothing extra, or make a new key in the Claude Console. Then upload the site again.",
  billing: "The Claude account is out of credit or has a billing problem. Open Billing in the Claude Console to add credit.",
  limit_reached: "This month's spending limit has been reached, so talks are paused until next month. You can raise the limit in Billing in the Claude Console.",
  workspace: "The key isn't tied to one workspace. In the Claude Console, make a new key and choose your workspace when you create it, put the new key in Cloudflare, then upload the site again.",
  busy: "Claude is busy right now. Try again in a minute.",
  problem: "Something unexpected went wrong. Try again later.",
  daily_limit: "Today's limit on Claude use (DAILY_BUDGET, in dollars) has been reached, so talks are paused until midnight UTC. If this happens often, raise DAILY_BUDGET in Cloudflare, then upload the site again.",
};
const checked = new Map(); // the last check for each web address and setup, reused for a minute
async function checkPage(request, env, url, s) {
  const html = /text\/html/.test(request.headers.get("accept") || "");
  const p = plans(env), key = url.host + JSON.stringify([s, String(env.EMAIL_FROM || ""), stripeMode(env), p, String(env.AZURE_SPEECH_REGION || "")]);
  const last = checked.get(key);
  if (last && Date.now() - last.at < 60e3) return html ? checkHtml(last.out) : reply(last.out);
  if (tooMany(request, "check", 6, 30)) return reply({ ok: false, status: "too_many", message: "Too many checks in a row. Wait a minute, then try again." });
  const items = [];
  // today's limit on Claude use, for everyone together
  let overBudget = false;
  if (s.db) {
    try {
      await ensureSchema(env);
      const r = await env.DB.prepare("SELECT micro FROM spend WHERE k = ?").bind(dayKey(Date.now()) + ":*").first();
      overBudget = !!r && Number(r.micro) >= p.dailyBudget;
    } catch (e) {}
  }
  // Claude
  let claude = { ok: false, status: "no_key", message: CLAUDE_SAYS.no_key };
  if (s.claude && overBudget) claude = { ok: false, status: "daily_limit", message: CLAUDE_SAYS.daily_limit };
  else if (s.claude) {
    const r = await askClaude(env, {
      model: MODEL, max_tokens: 16, system: SYSTEM, thinking: { type: "disabled" },
      output_config: { effort: "low", format: { type: "json_schema", schema: SCHEMA } },
      messages: [{ role: "user", content: "This is a setup check. Say hello in Persian." }],
    });
    claude = r.ok ? { ok: true, status: "working", message: CLAUDE_SAYS.working }
      : { ok: false, status: r.why, message: CLAUDE_SAYS[r.why] + (r.why === "problem" && r.type ? ` (Claude said: ${r.type})` : "") };
    if (r.ok && s.db) { try { await ensureSchema(env); await addSpend(env, null, costMicro(r.data.usage)); } catch (e) {} }
  }
  items.push({ name: "Claude (the talks)", ...claude });
  // the database
  if (!s.db) items.push({ name: "Database", ok: false, message: "There's no database yet. Create a D1 database, add it under Settings, then Bindings, with the variable name DB, then upload the site again." });
  else {
    try {
      await ensureSchema(env);
      await env.DB.prepare("SELECT COUNT(*) AS n FROM settings").first();
      items.push({ name: "Database", ok: true, message: "The database is connected." });
    } catch (e) { items.push({ name: "Database", ok: false, message: "The database is there but didn't answer. Check the D1 binding is named DB, then upload the site again." }); }
  }
  // sign-in emails
  const from = fromAddress(env, url), fromDomain = (/@([^\s@>]+)>?$/.exec(from) || [])[1] || "";
  if (!s.email) items.push({ name: "Sign-in emails", ok: false, message: "There's no RESEND_API_KEY yet. Make a key in Resend, add it in Cloudflare, then upload the site again." });
  else if (/\.pages\.dev$/i.test(fromDomain)) items.push({ name: "Sign-in emails", ok: false, message: "Sign-in emails need Alefba's own web address. Connect yours under Custom domains, set EMAIL_FROM to it, then upload the site again." });
  else {
    let msg = `Sign-in emails come from ${from}. To test them, sign in on the site.`, ok = true;
    try {
      const res = await fetch(serviceURL(env.RESEND_BASE_URL, "https://api.resend.com") + "/domains", { headers: { authorization: "Bearer " + env.RESEND_API_KEY.trim() } });
      if (res.status === 401 && !/restricted/i.test(await res.clone().text())) { ok = false; msg = "Resend didn't accept the key. Make a new one in Resend and put it in Cloudflare, then upload again."; }
      else if (res.ok) {
        const d = ((await res.json()).data || []).find(x => String(x.name).toLowerCase() === fromDomain.toLowerCase());
        if (!d) { ok = false; msg = `Add ${fromDomain} under Domains in Resend, so emails can come from it.`; }
        else if (d.status !== "verified") { ok = false; msg = `Resend hasn't verified ${fromDomain} yet (it says: ${String(d.status).replace(/[^a-z_ ]/gi, "")}). Finish the DNS step in Resend, then check again.`; }
      }
    } catch (e) { /* can't look, but the key is set */ }
    items.push({ name: "Sign-in emails", ok, message: msg });
  }
  let robotKeyOk = true;
  if (s.turnstile) { // Cloudflare says whether it knows the secret, even for a made-up check
    try {
      const res = await fetch(serviceURL(env.TURNSTILE_BASE_URL, "https://challenges.cloudflare.com") + "/turnstile/v0/siteverify", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ secret: String(env.TURNSTILE_SECRET_KEY).trim(), response: "alefba-setup-check" }),
      });
      robotKeyOk = !(((await res.json())["error-codes"] || []).includes("invalid-input-secret"));
    } catch (e) { /* can't look, but the keys are set */ }
  }
  items.push(s.turnstile
    ? robotKeyOk ? { name: "Robot check (Turnstile)", ok: true, message: "On: parents pass a quick robot check before a sign-in email is sent." }
      : { name: "Robot check (Turnstile)", ok: false, message: "Cloudflare didn't accept TURNSTILE_SECRET_KEY. Copy the Secret Key again from the Turnstile widget, put it in Cloudflare, then upload the site again." }
    : { name: "Robot check (Turnstile)", ok: false, message: "Not set up yet. Make the free robot check in Cloudflare, add TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY, then upload the site again. It stops anyone using the site to send lots of emails, which could stop parents signing in." });
  // payments
  if (!s.stripe) items.push({ name: "Payments (Stripe)", ok: false, optional: true, message: "Not set up yet, so families get their free talks but can't choose a plan. Add STRIPE_SECRET_KEY to turn on plans." });
  else {
    const acc = await stripe(env, "GET", "/account");
    const prices = acc.ok && s.db ? await ensurePrices(env).catch(() => null) : null;
    if (!acc.ok) items.push({ name: "Payments (Stripe)", ok: false, message: acc.status === 401 ? "Stripe didn't accept the key. Copy the secret key again from Stripe, put it in Cloudflare, then upload again." : "Couldn't reach Stripe with this key. Use the standard secret key, or try again in a minute." });
    else if (!prices) items.push({ name: "Payments (Stripe)", ok: false, message: "Stripe accepted the key but the plans couldn't be set up. Use the standard secret key, which can manage products, prices and customers." });
    else if (stripeMode(env) === "test") items.push({ name: "Payments (Stripe)", ok: true, message: `Test mode: plans are ${dollars(p.basic)} for ${p.basicTalks} talks a month, ${dollars(p.unlimited)} a month for unlimited, or ${dollars(p.yearly)} a year. Try a payment with the card 4242 4242 4242 4242, then switch to the live key.` });
    else if (acc.data && acc.data.charges_enabled === false) items.push({ name: "Payments (Stripe)", ok: false, message: "Live key set, but Stripe can't take payments yet. Finish activating the account in Stripe." });
    else items.push({ name: "Payments (Stripe)", ok: true, message: `Live: plans are ${dollars(p.basic)} for ${p.basicTalks} talks a month, ${dollars(p.unlimited)} a month for unlimited, or ${dollars(p.yearly)} a year.` });
  }
  items.push(s.ai
    ? { name: "Speaking practice (Workers AI)", ok: true, message: "Connected. Talk voice typing works, and families with a plan get speaking practice (they hear themselves next to the real voice)." }
    : { name: "Speaking practice (Workers AI)", ok: false, optional: true, message: "Not set up yet. To let families with a plan practice speaking, add a Workers AI binding with the variable name AI under Settings, then Bindings, then upload the site again." });
  // spoken conversations
  if (!s.voice) items.push({ name: "Spoken conversations (Microsoft voices)", ok: false, optional: true, message: "Not set up yet. Characters are read aloud only on devices with their own Persian voice. To give every family with a plan spoken conversations, make a free Speech resource in Azure, then add AZURE_SPEECH_KEY and AZURE_SPEECH_REGION (like eastus) in Cloudflare and upload the site again." });
  else {
    const r = await azureSpeak(env, "سلام", SAY_VOICES.f, false);
    items.push(r.ok ? { name: "Spoken conversations (Microsoft voices)", ok: true, message: `On: with a plan, characters speak their lines (Dilara and Farid, Microsoft's Persian voices) and learners answer out loud, with Slower and Hint buttons. Microsoft's Persian speech-to-text also listens to the microphone, with Whisper as the back-up.${s.ai ? "" : " Answering out loud also needs the Workers AI binding above."}` }
      : { name: "Spoken conversations (Microsoft voices)", ok: false, message: r.status === 401 || r.status === 403 ? "Azure didn't accept AZURE_SPEECH_KEY for AZURE_SPEECH_REGION. Copy key 1 and the region again from the Speech resource's Keys and Endpoint page, put them in Cloudflare, then upload the site again." : r.status === 404 ? "AZURE_SPEECH_REGION doesn't look right. Use the short region name from the Speech resource, like eastus or westeurope." : "Azure's voice service couldn't be reached right now. Try again in a minute." });
  }
  const ok = items.every(i => i.ok || i.optional);
  const out = { ok, status: claude.status, message: claude.message, items };
  if (checked.size > 50) checked.clear();
  checked.set(key, { at: Date.now(), out });
  return html ? checkHtml(out) : reply(out);
}
function checkHtml(out) {
  const esc = t => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const rows = out.items.map(i => `<li class="${i.ok ? "ok" : i.optional ? "opt" : "bad"}"><b>${i.ok ? "✓" : i.optional ? "–" : "✗"} ${esc(i.name)}</b><span>${esc(i.message)}</span></li>`).join("");
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Alefba setup check</title>
<style>:root{color-scheme:light dark;--bg:#f2f6f7;--card:#fff;--ink:#13293a;--muted:#5a7282;--ok:#1d7a3e;--bad:#b3261e;--opt:#8f5d07}@media(prefers-color-scheme:dark){:root{--bg:#0b1820;--card:#112430;--ink:#e4eef1;--muted:#8fa8b3;--ok:#5cc98a;--bad:#ff8a80;--opt:#f0b649}}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,sans-serif}main{max-width:40rem;margin:0 auto;padding:24px 16px}h1{font-size:1.5rem;margin:0 0 4px}p{margin:0 0 16px;color:var(--muted)}ul{list-style:none;padding:0;margin:0;display:grid;gap:10px}li{background:var(--card);border-radius:12px;padding:12px 14px;display:grid;gap:4px;border-left:5px solid}li.ok{border-color:var(--ok)}li.bad{border-color:var(--bad)}li.opt{border-color:var(--opt)}li.ok b{color:var(--ok)}li.bad b{color:var(--bad)}li.opt b{color:var(--opt)}</style></head>
<body><main><h1>${out.ok ? "Alefba is ready" : "Alefba setup check"}</h1><p>${out.ok ? "Everything needed for talks is working." : "Fix the items marked ✗, upload the site again, then reload this page in a minute."}</p><ul>${rows}</ul></main></body></html>`;
  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" } });
}

// ---------- what a talk may contain ----------
// A talk must look like one from the app: it starts with the app's instructions for a character, of the size
// the app really sends, then takes turns, child and character. Children's messages are kept short and cleaned.
const PERSIAN = /[؀-ۿﭐ-﷿ﹰ-﻿‌-‏]/g;
const OTHER = /[^\u0000-ɏ؀-ۿﭐ-﷿ﹰ-﻿ -⁯←-⇿]/gu;
function checkTurns(turns) {
  if (!Array.isArray(turns) || turns.length < 1 || turns.length > LIMITS.turns) return null;
  let total = 0, bytes = 0;
  const out = [];
  for (let i = 0; i < turns.length; i++) {
    const t = turns[i];
    if (!t || typeof t.content !== "string") return null;
    const role = i % 2 === 0 ? "user" : "assistant";
    if (t.role !== role) return null;
    let text = t.content;
    total += text.length;
    if (i === 0) {
      if (text.length > LIMITS.firstChars || !/^You are .{1,200}in a Persian practice app for (children|adults)/.test(text)) return null;
      if ((text.match(PERSIAN) || []).length > LIMITS.firstPersian || (text.match(OTHER) || []).length > LIMITS.firstOther) return null;
    } else if (role === "user") {
      text = cleanChild(text);
    } else {
      // an earlier reply must be one of Claude's replies as the app keeps it, so it can't be padded with anything else
      text = earlierReply(text);
      if (!text) return null;
    }
    bytes += utf8(text);
    out.push({ role, content: i === 0 ? [{ type: "text", text, cache_control: { type: "ephemeral" } }] : text });
  }
  if (total > LIMITS.totalChars || bytes > LIMITS.totalBytes || out[out.length - 1].role !== "user") return null;
  out.bytes = bytes;
  return out;
}
// The reply's fields only, as the app keeps them, in the alphabets the app uses (Latin, Persian, and Chinese for
// meanings in Chinese). Anything else, or a reply longer than any real one, is refused.
const REPLY_OTHER = /[^\u0000-ɏḀ-ỿ؀-ۿﭐ-﷿ﹰ-﻿ -⁯←-⇿　-〿㐀-䶿一-鿿＀-￯]/gu;
function earlierReply(text) {
  if (text.length > LIMITS.assistantChars) return null;
  let r;
  try { r = JSON.parse(text); } catch (e) { return null; }
  const str = v => (typeof v === "string" && v.length <= 1000 ? v : null);
  if (!r || typeof r !== "object" || Array.isArray(r) || !str(r.fa)) return null;
  const item = x => (x && typeof x === "object" && str(x.fa) !== null ? { fa: x.fa, translit: str(x.translit) || "", en: str(x.en) || "" } : null);
  const list = (v, max) => (Array.isArray(v) && v.length <= max ? v.map(item) : null);
  const sugs = list(r.suggestions || [], 6), words = list(r.new_words || [], 8);
  if (!sugs || !words || sugs.includes(null) || words.includes(null)) return null;
  const fb = r.feedback;
  if (fb !== null && fb !== undefined && (typeof fb !== "object" || Array.isArray(fb))) return null;
  const goals = Array.isArray(r.goals_done) ? r.goals_done : [];
  if (goals.length > 10 || !goals.every(n => Number.isInteger(n) && n >= 0 && n <= 20)) return null;
  const clean = JSON.stringify({
    fa: r.fa, translit: str(r.translit) || "", en: str(r.en) || "", written: str(r.written) || "", written_translit: str(r.written_translit) || "",
    feedback: fb ? { note: str(fb.note) || "", better_fa: str(fb.better_fa) || "", better_translit: str(fb.better_translit) || "" } : null,
    suggestions: sugs, new_words: words, goals_done: goals,
    pace: ["harder", "same", "easier"].includes(r.pace) ? r.pace : "same", done: r.done === true,
  });
  if (clean.length > LIMITS.assistantChars || (clean.match(REPLY_OTHER) || []).length > LIMITS.assistantOther) return null;
  return clean;
}
// What a child types: at most a short message, with email addresses, links and phone numbers taken out.
// The app's own notes around the child's words are kept, cut to a short length.
const HELP = /^(\(The (?:child|learner) is asking for help: how do you say ")([\s\S]*)(" in everyday spoken Persian\?[\s\S]{0,400})$/;
function cleanChild(text) {
  text = text.slice(0, LIMITS.childChars * 4); // bounded before any pattern looks at it, so a huge message can't cost seconds of work
  const note = text.indexOf("\n\n(Note from the app");
  const words = note >= 0 ? text.slice(0, note) : text, rest = note >= 0 ? text.slice(note, note + 300) : "";
  const m = HELP.exec(words);
  const child = m ? m[1] + scrub(m[2]).slice(0, LIMITS.childChars) + m[3] : scrub(words).slice(0, LIMITS.childChars);
  return child + rest;
}
function scrub(s) {
  return s
    .replace(/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, "[removed]")
    .replace(/\b(?:https?:\/\/|www\.)\S+/gi, "[removed]")
    .replace(/(?:\+|00)?[\d۰-۹٠-٩][\d۰-۹٠-٩\s().-]{6,}[\d۰-۹٠-٩]/g, m => (m.replace(/\D/g, "").length + (m.match(/[۰-۹٠-٩]/g) || []).length >= 7 ? "[removed]" : m));
}

// ---------- the parents, adults and teachers pages, with the plans and contact email from the settings ----------
async function parentsPage(request, env) {
  if (request.method !== "GET" && request.method !== "HEAD") return env.ASSETS.fetch(request);
  const ask = new Headers(request.headers);
  ask.delete("if-none-match"); ask.delete("if-modified-since"); // always the whole page, so a changed email shows at once
  const res = await env.ASSETS.fetch(new Request(request.url, { method: request.method, headers: ask }));
  if (res.status !== 200) return res;
  let html = request.method === "HEAD" ? "" : await res.text();
  const p = plans(env), values = { free: String(p.free), basicTalks: String(p.basicTalks), perDay: String(p.perDay), basicPrice: dollars(p.basic), unlimitedPrice: dollars(p.unlimited), yearlyPrice: dollars(p.yearly), schoolPrice: dollars(p.school), freeLevels: String(FREE_LEVELS) };
  html = html.replace(/<!--v:(\w+)-->[\s\S]*?<!--\/v-->/g, (m, k) => (k in values ? values[k] : m)); // the plans as they're set now
  const sv = services(env), on = { turnstile: sv.turnstile, hear: sv.ai, voice: sv.voice && sv.ai };
  html = html.replace(/<!--if:(\w+)-->([\s\S]*?)<!--\/if-->/g, (m, k, inner) => (on[k] ? inner : "")); // the robot check and speaking practice, only if they're on
  const email = contactEmail(env);
  const path = new URL(request.url).pathname, adults = /^\/adults(\.html)?$/.test(path), teachers = /^\/teachers(\.html)?$/.test(path);
  if (email) html = html.replace(/<!--contact-->[\s\S]*?<!--\/contact-->/,
    `<p>Write to us at <a href="mailto:${email}">${email}</a>. We're happy to help, and we'll answer any request about ${adults ? "your" : teachers ? "your class's" : "your child's"} information.</p>`);
  const headers = new Headers(res.headers);
  for (const h of ["etag", "last-modified", "content-length", "content-encoding"]) headers.delete(h);
  headers.set("cache-control", "no-cache");
  return new Response(request.method === "HEAD" ? null : html, { status: 200, headers });
}
function contactEmail(env) {
  const s = String(env.CONTACT_EMAIL || "").trim();
  return /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/.test(s) ? s : "";
}

// ---------- classes (teacher mode) ----------
const CLASS = { maxClasses: 20, maxMembers: 60, maxAssigned: 40, nameMax: 40, learnerNameMax: 24, progressBytes: 8000 };
const JOIN_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // no 0, O, 1 or I, which are easy to mix up
const LESSON_ID = /^[a-z][a-z0-9-]{0,23}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
function joinCode() { return [...randomBytes(6)].map(b => JOIN_LETTERS[b % 32]).join(""); }
const cleanCode = v => { const c = latinDigits(String(v == null ? "" : v)).toUpperCase().replace(/[\s-]/g, ""); return /^[A-HJ-NP-Z2-9]{6}$/.test(c) ? c : ""; };
// A class name, or a learner's first name or nickname: plain text, short, and never an email address, a link or a
// phone number (those would be personal details a teacher's screen doesn't need).
function cleanLabel(v, max, isLearner) {
  const t = String(v == null ? "" : v).normalize("NFC").replace(/[\u0000-\u001f\u007f-\u009f​‎‏‪-‮⁦-⁩]/g, "").replace(/\s+/g, " ").trim();
  if (!t || [...t].length > max) return "";
  if (/@|https?:|www\.|\.(com|org|net|io)\b/i.test(t)) return "";
  if (isLearner && /\d{5,}/.test(latinDigits(t).replace(/[\s().+-]/g, ""))) return "";
  return t;
}
const parseList = v => { try { const a = JSON.parse(v || "[]"); return Array.isArray(a) ? a.filter(x => typeof x === "string" && LESSON_ID.test(x)) : []; } catch (e) { return []; } };
const parseObj = v => { try { const o = JSON.parse(v || "null"); return o && typeof o === "object" && !Array.isArray(o) ? o : null; } catch (e) { return null; } };
// What a learner's device sends: counts and lesson names only, each checked and capped.
function cleanProgress(p) {
  if (!p || typeof p !== "object" || Array.isArray(p)) return null;
  const num = (v, max) => (Number.isFinite(v) ? Math.max(0, Math.min(max, Math.floor(v))) : 0);
  const ids = Array.isArray(p.done) ? [...new Set(p.done.filter(x => typeof x === "string" && LESSON_ID.test(x)))].slice(0, 400) : [];
  const days = Array.isArray(p.days) ? [...new Set(p.days.filter(d => typeof d === "string" && DATE_RE.test(d)))].sort().slice(-31) : [];
  return { done: ids, days, streak: num(p.streak, 400), best: num(p.best, 400), letters: num(p.letters, 32), words: num(p.words, 5000), today: typeof p.today === "string" && DATE_RE.test(p.today) ? p.today : "" };
}
async function teacherAndClass(request, env, s, body) {
  if (!s.db) return { res: reply({ error: "not_configured" }, 503) };
  const fam = await currentFamily(request, env);
  if (!fam) return { res: reply({ error: "sign_in" }, 401) };
  if (tooMany(request, "class", 30, 400)) return { res: reply({ error: "too_many" }, 429) };
  if (body === undefined) return { fam };
  const id = body && typeof body.id === "string" && /^[0-9a-f]{24}$/.test(body.id) ? body.id : "";
  const c = id && (await env.DB.prepare("SELECT * FROM classes WHERE id = ? AND teacher_id = ?").bind(id, fam.id).first());
  if (!c) return { res: reply({ error: "not_found" }, 404) };
  return { fam, c };
}
const classOut = (c, members) => ({ id: c.id, name: c.name, code: c.code, assigned: parseList(c.assigned), paidUntil: Number(c.paid_until) || 0, pending: !!c.checkout_id, ...(members == null ? {} : { members }) });
// What a learner's device is told about its class: the name, the assigned lessons, and whether the class has a school plan.
const memberClass = c => { const until = Number(c.paid_until) || 0; return { name: c.class_name || c.name, assigned: parseList(c.assigned), fullUntil: until > Date.now() ? until : 0 }; };
async function classCreate(request, env, url, s) {
  const t = await teacherAndClass(request, env, s);
  if (t.res) return t.res;
  const body = (await readJson(request, 2000)) || {};
  const name = cleanLabel(body.name, CLASS.nameMax, false);
  if (!name) return reply({ error: "bad_name" }, 400);
  const n = await env.DB.prepare("SELECT COUNT(*) AS n FROM classes WHERE teacher_id = ?").bind(t.fam.id).first();
  if (n && n.n >= CLASS.maxClasses) return reply({ error: "too_many_classes" }, 409);
  for (let i = 0; i < 6; i++) {
    const c = { id: randomId(), name, code: joinCode(), assigned: "[]" };
    try {
      await env.DB.prepare("INSERT INTO classes (id, teacher_id, name, code, created_at, assigned) VALUES (?, ?, ?, ?, ?, '[]')").bind(c.id, t.fam.id, c.name, c.code, Date.now()).run();
      return reply({ class: classOut(c, 0) });
    } catch (e) { /* that code is taken: try another */ }
  }
  return reply({ error: "server_error" }, 500);
}
async function classList(request, env, url, s) {
  const t = await teacherAndClass(request, env, s);
  if (t.res) return t.res;
  let rows = (await env.DB.prepare("SELECT c.*, (SELECT COUNT(*) FROM class_members m WHERE m.class_id = c.id) AS n FROM classes c WHERE c.teacher_id = ? ORDER BY c.created_at").bind(t.fam.id).all()).results || [];
  if (s.stripe && rows.some(c => c.checkout_id)) rows = await Promise.all(rows.map(c => (c.checkout_id ? schoolPaidCheck(env, c) : c)));
  return reply({ classes: rows.map(c => classOut(c, Number(c.n) || 0)) });
}
async function classView(request, env, url, s) {
  const t = await teacherAndClass(request, env, s, (await readJson(request, 1000)) || {});
  if (t.res) return t.res;
  if (s.stripe && t.c.checkout_id) t.c = await schoolPaidCheck(env, t.c); // back from paying: the school plan is on now
  const rows = (await env.DB.prepare("SELECT id, name, joined_at, seen_at, progress FROM class_members WHERE class_id = ? ORDER BY name COLLATE NOCASE, joined_at").bind(t.c.id).all()).results || [];
  return reply({ class: classOut(t.c, rows.map(m => ({ id: m.id, name: m.name, joined: m.joined_at, seen: m.seen_at, progress: cleanProgress(parseObj(m.progress)) }))) });
}
async function classAssign(request, env, url, s) {
  const body = (await readJson(request, 4000)) || {};
  const t = await teacherAndClass(request, env, s, body);
  if (t.res) return t.res;
  if (!Array.isArray(body.lessons)) return reply({ error: "bad_request" }, 400);
  const list = [...new Set(body.lessons.filter(x => typeof x === "string" && LESSON_ID.test(x)))];
  if (list.length > CLASS.maxAssigned) return reply({ error: "too_many_lessons" }, 400);
  await env.DB.prepare("UPDATE classes SET assigned = ? WHERE id = ?").bind(JSON.stringify(list), t.c.id).run();
  return reply({ class: classOut({ ...t.c, assigned: JSON.stringify(list) }) });
}
async function classRemove(request, env, url, s) {
  const body = (await readJson(request, 1000)) || {};
  const t = await teacherAndClass(request, env, s, body);
  if (t.res) return t.res;
  const member = typeof body.member === "string" && /^[0-9a-f]{24}$/.test(body.member) ? body.member : "";
  if (!member) return reply({ error: "bad_request" }, 400);
  await env.DB.prepare("DELETE FROM class_members WHERE id = ? AND class_id = ?").bind(member, t.c.id).run();
  return reply({ ok: true });
}
async function classDelete(request, env, url, s) {
  const t = await teacherAndClass(request, env, s, (await readJson(request, 1000)) || {});
  if (t.res) return t.res;
  if (t.c.checkout_id && s.stripe) { // a school plan checkout still open is closed first, so it can't be paid for a class that's gone
    t.c = await schoolPaidCheck(env, t.c);
    if (t.c.checkout_id && t.c.checkout_status === "complete") return reply({ error: "pending_payment" }, 409);
  }
  if (t.c.checkout_id && s.stripe) {
    const mode = stripeMode(env), v = String(t.c.checkout_id);
    if (v.startsWith(mode + ":") && !(await expireCheckout(env, v.slice(mode.length + 1)))) return reply({ error: "payment_error" }, 502);
  }
  await env.DB.batch([
    env.DB.prepare("DELETE FROM class_members WHERE class_id = ?").bind(t.c.id),
    env.DB.prepare("DELETE FROM classes WHERE id = ?").bind(t.c.id),
  ]);
  return reply({ ok: true });
}
// A learner's device: it joins with the code and gets its own key back, which it keeps instead of signing in.
async function classJoin(request, env, url, s) {
  if (!s.db) return reply({ error: "not_configured" }, 503);
  if (tooMany(request, "join", 6, 30)) return reply({ error: "too_many" }, 429);
  const body = (await readJson(request, 1000)) || {};
  const code = cleanCode(body.code);
  if (!code) return reply({ error: "bad_code" }, 400);
  const name = cleanLabel(body.name, CLASS.learnerNameMax, true);
  if (!name) return reply({ error: "bad_name" }, 400);
  const c = await env.DB.prepare("SELECT * FROM classes WHERE code = ?").bind(code).first();
  if (!c) return reply({ error: "bad_code" }, 404);
  const n = await env.DB.prepare("SELECT COUNT(*) AS n FROM class_members WHERE class_id = ?").bind(c.id).first();
  if (n && n.n >= CLASS.maxMembers) return reply({ error: "class_full" }, 409);
  const token = randomToken(), now = Date.now();
  await env.DB.prepare("INSERT INTO class_members (id, class_id, token_hash, name, joined_at, seen_at, progress) VALUES (?, ?, ?, ?, ?, ?, NULL)").bind(randomId(), c.id, await sha256(token), name, now, now).run();
  return reply({ token, name, class: memberClass(c) });
}
async function memberOf(env, token) {
  if (typeof token !== "string" || !/^[A-Za-z0-9_-]{40,50}$/.test(token)) return null;
  return env.DB.prepare("SELECT m.id, m.name, c.id AS cid, c.name AS class_name, c.assigned, c.paid_until, c.checkout_id FROM class_members m JOIN classes c ON c.id = m.class_id WHERE m.token_hash = ?").bind(await sha256(token)).first();
}
async function classMine(request, env, url, s) {
  if (!s.db) return reply({ error: "not_configured" }, 503);
  if (tooMany(request, "classme", 30, 300)) return reply({ error: "too_many" }, 429);
  let m = await memberOf(env, ((await readJson(request, 1000)) || {}).token);
  if (!m) return reply({ error: "not_in_class" }, 404);
  m = await schoolCheckForMember(env, s, m);
  await env.DB.prepare("UPDATE class_members SET seen_at = ? WHERE id = ?").bind(Date.now(), m.id).run();
  return reply({ name: m.name, class: memberClass(m) });
}
async function classProgress(request, env, url, s) {
  if (!s.db) return reply({ error: "not_configured" }, 503);
  if (tooMany(request, "classprog", 30, 300)) return reply({ error: "too_many" }, 429);
  const body = await readJson(request, CLASS.progressBytes);
  if (!body) return reply({ error: "bad_request" }, 400);
  let m = await memberOf(env, body.token);
  if (!m) return reply({ error: "not_in_class" }, 404);
  m = await schoolCheckForMember(env, s, m);
  const p = cleanProgress(body.progress);
  if (!p) return reply({ error: "bad_request" }, 400);
  await env.DB.prepare("UPDATE class_members SET progress = ?, seen_at = ? WHERE id = ?").bind(JSON.stringify(p), Date.now(), m.id).run();
  return reply({ name: m.name, class: memberClass(m) });
}
async function classLeave(request, env, url, s) {
  if (!s.db) return reply({ error: "not_configured" }, 503);
  if (tooMany(request, "classme", 30, 300)) return reply({ error: "too_many" }, 429);
  const token = ((await readJson(request, 1000)) || {}).token;
  if (typeof token === "string" && /^[A-Za-z0-9_-]{40,50}$/.test(token)) await env.DB.prepare("DELETE FROM class_members WHERE token_hash = ?").bind(await sha256(token)).run();
  return reply({ ok: true });
}

// ---------- school plan: one class, all the levels for everyone in it, for a year ----------
// Paid once through Stripe Checkout (no subscription, so nothing renews by itself). When the teacher comes back, or next
// opens teacher mode, the payment is checked with Stripe and the class gets a year (added to any time it still has).
const SCHOOL_DAYS = 365;
async function classCheckout(request, env, url, s) {
  if (!plansReady(s)) return reply({ error: "not_configured" }, 503);
  const body = (await readJson(request, 1000)) || {};
  const t = await teacherAndClass(request, env, s, body);
  if (t.res) return t.res;
  if (tooMany(request, "plans", 10, 60)) return reply({ error: "too_many" }, 429);
  const c = t.c.checkout_id ? await schoolPaidCheck(env, t.c) : t.c;
  if (c.checkout_id && c.checkout_status === "complete") return reply({ error: "pending_payment", class: classOut(c) }, 409); // paid, still being confirmed: never replaced
  if (Number(c.paid_until) > Date.now() + 60 * 864e5) return reply({ error: "has_plan", class: classOut(c) }, 409); // more than two months left: renew later
  const customer = await ensureCustomer(env, t.fam);
  if (!customer) return reply({ error: "payment_error" }, 502);
  const mode = stripeMode(env), prevRaw = c.checkout_id || null, prev = String(prevRaw || "");
  if (prev.startsWith(mode + ":") && !(await expireCheckout(env, prev.slice(mode.length + 1)))) return reply({ error: "payment_error" }, 502);
  const p = plans(env);
  const r = await stripe(env, "POST", "/checkout/sessions", {
    mode: "payment", customer, client_reference_id: t.fam.id,
    "line_items[0][quantity]": 1,
    "line_items[0][price_data][currency]": "usd",
    "line_items[0][price_data][unit_amount]": p.school,
    "line_items[0][price_data][product_data][name]": `Alefba school plan: ${c.name}, one year`,
    "line_items[0][price_data][product_data][metadata][alefba_plan]": "school",
    "metadata[class_id]": c.id, "payment_intent_data[metadata][class_id]": c.id,
    allow_promotion_codes: "true",
    expires_at: Math.floor(Date.now() / 1000) + 31 * 60,
    success_url: url.origin + "/?school=done&class=" + c.id, cancel_url: url.origin + "/?school=cancel",
  });
  if (!r.ok || !r.data || !/^https?:\/\//.test(String(r.data.url))) return reply({ error: "payment_error" }, 502);
  const saved = await env.DB.prepare("UPDATE classes SET checkout_id = ? WHERE id = ? AND checkout_id IS ?").bind(mode + ":" + r.data.id, c.id, prevRaw).run();
  if (!saved.meta || saved.meta.changes !== 1) { await expireCheckout(env, r.data.id); return reply({ error: "busy" }, 409); }
  return reply({ url: r.data.url });
}
// A class with a checkout in progress: asks Stripe whether it was paid. A paid one adds a year, once (the update only
// happens while the checkout is still the one saved, so two checks at once can't add two years).
const SCHOOL_PAID = ["paid", "no_payment_required"]; // no_payment_required: a promotion code covered all of it
async function schoolPaidCheck(env, c) {
  const mode = stripeMode(env), v = String(c.checkout_id || "");
  if (!v) return c;
  if (!v.startsWith(mode + ":")) { // made in Stripe's other mode (test vs live): it can't be checked with this key
    await env.DB.prepare("UPDATE classes SET checkout_id = NULL WHERE id = ? AND checkout_id = ?").bind(c.id, v).run();
    return { ...c, checkout_id: null };
  }
  const id = v.slice(mode.length + 1);
  const r = await stripe(env, "GET", `/checkout/sessions/${encodeURIComponent(id)}`);
  if (!r.ok || !r.data) { if (r.status === 404) await env.DB.prepare("UPDATE classes SET checkout_id = NULL WHERE id = ? AND checkout_id = ?").bind(c.id, v).run(); return r.status === 404 ? { ...c, checkout_id: null } : c; }
  const meta = r.data.metadata || {};
  if (SCHOOL_PAID.includes(r.data.payment_status) && meta.class_id === c.id) {
    const now = Date.now(), until = Math.max(Number(c.paid_until) || 0, now) + SCHOOL_DAYS * 864e5;
    const u = await env.DB.prepare("UPDATE classes SET paid_until = ?, checkout_id = NULL WHERE id = ? AND checkout_id = ?").bind(until, c.id, v).run();
    if (u.meta && u.meta.changes === 1) return { ...c, paid_until: until, checkout_id: null };
    return (await env.DB.prepare("SELECT * FROM classes WHERE id = ?").bind(c.id).first()) || c;
  }
  if (r.data.status === "expired") { await env.DB.prepare("UPDATE classes SET checkout_id = NULL WHERE id = ? AND checkout_id = ?").bind(c.id, v).run(); return { ...c, checkout_id: null }; }
  return { ...c, checkout_status: r.data.status }; // "open", or "complete" with a payment still on its way (a bank payment, say)
}
// Learners' devices check in often: while a class has a payment in progress, Stripe is asked at most once a minute per class.
const schoolAsked = new Map();
async function schoolCheckForMember(env, s, m) {
  if (!s.stripe || !m.checkout_id) return m;
  const now = Date.now();
  if (now - (schoolAsked.get(m.cid) || 0) < 60e3) return m;
  schoolAsked.set(m.cid, now);
  if (schoolAsked.size > 2000) schoolAsked.clear();
  const c = await schoolPaidCheck(env, { id: m.cid, checkout_id: m.checkout_id, paid_until: m.paid_until });
  return { ...m, paid_until: c.paid_until };
}

// ---------- progress on every device ----------
// A signed-in grown-up turns it on for the family. Each learner's progress is then kept here as one small record (a
// first name or nickname, lessons, scores, practice days and settings: never anything from the talks), and merged with
// what each device has, so it's the same everywhere. Turning it off deletes every record at once.
const SYNC = { learners: 8, stateChars: 100000, gone: 50 };
// never kept online: the class key (it stays on the device that joined) and how many talks were had
const syncable = st => { const o = { ...st }; delete o.cls; delete o.talks; return o; };
const SID = /^[0-9a-f]{24}$/;
async function syncFamily(request, env, s, max) {
  if (!s.db) return { res: reply({ error: "not_configured" }, 503) };
  const fam = await currentFamily(request, env);
  if (!fam) return { res: reply({ error: "sign_in" }, 401) };
  if (tooMany(request, "sync", 30, 600)) return { res: reply({ error: "too_many" }, 429) };
  return { fam, body: (await readJson(request, max)) || {} };
}
async function syncOn(request, env, url, s) {
  const g = await syncFamily(request, env, s, 1000);
  if (g.res) return g.res;
  if (g.body.agree !== true) return reply({ error: "agree" }, 400); // the grown-up said yes to keeping progress online
  await env.DB.prepare("UPDATE families SET sync_on = ? WHERE id = ?").bind(Date.now(), g.fam.id).run();
  return reply({ ok: true, sync: true });
}
async function syncOff(request, env, url, s) {
  const g = await syncFamily(request, env, s, 1000);
  if (g.res) return g.res;
  await env.DB.batch([
    env.DB.prepare("DELETE FROM progress WHERE family_id = ?").bind(g.fam.id),
    env.DB.prepare("UPDATE families SET sync_on = NULL, sync_gone = NULL WHERE id = ?").bind(g.fam.id),
  ]);
  return reply({ ok: true, sync: false });
}
async function syncRemove(request, env, url, s) {
  const g = await syncFamily(request, env, s, 1000);
  if (g.res) return g.res;
  const sid = typeof g.body.sid === "string" && SID.test(g.body.sid) ? g.body.sid : "";
  if (!sid) return reply({ error: "bad_request" }, 400);
  const gone = [...new Set([...parseSids(g.fam.sync_gone), sid])].slice(-SYNC.gone);
  await env.DB.batch([
    env.DB.prepare("DELETE FROM progress WHERE family_id = ? AND sid = ?").bind(g.fam.id, sid),
    env.DB.prepare("UPDATE families SET sync_gone = ? WHERE id = ?").bind(JSON.stringify(gone), g.fam.id),
  ]);
  return reply({ ok: true });
}
const parseSids = v => { try { const a = JSON.parse(v || "[]"); return Array.isArray(a) ? a.filter(x => typeof x === "string" && SID.test(x)) : []; } catch (e) { return []; } };
// Each device sends its learners: ones it already shares (with their sid) and new ones (with a temporary lid). A new one
// with the same name as a shared one that this device doesn't have yet is the same learner (Sara on the laptop and Sara on
// the tablet), so the two are merged. The reply is every learner the family has, merged.
async function syncProgress(request, env, url, s) {
  const g = await syncFamily(request, env, s, SYNC.learners * (SYNC.stateChars + 200) + 2000);
  if (g.res) return g.res;
  const { fam, body } = g;
  if (!fam.sync_on) return reply({ error: "sync_off" }, 409);
  if (!Array.isArray(body.learners) || body.learners.length > SYNC.learners) return reply({ error: "bad_request" }, 400);
  const incoming = [];
  for (const l of body.learners) {
    if (!l || typeof l !== "object" || !l.state || typeof l.state !== "object" || Array.isArray(l.state)) return reply({ error: "bad_request" }, 400);
    const sid = typeof l.sid === "string" && SID.test(l.sid) ? l.sid : "", lid = typeof l.lid === "string" && /^[a-z0-9]{1,24}$/.test(l.lid) ? l.lid : "";
    if (!sid && !lid) return reply({ error: "bad_request" }, 400);
    incoming.push({ sid, lid, state: syncable(l.state) });
  }
  const rows = (await env.DB.prepare("SELECT sid, state, updated_at FROM progress WHERE family_id = ?").bind(fam.id).all()).results || [];
  const stored = new Map(rows.map(r => [r.sid, { state: parseObj(r.state) || {}, updated: Number(r.updated_at) }]));
  const gone = new Set(parseSids(fam.sync_gone)), sent = new Set(incoming.filter(l => l.sid).map(l => l.sid));
  const nameOf = st => String((st && st.profile && !st.profile.skipped && st.profile.name) || "").trim().toLowerCase();
  const writes = [], lidOf = new Map(), skipped = [], now = Date.now();
  for (const l of incoming) {
    if (l.sid && gone.has(l.sid)) continue; // removed on another device: not brought back
    let sid = l.sid;
    if (!sid) { // a learner this device hasn't shared yet: the same one by name, or a new one
      const nm = nameOf(l.state);
      sid = (nm && [...stored.keys()].find(k => !sent.has(k) && ![...lidOf.values()].includes(k) && nameOf(stored.get(k).state) === nm)) || randomId();
      lidOf.set(l.lid, sid);
    }
    const before = stored.get(sid);
    const merged = syncable(before ? mergeProgress(before.state, l.state) : l.state);
    merged.sid = sid;
    if (JSON.stringify(merged).length > SYNC.stateChars) { skipped.push(l.lid || sid); continue; } // far bigger than any real one: left as it was
    if (!before && stored.size >= SYNC.learners) continue; // the family's limit
    stored.set(sid, { state: merged, updated: now });
    writes.push(env.DB.prepare("INSERT INTO progress (family_id, sid, state, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(family_id, sid) DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at").bind(fam.id, sid, JSON.stringify(merged), now));
  }
  if (writes.length) await env.DB.batch(writes);
  // a learner removed on another device while this request ran isn't brought back
  const goneNow = parseSids(((await env.DB.prepare("SELECT sync_gone FROM families WHERE id = ?").bind(fam.id).first()) || {}).sync_gone);
  const back = goneNow.filter(x => stored.has(x));
  if (back.length) { await env.DB.batch(back.map(x => env.DB.prepare("DELETE FROM progress WHERE family_id = ? AND sid = ?").bind(fam.id, x))); back.forEach(x => stored.delete(x)); }
  goneNow.forEach(x => gone.add(x));
  const lids = Object.fromEntries([...lidOf].map(([lid, sid]) => [sid, lid]));
  return reply({ learners: [...stored].map(([sid, v]) => ({ sid, state: v.state, updated: v.updated, ...(lids[sid] ? { lid: lids[sid] } : {}) })), gone: [...gone], ...(skipped.length ? { skipped } : {}) });
}
// Two copies of one learner's progress, made into one: lessons, practice days and scores from both, and settings, name
// and level from whichever copy was saved last. The app does the same merge, so a device and the server always agree.
function mergeProgress(a, b) {
  const obj = v => (v && typeof v === "object" && !Array.isArray(v) ? v : {});
  const A = obj(a), B = obj(b), num = v => Number(v) || 0;
  const [old, neu] = num(A.updated) > num(B.updated) ? [B, A] : [A, B];
  const out = { ...old, ...neu };
  // lessons done for real on either copy stay done; the marks from a level check ("test") come from the copy whose
  // check is newer, so a check taken again (or failed) can take them away
  const tests = num(A.testAt) === num(B.testAt) ? neu : num(A.testAt) > num(B.testAt) ? A : B;
  const done = {};
  for (const src of [obj(old.done), obj(neu.done)]) for (const [k, v] of Object.entries(src)) if (v === true) done[k] = true;
  for (const [k, v] of Object.entries(obj(tests.done))) if (v === "test" && !done[k]) done[k] = "test";
  out.done = done;
  out.testAt = Math.max(num(A.testAt), num(B.testAt));
  const firsts = [A.firstDay, B.firstDay].filter(d => typeof d === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d)).sort(); // the day this learner first opened the app, on any device
  if (firsts.length) out.firstDay = firsts[0];
  const items = {};
  for (const src of [obj(old.items), obj(neu.items)]) for (const [k, v] of Object.entries(src)) {
    const e = items[k] || { r: 0, w: 0 }, x = obj(v);
    items[k] = { r: Math.max(e.r, num(x.r)), w: Math.max(e.w, num(x.w)) };
  }
  out.items = items;
  const dates = (x, y, keep) => [...new Set([...(Array.isArray(x) ? x : []), ...(Array.isArray(y) ? y : [])].filter(d => typeof d === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d)))].sort().slice(-keep);
  out.days = dates(old.days, neu.days, 400);
  out.restDays = dates(old.restDays, neu.restDays, 60); // days a rest day covered
  out.restGot = dates(old.restGot, neu.restGot, 60);    // days a rest day was earned
  out.rest = Math.max(0, Math.min(2, out.restGot.length - out.restDays.length));
  const maxed = (x, y) => { const o = { ...obj(x) }; for (const [k, v] of Object.entries(obj(y))) o[k] = Math.max(num(o[k]), num(v)); return o; };
  const log = maxed(old.log, neu.log);
  out.log = Object.fromEntries(Object.keys(log).sort().slice(-31).map(k => [k, log[k]])); // the app keeps a month of these
  out.talks = maxed(old.talks, neu.talks);
  out.best = Math.max(num(old.best), num(neu.best));
  out.rewardsSeen = { ...obj(old.rewardsSeen), ...obj(neu.rewardsSeen) };
  out.fseen = { ...obj(old.fseen), ...obj(neu.fseen) }; // words whose Finglish has been shown in a question
  out.tips = { ...obj(old.tips), ...obj(neu.tips) };
  return out;
}

// ---------- storage (D1) ----------
// The tables are made the first time they're needed, and brought up to date if an earlier version made them.
const SCHEMA_VERSION = 7;
const SCHEMA_TABLES = [
  "CREATE TABLE IF NOT EXISTS families (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL, stripe_test TEXT, stripe_live TEXT, checkout_id TEXT, sub_id TEXT, plan TEXT, plan_status TEXT, plan_checked INTEGER NOT NULL DEFAULT 0)",
  "CREATE TABLE IF NOT EXISTS free_ledger (h TEXT PRIMARY KEY, used INTEGER NOT NULL DEFAULT 0)",
  "CREATE TABLE IF NOT EXISTS codes (email TEXT PRIMARY KEY, salt TEXT NOT NULL, hash TEXT NOT NULL, expires INTEGER NOT NULL, tries INTEGER NOT NULL DEFAULT 0, sent_at INTEGER NOT NULL, sends INTEGER NOT NULL DEFAULT 0, window_start INTEGER NOT NULL)",
  "CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY, family_id TEXT NOT NULL, created_at INTEGER NOT NULL, seen_at INTEGER NOT NULL)",
  "CREATE TABLE IF NOT EXISTS talks (id TEXT PRIMARY KEY, family_id TEXT NOT NULL, started_at INTEGER NOT NULL, month TEXT NOT NULL, kind TEXT NOT NULL, requests INTEGER NOT NULL DEFAULT 1, client_key TEXT)",
  "CREATE TABLE IF NOT EXISTS spend (k TEXT PRIMARY KEY, micro INTEGER NOT NULL DEFAULT 0)",
  "CREATE TABLE IF NOT EXISTS counters (k TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0)",
  "CREATE TABLE IF NOT EXISTS usage (day TEXT NOT NULL, name TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, name))", // daily totals only
  "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
  "CREATE TABLE IF NOT EXISTS classes (id TEXT PRIMARY KEY, teacher_id TEXT NOT NULL, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL, assigned TEXT NOT NULL DEFAULT '[]', paid_until INTEGER, checkout_id TEXT)",
  "CREATE TABLE IF NOT EXISTS progress (family_id TEXT NOT NULL, sid TEXT NOT NULL, state TEXT NOT NULL, updated_at INTEGER NOT NULL, PRIMARY KEY (family_id, sid))",
  "CREATE TABLE IF NOT EXISTS nudges (h TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, email_id TEXT, send_at INTEGER, stopped INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL)",
  "CREATE TABLE IF NOT EXISTS class_members (id TEXT PRIMARY KEY, class_id TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE, name TEXT NOT NULL, joined_at INTEGER NOT NULL, seen_at INTEGER NOT NULL, progress TEXT)",
];
const SCHEMA_ADDED = [ // columns an earlier version's tables don't have yet (each fails harmlessly if it's there)
  "ALTER TABLE families ADD COLUMN stripe_test TEXT",
  "ALTER TABLE families ADD COLUMN stripe_live TEXT",
  "ALTER TABLE families ADD COLUMN checkout_id TEXT",
  "ALTER TABLE talks ADD COLUMN client_key TEXT",
  "ALTER TABLE families ADD COLUMN sync_on INTEGER",
  "ALTER TABLE families ADD COLUMN sync_gone TEXT",
  "ALTER TABLE classes ADD COLUMN paid_until INTEGER",
  "ALTER TABLE classes ADD COLUMN checkout_id TEXT",
];
const SCHEMA_INDEXES = [
  "CREATE INDEX IF NOT EXISTS talks_by_family ON talks (family_id, started_at)",
  "CREATE UNIQUE INDEX IF NOT EXISTS talks_by_key ON talks (family_id, client_key)",
  "CREATE INDEX IF NOT EXISTS talks_by_time ON talks (started_at)",
  "CREATE INDEX IF NOT EXISTS sessions_by_family ON sessions (family_id)",
  "CREATE INDEX IF NOT EXISTS sessions_by_time ON sessions (seen_at)",
  "CREATE INDEX IF NOT EXISTS codes_by_time ON codes (expires)",
  "CREATE INDEX IF NOT EXISTS classes_by_teacher ON classes (teacher_id)",
  "CREATE INDEX IF NOT EXISTS members_by_class ON class_members (class_id)",
];
const schemaDone = new WeakSet();
async function ensureSchema(env) {
  if (schemaDone.has(env.DB)) return;
  let version = 0;
  try { const r = await env.DB.prepare("SELECT value FROM settings WHERE key = 'schema'").first(); version = r ? Number(JSON.parse(r.value)) || 0 : 0; } catch (e) {}
  if (version < SCHEMA_VERSION) {
    await env.DB.batch(SCHEMA_TABLES.map(q => env.DB.prepare(q)));
    for (const q of SCHEMA_ADDED) { try { await env.DB.prepare(q).run(); } catch (e) { /* already there */ } }
    await upgradeEarlierVersion(env);
    await env.DB.batch(SCHEMA_INDEXES.map(q => env.DB.prepare(q)));
    await setSetting(env, "schema", SCHEMA_VERSION);
  }
  schemaDone.add(env.DB);
}
// A database made by the first test version kept the Stripe customer as "test:cus_…" or "live:cus_…" in one
// column and the free talks used in the families table. Both are moved to where this version keeps them.
async function upgradeEarlierVersion(env) {
  const cols = ((await env.DB.prepare("PRAGMA table_info(families)").all()).results || []).map(c => c.name);
  if (cols.includes("stripe_customer")) {
    await env.DB.batch([
      env.DB.prepare("UPDATE families SET stripe_test = substr(stripe_customer, 6), plan_checked = 0 WHERE stripe_customer LIKE 'test:%' AND stripe_test IS NULL"),
      env.DB.prepare("UPDATE families SET stripe_live = substr(stripe_customer, 6), plan_checked = 0 WHERE stripe_customer LIKE 'live:%' AND stripe_live IS NULL"),
    ]);
  }
  if (cols.includes("free_used")) {
    const rows = (await env.DB.prepare("SELECT email, free_used FROM families WHERE free_used > 0").all()).results || [];
    for (const row of rows) {
      await env.DB.prepare("INSERT INTO free_ledger (h, used) VALUES (?, ?) ON CONFLICT(h) DO UPDATE SET used = MAX(used, excluded.used)").bind(await freeKey(row.email), Number(row.free_used)).run();
    }
  }
}
async function getSetting(env, key) {
  const r = await env.DB.prepare("SELECT value FROM settings WHERE key = ?").bind(key).first();
  try { return r ? JSON.parse(r.value) : null; } catch (e) { return null; }
}
const setSetting = (env, key, value) => env.DB.prepare("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value").bind(key, JSON.stringify(value)).run();
async function prune(env) {
  const now = Date.now(), weekAgo = dayKey(now - 8 * 864e5);
  await env.DB.batch([
    env.DB.prepare("DELETE FROM codes WHERE expires < ?").bind(now - 864e5),
    env.DB.prepare("DELETE FROM sessions WHERE seen_at < ?").bind(now - SESSION_DAYS * 864e5),
    env.DB.prepare("DELETE FROM talks WHERE started_at < ?").bind(now - 100 * 864e5),
    env.DB.prepare("DELETE FROM class_members WHERE seen_at < ?").bind(now - SESSION_DAYS * 864e5),
    env.DB.prepare("DELETE FROM progress WHERE updated_at < ?").bind(now - SESSION_DAYS * 864e5), // a learner not seen on any device for over a year
    env.DB.prepare("DELETE FROM spend WHERE k < ?").bind(weekAgo),
    env.DB.prepare("DELETE FROM counters WHERE k < ?").bind(dayKey(now - 2 * 864e5)), // daily counts, kept two days
    env.DB.prepare("DELETE FROM usage WHERE day < ?").bind(dayKey(now - 400 * 864e5)), // usage totals, kept about a year
    env.DB.prepare("DELETE FROM nudges WHERE COALESCE(send_at, created_at) < ?").bind(now - 60 * 864e5), // reminder emails: the address goes 60 days after the last one
  ]);
}

// ---------- small helpers ----------
const enc = new TextEncoder();
async function sha256(s) {
  const b = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
}
function randomBytes(n) { const a = new Uint8Array(n); crypto.getRandomValues(a); return a; }
const randomId = () => [...randomBytes(12)].map(x => x.toString(16).padStart(2, "0")).join("");
const randomToken = () => btoa(String.fromCharCode(...randomBytes(32))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
function sixDigits() { const a = new Uint32Array(1); crypto.getRandomValues(a); return String(a[0] % 1000000).padStart(6, "0"); }
const latinDigits = s => s.replace(/[۰-۹]/g, d => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d))).replace(/[٠-٩]/g, d => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
function cleanEmail(v) {
  const e = String(v == null ? "" : v).trim().toLowerCase();
  return e.length <= 254 && !e.includes("..") && /^[a-z0-9._%+'-]{1,64}@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,24}$/.test(e) ? e : "";
}
function maskEmail(e) { const [u, d] = e.split("@"); return (u.length <= 2 ? u.slice(0, 1) : u.slice(0, 2)) + "•••@" + d; }
// Reads a body, but never more than maxBytes of it: a larger one is dropped part-way, so a huge upload can't fill memory.
async function readBounded(request, maxBytes) {
  const len = Number(request.headers.get("content-length"));
  if (Number.isFinite(len) && len > maxBytes) return null;
  if (!request.body) return new Uint8Array(0);
  const reader = request.body.getReader(), parts = [];
  let total = 0;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maxBytes) { try { await reader.cancel(); } catch (e) {} return null; }
      parts.push(value);
    }
  } catch (e) { return null; }
  const out = new Uint8Array(total);
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.byteLength; }
  return out;
}
async function readJson(request, max) {
  const bytes = await readBounded(request, max * 3);
  if (!bytes || !bytes.length) return null;
  let text = "";
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); } catch (e) { return null; }
  if (!text || text.length > max) return null;
  try { const j = JSON.parse(text); return j && typeof j === "object" && !Array.isArray(j) ? j : null; } catch (e) { return null; }
}
const cookieName = url => (url.protocol === "https:" ? "__Host-alefba" : "alefba");
const sessionCookie = (url, token) => `${cookieName(url)}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${SESSION_DAYS * 86400}${url.protocol === "https:" ? "; Secure" : ""}`;
const clearCookie = url => `${cookieName(url)}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0${url.protocol === "https:" ? "; Secure" : ""}`;
// Only the cookie this site sets is read (on https, the __Host- one, which no other site or page can plant).
function readCookie(request, url) {
  const name = cookieName(url).replace(/[-]/g, "\\-");
  const m = new RegExp(`(?:^|;\\s*)${name}=([A-Za-z0-9_-]{20,100})(?:;|$)`).exec(request.headers.get("cookie") || "");
  return m ? m[1] : "";
}

// A simple per-connection limit (kept in memory, so it's a speed bump, not a wall).
// The daily limits in the database and the monthly spending limit in the Claude Console are the real caps on cost.
const seen = new Map();
let lastSweep = 0;
function tooMany(request, bucket, perMinute = LIMITS.perMinute, perHour = LIMITS.perHour) {
  const who = bucket + ":" + (request.headers.get("CF-Connecting-IP") || "unknown");
  const now = Date.now();
  if (now - lastSweep > 60e3) { // addresses not seen for an hour are forgotten
    lastSweep = now;
    for (const [k, list] of seen) if (!list.length || now - list[list.length - 1] >= 3600e3) seen.delete(k);
  }
  const list = (seen.get(who) || []).filter(t => now - t < 3600e3);
  const lastMinute = list.filter(t => now - t < 60e3).length;
  if (lastMinute >= perMinute || list.length >= perHour) { seen.set(who, list); return true; }
  list.push(now); seen.set(who, list);
  if (seen.size > 5000) for (const k of seen.keys()) { seen.delete(k); if (seen.size < 4000) break; }
  return false;
}

function reply(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" } });
}
