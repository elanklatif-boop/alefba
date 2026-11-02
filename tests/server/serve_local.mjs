// Runs the website's server code on this computer (with a stand-in database) so a real browser can try it.
// node tests/server/serve_local.mjs [port] — STATS_KEY is "local-test-key-123" here.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { D1 } from "./d1shim.mjs";
const SITE = process.env.SITE || new URL("../../alefba-site/", import.meta.url).pathname;
const worker = (await import(path.join(SITE, "_worker.js"))).default;
const db = new D1();
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".json": "application/json", ".css": "text/css", ".mp3": "audio/mpeg", ".png": "image/png", ".webmanifest": "application/manifest+json", ".woff2": "font/woff2" };
const ASSETS = { fetch: async r => {
  let p = decodeURIComponent(new URL(r.url).pathname); if (p.endsWith("/")) p += "index.html";
  const f = path.join(SITE, p);
  if (!f.startsWith(SITE) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) return new Response("not found", { status: 404 });
  return new Response(fs.readFileSync(f), { headers: { "content-type": types[path.extname(f)] || "application/octet-stream" } });
} };
const env = { DB: db, ASSETS, STATS_KEY: "local-test-key-123" };
const port = Number(process.argv[2] || 8830);
http.createServer(async (req, res) => {
  const chunks = []; for await (const c of req) chunks.push(c);
  const headers = new Headers(); for (const [k, v] of Object.entries(req.headers)) if (typeof v === "string") headers.set(k, v);
  headers.set("CF-Connecting-IP", req.socket.remoteAddress || "127.0.0.1");
  const r = await worker.fetch(new Request("http://" + req.headers.host + req.url, { method: req.method, headers, body: ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks) }), env, { waitUntil: p => p });
  res.writeHead(r.status, Object.fromEntries(r.headers)); res.end(Buffer.from(await r.arrayBuffer()));
}).listen(port, () => console.log("serving on " + port));
