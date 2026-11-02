// A stand-in for Cloudflare's D1 database, on Node's built-in SQLite, with the same calls the server uses.
import { DatabaseSync } from "node:sqlite";

class Stmt {
  constructor(db, sql, params = []) { this.db = db; this.sql = sql; this.params = params; }
  bind(...params) { return new Stmt(this.db, this.sql, params.map(v => (v === undefined ? null : v))); }
  _plain(r) { return r ? Object.fromEntries(Object.entries(r)) : r; }
  _exec() {
    const st = this.db.prepare(this.sql);
    if (/^\s*(select|with|pragma)\b/i.test(this.sql)) return { success: true, results: st.all(...this.params).map(r => this._plain(r)), meta: { changes: 0 } };
    const info = st.run(...this.params);
    return { success: true, results: [], meta: { changes: Number(info.changes), last_row_id: Number(info.lastInsertRowid) } };
  }
  async first(col) {
    const r = this.db.prepare(this.sql).get(...this.params);
    if (r === undefined) return null;
    const row = this._plain(r);
    return col ? row[col] : row;
  }
  async all() { return this._exec(); }
  async run() { return this._exec(); }
}

export class D1 {
  constructor(path = ":memory:") { this.db = new DatabaseSync(path); this.calls = 0; }
  prepare(sql) { this.calls++; return new Stmt(this.db, sql); }
  async batch(stmts) {
    this.db.exec("BEGIN");
    try { const out = stmts.map(s => s._exec()); this.db.exec("COMMIT"); return out; }
    catch (e) { this.db.exec("ROLLBACK"); throw e; }
  }
  async exec(sql) { this.db.exec(sql); return { count: 1 }; }
  // for tests: look inside directly
  q(sql, ...params) { return this.db.prepare(sql).all(...params).map(r => Object.fromEntries(Object.entries(r))); }
  x(sql, ...params) { return this.db.prepare(sql).run(...params); }
}
