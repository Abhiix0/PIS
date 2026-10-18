// Screenshots every screen in mock mode. Needs: VITE_MOCK_API=1 VITE_AUTH_ISSUER=http://mock.idp VITE_AUTH_CLIENT_ID=mock npm run dev
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const url = process.env.URL ?? "http://localhost:1420/";
const out = "../../docs/design/screens";
mkdirSync(out, { recursive: true });
const errors = [];
const browser = await chromium.launch();
const shot = async (path, query, hash, nav, name) => {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on("console", (m) => m.type() === "error" && errors.push(`${name}: ${m.text()}`));
  page.on("pageerror", (e) => errors.push(`${name}: ${e.message}`));
  await page.goto(url + query + hash);
  if (nav) await page.getByRole("link", { name: nav, exact: true }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
  await page.close();
};
const S = [
  ["overview", "", "", "Overview"],
  ["assessment", "", "", "Assessment"],
  ["plan", "", "", "Development plan"],
  ["history", "", "", "History"],
  ["integrations", "", "", "Integrations"],
  ["profile", "", "", "Profile"],
  ["settings", "", "", "Settings"],
  ["sign-in", "", "#signed-out"],
  ["overview-empty", "?mock=empty", "", "Overview"],
  ["overview-error", "?mock=error", "", "Overview"],
];
for (const [name, q, h, nav] of S) await shot(url, q, h, nav, name);
await browser.close();
console.log(errors.length ? `console errors:\n${errors.join("\n")}` : "no console errors");
process.exit(errors.length ? 1 : 0);
