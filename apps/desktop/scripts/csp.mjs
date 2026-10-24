// Builds the Tauri config override that sets the webview CSP for one API and one IdP. The base
// tauri.conf.json allows only localhost; no arbitrary https: origin is ever allowed.
// Usage (apps/desktop): node scripts/csp.mjs && npx tauri build|dev --config src-tauri/tauri.csp.conf.json
// Env: VITE_API_BASE_URL, VITE_AUTH_ISSUER, optional CSP_EXTRA_ORIGINS (comma list, e.g. an IdP token host).
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const LOCAL = new Set(["localhost", "127.0.0.1"]);

export function origin(value, name) {
  let u;
  try {
    u = new URL(value);
  } catch {
    throw new Error(`${name} is not a valid URL`);
  }
  const ok = u.protocol === "https:" || (u.protocol === "http:" && LOCAL.has(u.hostname));
  if (!ok) throw new Error(`${name} must be https (http only for localhost)`);
  return u.origin;
}

export function buildCsp(env) {
  const origins = [
    origin(env.VITE_API_BASE_URL ?? "", "VITE_API_BASE_URL"),
    origin(env.VITE_AUTH_ISSUER ?? "", "VITE_AUTH_ISSUER"),
    ...(env.CSP_EXTRA_ORIGINS ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => origin(s, "CSP_EXTRA_ORIGINS")),
  ];
  const connect = ["'self'", "ipc:", "http://ipc.localhost", ...new Set(origins)].join(" ");
  return `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src ${connect}; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'none'`;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const out = "src-tauri/tauri.csp.conf.json";
  writeFileSync(out, JSON.stringify({ app: { security: { csp: buildCsp(process.env) } } }, null, 2));
  console.log(`wrote ${out}`);
}
