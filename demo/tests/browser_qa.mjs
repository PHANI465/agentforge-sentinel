// DEMO01 browser QA in a real headless Chromium, using an existing Playwright install
// (no download, no package change). It serves demo/ from its own loopback-only Node server,
// which it closes by its own handle, and fails on any request outside that origin/allowlist.
//
//   node demo/tests/browser_qa.mjs --node-modules <dir containing playwright/> [--out <dir>]
//
// Screenshots and the JSON report go to --out (default: .agent/demo01/qa, git-ignored).
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const DEMO = resolve(HERE, "..");
const ROOT = resolve(DEMO, "..");
const ALLOWED = new Set(["/", "/index.html", "/replay.css", "/replay.js",
  "/data/recorded-case.json", "/data/manifest.json"]);
const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8" };

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const nodeModules = arg("--node-modules", process.env.DEMO_PLAYWRIGHT_NODE_MODULES);
if (!nodeModules || !existsSync(join(nodeModules, "playwright"))) {
  console.error("GAP: no existing Playwright install given (--node-modules <dir>)");
  process.exit(3);
}
const require = createRequire(import.meta.url);
const { chromium } = require(join(resolve(nodeModules), "playwright"));
const OUT = resolve(arg("--out", join(ROOT, ".agent", "demo01", "qa")));
mkdirSync(OUT, { recursive: true });

const fixture = JSON.parse(readFileSync(join(DEMO, "data", "recorded-case.json"), "utf-8"));
const served = [];

function serve() {
  const server = createServer((req, res) => {
    const path = new URL(req.url, "http://127.0.0.1").pathname;
    served.push(req.method + " " + path);
    const file = normalize(join(DEMO, path === "/" ? "index.html" : path));
    if (!ALLOWED.has(path) || req.method !== "GET" || !file.startsWith(DEMO + sep)) {
      res.writeHead(404).end();
      return;
    }
    const ext = file.slice(file.lastIndexOf("."));
    res.writeHead(200, { "content-type": TYPES[ext] || "application/octet-stream",
      "cache-control": "no-store" });
    res.end(readFileSync(file));
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok(server)));
}

const results = [];
function record(name, ok, detail) {
  results.push({ name, ok: Boolean(ok), detail: detail === undefined ? null : detail });
  console.log((ok ? "PASS " : "FAIL ") + name + (detail !== undefined && !ok ?
    " :: " + JSON.stringify(detail) : ""));
}

async function watched(context, origin) {
  const page = await context.newPage();
  const foreign = [];
  const errors = [];
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (u.protocol === "data:") return;
    if (u.origin !== origin || !ALLOWED.has(u.pathname) || r.method() !== "GET") {
      foreign.push(r.method() + " " + r.url());
    }
  });
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  return { page, foreign, errors };
}

async function ready(page) {
  await page.waitForFunction(() => /^Frame \d+ of \d+$/.test(
    document.getElementById("frame-no").textContent));
}

async function ledger(page) {
  return page.$$eval("#ledger .kv-row", (rows) => Object.fromEntries(rows.map((r) =>
    [r.querySelector("dt").textContent, r.querySelector("dd .mono").textContent])));
}

async function noHorizontalScroll(page) {
  return page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
}

async function main() {
  const server = await serve();
  const origin = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ headless: true });
  try {
    // ---- desktop: load, labels, hash, navigation, ledger counts --------------------------
    const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const d = await watched(desk, origin);
    await d.page.goto(origin + "/");
    await ready(d.page);
    record("loads frame 1", (await d.page.textContent("#frame-no")) === "Frame 1 of 10");
    const labels = await d.page.$$eval(".labels .label", (n) => n.map((x) => x.textContent));
    record("six persistent labels", labels.join("|") === ["Recorded", "Synthetic",
      "Rule baseline", "Deterministic roles", "Scripted approval", "Simulated action"].join("|"),
    labels);
    await d.page.waitForFunction(() => /matches the manifest|DOES NOT/.test(
      document.getElementById("provenance").textContent));
    const prov = await d.page.textContent("#provenance");
    record("data hash computed and matches manifest", prov.includes("matches the manifest") &&
      !prov.includes("DOES NOT"));
    record("integrity banner hidden for published data",
      await d.page.$eval("#integrity", (n) => n.hidden));
    await d.page.screenshot({ path: join(OUT, "desktop-frame01.png"), fullPage: true });

    const titles = [];
    const ledgers = [];
    for (let i = 0; i < fixture.frames.length; i += 1) {
      titles.push(await d.page.textContent("#frame-title"));
      ledgers.push(await ledger(d.page));
      if (i < fixture.frames.length - 1) await d.page.click("#next");
      if (i === 0) {
        record("Next keeps keyboard focus on the button",
          await d.page.evaluate(() => document.activeElement.id === "next"));
      }
    }
    record("Next walks every frame in recorded order",
      titles.join("|") === fixture.frames.map((f) => f.title).join("|"), titles);
    record("Next disabled on the last frame", await d.page.$eval("#next", (b) => b.disabled));
    const before = ledgers.slice(0, 6);
    record("frames 1-6 show zero approvals and zero simulated actions",
      before.every((l) => l.Approvals === "0" && l["Simulated actions"] === "0"), before);
    record("frame 7 (approval) shows one approval and zero actions",
      ledgers[6].Approvals === "1" && ledgers[6]["Simulated actions"] === "0", ledgers[6]);
    record("frames 8-10 show exactly one simulated action",
      ledgers.slice(7).every((l) => l["Simulated actions"] === "1"), ledgers.slice(7));
    await d.page.screenshot({ path: join(OUT, "desktop-frame10.png"), fullPage: true });

    await d.page.keyboard.press("Home");
    record("Home key goes to frame 1", (await d.page.textContent("#frame-no")) === "Frame 1 of 10");
    await d.page.keyboard.press("ArrowRight");
    await d.page.keyboard.press("ArrowRight");
    record("ArrowRight advances", (await d.page.textContent("#frame-no")) === "Frame 3 of 10");
    await d.page.keyboard.press("ArrowLeft");
    record("ArrowLeft goes back", (await d.page.textContent("#frame-no")) === "Frame 2 of 10");
    await d.page.keyboard.press("End");
    record("End key goes to the last frame",
      (await d.page.textContent("#frame-no")) === "Frame 10 of 10");
    await d.page.click(".rail-btn[data-index='6']");
    record("rail button opens frame 7 and marks it current",
      (await d.page.textContent("#frame-no")) === "Frame 7 of 10" &&
      (await d.page.getAttribute(".rail-btn[data-index='6']", "aria-current")) === "step");
    // Frame titles in the rail name recorded steps ("... executed"); every control must be
    // frame navigation, and nothing in the frame itself may be a button, input or form.
    const controls = await d.page.evaluate(() => ({
      other: [...document.querySelectorAll("button")].filter((b) =>
        !b.classList.contains("rail-btn") && b.id !== "prev" && b.id !== "next")
        .map((b) => b.textContent),
      inFrame: document.querySelectorAll("#frame button, #frame input, form, input").length,
    }));
    record("no Approve/Execute control: only frame navigation buttons exist",
      controls.other.length === 0 && controls.inFrame === 0, controls);
    await d.page.screenshot({ path: join(OUT, "desktop-frame07-approval.png"), fullPage: true });

    // ---- every in-page link targets an existing record ---------------------------------
    const hrefs = new Set();
    for (let i = 0; i < fixture.frames.length; i += 1) {
      await d.page.click(".rail-btn[data-index='" + i + "']");
      (await d.page.$$eval("a[href]", (as) => as.map((a) => a.getAttribute("href"))))
        .forEach((x) => hrefs.add(x));
    }
    const external = [...hrefs].filter((x) => !/^#rec-[0-9a-f-]{36}$/.test(x) &&
      x !== "#frame-title");
    record("links are only in-page record fragments", external.length === 0, external);
    const broken = [];
    for (const href of hrefs) {
      if (!href.startsWith("#rec-")) continue;
      for (let i = 0; i < fixture.frames.length; i += 1) {
        await d.page.click(".rail-btn[data-index='" + i + "']");
        const link = await d.page.$("a[href='" + href + "']");
        if (!link) continue;
        await link.click();
        const ok = await d.page.evaluate((h) => {
          const el = document.getElementById(h.slice(1));
          return Boolean(el) && document.activeElement === el;
        }, href);
        if (!ok) broken.push(href);
        break;
      }
    }
    record("every record link opens and focuses its record (" + hrefs.size + " links)",
      broken.length === 0, broken);
    await d.page.click(".rail-btn[data-index='2']");
    const firstCite = await d.page.$(".claims a.reclink");
    await firstCite.click();
    record("a claim citation jumps to the cited evidence frame",
      (await d.page.textContent("#frame-no")) === "Frame 2 of 10");

    // ---- keyboard focus order and visibility ---------------------------------------------
    // A fresh page: a hash-only goto is a same-document navigation that keeps old focus.
    const f = await watched(desk, origin);
    await f.page.goto(origin + "/#frame-1");
    await ready(f.page);
    await f.page.keyboard.press("Tab");
    const skip = await f.page.evaluate(() => document.activeElement.className);
    await f.page.keyboard.press("Tab");
    const rail = await f.page.evaluate(() => document.activeElement.className);
    const ring = await f.page.evaluate(() => getComputedStyle(document.activeElement)
      .outlineStyle);
    d.errors.push(...f.errors);
    d.foreign.push(...f.foreign);
    record("Tab reaches skip link then the frame rail with a visible focus ring",
      skip === "skip" && rail.includes("rail-btn") && ring !== "none", { skip, rail, ring });
    record("no console errors (desktop)", d.errors.length === 0, d.errors);
    record("no request outside the demo allowlist (desktop)", d.foreign.length === 0, d.foreign);
    await desk.close();

    // ---- narrow and dark layouts -------------------------------------------------------
    const narrow = await browser.newContext({ viewport: { width: 375, height: 812 },
      deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const n = await watched(narrow, origin);
    await n.page.goto(origin + "/");
    await ready(n.page);
    const overflow = [];
    for (let i = 0; i < fixture.frames.length; i += 1) {
      await n.page.evaluate((k) => { location.hash = "#frame-" + k; }, i + 1);
      await n.page.waitForFunction((k) => document.getElementById("frame-no").textContent ===
        "Frame " + k + " of 10", i + 1);
      if (!(await noHorizontalScroll(n.page))) overflow.push(i + 1);
      if ([0, 2, 5, 6, 9].includes(i)) {
        await n.page.screenshot({ path: join(OUT, "narrow-frame" + String(i + 1)
          .padStart(2, "0") + ".png"), fullPage: true });
      }
    }
    record("narrow 375px: no horizontal page scroll on any frame", overflow.length === 0,
      overflow);
    record("no console errors (narrow)", n.errors.length === 0, n.errors);
    record("no request outside the demo allowlist (narrow)", n.foreign.length === 0, n.foreign);
    await narrow.close();

    const dark = await browser.newContext({ viewport: { width: 1280, height: 900 },
      colorScheme: "dark" });
    const k = await watched(dark, origin);
    await k.page.goto(origin + "/#frame-5");
    await ready(k.page);
    const bg = await k.page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    record("dark color scheme applies", bg !== "rgb(245, 242, 234)", bg);
    await k.page.screenshot({ path: join(OUT, "dark-frame05.png"), fullPage: true });
    await dark.close();

    // ---- hostile literal text stays text ------------------------------------------------
    const hostile = JSON.parse(JSON.stringify(fixture));
    const H1 = "<img src=x onerror=\"window.__pwned=1\">";
    const H2 = "<script>window.__pwned=2</script><b>bold</b>";
    const H3 = "[click](javascript:window.__pwned=3) javascript:alert(1)";
    hostile.records.ingests[0].transaction.external_id = H1;
    hostile.scenario.description = H3;
    const inv = hostile.records.attempts.find((a) => a.role === "investigator");
    inv.finding.rationale = H2;
    inv.output.claims[0].value = H1;
    hostile.records.tool_results[0].values[H2] = H1;
    const evil = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const e = await watched(evil, origin);
    await e.page.route("**/data/recorded-case.json", (route) => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify(hostile) }));
    await e.page.goto(origin + "/");
    await ready(e.page);
    const seen = [];
    for (let i = 0; i < hostile.frames.length; i += 1) {
      await e.page.click(".rail-btn[data-index='" + i + "']");
      seen.push(await e.page.evaluate(() => document.getElementById("frame").textContent));
    }
    const all = seen.join("\n") + (await e.page.textContent("#provenance"));
    const state = await e.page.evaluate(() => ({
      pwned: window.__pwned === undefined ? null : window.__pwned,
      imgs: document.querySelectorAll("img").length,
      scripts: [...document.scripts].map((s) => s.getAttribute("src")),
      bold: document.querySelectorAll("b").length,
      js: [...document.querySelectorAll("a[href]")].filter((a) => /^javascript:/i.test(
        a.getAttribute("href"))).length,
    }));
    record("hostile strings render as literal text and never execute",
      state.pwned === null && state.imgs === 0 && state.bold === 0 && state.js === 0 &&
      state.scripts.join() === "replay.js" && all.includes(H1) && all.includes(H2) &&
      all.includes(H3), state);
    record("altered data is flagged against the manifest hash",
      await e.page.$eval("#integrity", (x) => !x.hidden && /does not match/.test(x.textContent)));
    await e.page.screenshot({ path: join(OUT, "hostile-frame05.png"), fullPage: true });
    record("no request outside the demo allowlist (hostile)", e.foreign.length === 0, e.foreign);
    await evil.close();
  } finally {
    await browser.close();
    await new Promise((ok) => server.close(ok));
  }
  const bad = served.filter((s) => !ALLOWED.has(s.split(" ")[1]) || !s.startsWith("GET "));
  record("static server saw only allowlisted GETs", bad.length === 0, bad);
  const failed = results.filter((r) => !r.ok);
  writeFileSync(join(OUT, "qa-report.json"), JSON.stringify({
    passed: results.length - failed.length, failed: failed.length, results,
    requests_served: served.length, browser: "chromium (existing Playwright install)" },
  null, 1) + "\n");
  console.log((failed.length ? "FAILED " : "ALL PASSED ") + (results.length - failed.length) +
    "/" + results.length + "; server closed; screenshots and report in the --out directory");
  process.exitCode = failed.length ? 1 : 0;
}

main().catch((error) => {
  console.error("QA crashed: " + (error && error.message ? error.message : String(error)));
  process.exitCode = 2;
});
