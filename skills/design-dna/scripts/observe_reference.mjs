#!/usr/bin/env node
/**
 * observe_reference.mjs
 *
 * Watch one public reference site the way a person does, and emit an evidence
 * record of what was actually observed.
 *
 * This exists because prose does not bind a producer. Told to "watch the site
 * scroll", a producer will teleport the scroll position, screenshot the resting
 * state, and call that watching. A sequence of stills cannot show motion, so
 * the extracted takeaway becomes whatever survives a photograph: a background
 * color, a wordmark placement, a layout offset. The observation this script
 * emits is machine-checkable, so a dossier row can no longer claim motion that
 * nobody watched.
 *
 * What it does per site:
 *   - scrolls in small steps and, at each step, screenshots on arrival and
 *     again after a settle delay; a difference between the two is a reveal or
 *     scroll-linked animation firing
 *   - screenshots twice at rest with no input; a difference is autoplaying
 *     motion (video, canvas, marquee, looping animation)
 *   - hovers real interactive elements and screenshots before and after
 *     each one
 *   - clicks an in-page link and screenshots the transition and the settled
 *     destination
 *
 * "Did anything change" is decided by comparing SHA-256 of the encoded frames.
 * Identical rendering encodes to identical bytes, so an unchanged hash is a
 * reliable negative and a changed hash is a reliable positive. No image
 * library is required.
 *
 * Usage:
 *   node observe_reference.mjs --url https://example.test/ --id strong-1 \
 *        --out .design-dna/references [--browser-executable FILE]
 *
 * Playwright resolution matches rendered_review.mjs: normal Node resolution or
 * DESIGN_DNA_PLAYWRIGHT_MODULE_DIR pointing at a node_modules directory.
 */
import { createHash } from "node:crypto";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";

const SCHEMA_VERSION = 1;
const REST_SETTLE_MS = 700;
const HOLD_MS = 900;
const SCROLL_STEP_RATIO = 0.62;
const MAX_STEPS = 14;
const MAX_HOVERS = 4;

function fail(code, message) {
  process.stdout.write(JSON.stringify({ ok: false, error: { code, message } }, null, 2) + "\n");
  process.exit(2);
}

function parseArgs(argv) {
  const out = { url: null, id: null, outDir: null, browserExecutable: null, label: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--url") out.url = argv[++i];
    else if (a === "--id") out.id = argv[++i];
    else if (a === "--out") out.outDir = argv[++i];
    else if (a === "--label") out.label = argv[++i];
    else if (a === "--browser-executable") out.browserExecutable = argv[++i];
    else if (a === "--help" || a === "-h") {
      process.stdout.write(
        "observe_reference.mjs --url URL --id ID --out DIR [--label TEXT] [--browser-executable FILE]\n"
      );
      process.exit(0);
    } else fail("unknown-argument", `Unrecognized argument: ${a}`);
  }
  if (!out.url || !/^https?:\/\//i.test(out.url)) fail("invalid-url", "--url must be an http(s) URL.");
  if (!out.id || !/^[a-z][a-z0-9-]{0,47}$/.test(out.id)) fail("invalid-id", "--id must be a short lowercase slug, e.g. strong-1.");
  if (!out.outDir) fail("invalid-out", "--out must name a directory.");
  return out;
}

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const moduleDir = process.env.DESIGN_DNA_PLAYWRIGHT_MODULE_DIR;
  const attempt = (name) => {
    if (moduleDir) {
      try {
        return require(path.join(moduleDir, name));
      } catch (e) { /* fall through */ }
    }
    return require(name);
  };
  for (const name of ["playwright", "playwright-core"]) {
    try {
      const pw = attempt(name);
      if (pw?.chromium) return pw;
    } catch (e) { /* try the next */ }
  }
  fail(
    "playwright-unavailable",
    "Playwright could not be loaded. Install it, or set DESIGN_DNA_PLAYWRIGHT_MODULE_DIR to its node_modules directory."
  );
  return null;
}

const sha = (buf) => createHash("sha256").update(buf).digest("hex");

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const pw = loadPlaywright();
  fs.mkdirSync(args.outDir, { recursive: true });
  const frameDir = path.join(args.outDir, `${args.id}-frames`);
  fs.mkdirSync(frameDir, { recursive: true });

  const frames = [];
  const interactions = [];
  const notes = [];
  let n = 0;

  const browser = await pw.chromium.launch(
    args.browserExecutable ? { executablePath: args.browserExecutable } : {}
  );
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  async function shot(kind, note) {
    n += 1;
    const file = `${args.id}-${String(n).padStart(3, "0")}-${kind}.png`;
    const buf = await page.screenshot({ path: path.join(frameDir, file) });
    const rec = { seq: n, kind, file, sha256: sha(buf), note: note || null };
    frames.push(rec);
    return rec;
  }

  try {
    await page.goto(args.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(3000);

    // Consent walls hide the page. Decline non-essential where the wording
    // allows it, otherwise accept only to reach the design underneath.
    for (const word of ["reject", "decline", "only necessary", "essential", "accept", "agree", "got it", "allow all"]) {
      try {
        const b = page.locator(`button:has-text("${word}"), a:has-text("${word}")`).first();
        if (await b.isVisible({ timeout: 250 })) {
          await b.click({ timeout: 1200 });
          notes.push(`consent control clicked: ${word}`);
          await page.waitForTimeout(600);
          break;
        }
      } catch (e) { /* none present */ }
    }

    // --- at rest: does anything move with no input at all?
    const rest0 = await shot("rest", "at rest, first frame");
    await page.waitForTimeout(REST_SETTLE_MS);
    const rest1 = await shot("rest", "at rest, after settle delay, no input");
    const restMoved = rest0.sha256 !== rest1.sha256;
    interactions.push({
      type: "rest",
      moved: restMoved,
      frames: [rest0.seq, rest1.seq],
      detail: restMoved
        ? "The page changed with no input, so something autoplays or loops."
        : "The page was still with no input.",
    });

    // --- scrolling: step down, screenshot on arrival and again after settling
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    const view = 900;
    const step = Math.max(240, Math.round(view * SCROLL_STEP_RATIO));
    const steps = Math.max(2, Math.min(MAX_STEPS, Math.floor((height - view) / step)));
    let scrollMoved = 0;
    for (let i = 1; i <= steps; i += 1) {
      const y = Math.min(height - view, i * step);
      // a real wheel gesture, not a teleport, so scroll-linked work runs
      await page.mouse.move(720, 450);
      await page.mouse.wheel(0, step);
      await page.waitForTimeout(90);
      await page.evaluate((yy) => window.scrollTo(0, yy), y);
      const a = await shot("scroll-arrive", `arrived at y=${y}`);
      await page.waitForTimeout(HOLD_MS);
      const b = await shot("scroll-settle", `held at y=${y} for ${HOLD_MS}ms`);
      const moved = a.sha256 !== b.sha256;
      if (moved) scrollMoved += 1;
      interactions.push({
        type: "scroll-hold",
        scroll_y: y,
        moved,
        frames: [a.seq, b.seq],
        detail: moved
          ? "Content changed while the page sat still at this offset, so something animated into place here."
          : "Nothing changed while the page sat still at this offset.",
      });
    }

    // --- hover: real pointer over real interactive elements
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(600);
    let hoverMoved = 0;
    let hoverTried = 0;
    const targets = await page.$$("a, button, [role=button], li, article, figure, img");
    for (const el of targets) {
      if (hoverTried >= MAX_HOVERS) break;
      let box = null;
      try { box = await el.boundingBox(); } catch (e) { box = null; }
      if (!box || box.width < 60 || box.height < 24 || box.y < 0 || box.y > 820) continue;
      hoverTried += 1;
      await page.mouse.move(4, 4);
      await page.waitForTimeout(200);
      const before = await shot("hover-before", "pointer away");
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(650);
      const after = await shot("hover-after", "pointer over an interactive element");
      const moved = before.sha256 !== after.sha256;
      if (moved) hoverMoved += 1;
      interactions.push({
        type: "hover",
        moved,
        frames: [before.seq, after.seq],
        detail: moved ? "The page responded to the pointer." : "Nothing responded to the pointer here.",
      });
    }

    // --- click through one in-page link and watch the transition
    let transition = { type: "transition", attempted: false, moved: false, frames: [], detail: "No same-origin link was available to follow." };
    try {
      const origin = new URL(args.url).origin;
      const href = await page.evaluate((o) => {
        const a = Array.from(document.querySelectorAll("a[href]")).find((x) => {
          try {
            const u = new URL(x.href, location.href);
            return u.origin === o && u.pathname !== location.pathname && !x.href.includes("#");
          } catch (e) { return false; }
        });
        return a ? a.href : null;
      }, origin);
      if (href) {
        await page.mouse.move(4, 4);
        const before = await shot("transition-before", "before following a link");
        await page.goto(href, { waitUntil: "domcontentloaded", timeout: 45000 });
        await page.waitForTimeout(260);
        const during = await shot("transition-during", "shortly after navigation started");
        await page.waitForTimeout(2200);
        const settled = await shot("transition-settled", "destination settled");
        transition = {
          type: "transition",
          attempted: true,
          url: href,
          moved: during.sha256 !== settled.sha256,
          frames: [before.seq, during.seq, settled.seq],
          detail:
            during.sha256 !== settled.sha256
              ? "The destination was still resolving after navigation, so the arrival is animated or staged."
              : "The destination appeared in its settled state immediately.",
        };
      }
    } catch (e) {
      transition.detail = `Following a link failed: ${String(e).slice(0, 160)}`;
    }
    interactions.push(transition);

    const motionObserved =
      restMoved || scrollMoved > 0 || hoverMoved > 0 || transition.moved === true;

    const record = {
      schema_version: SCHEMA_VERSION,
      tool: "observe_reference.mjs",
      id: args.id,
      label: args.label || null,
      url: args.url,
      observed_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      viewport: { width: 1440, height: 900 },
      frame_dir: path.basename(frameDir),
      frames,
      interactions,
      coverage: {
        rest: true,
        scroll_holds: steps,
        hovers: hoverTried,
        transition: transition.attempted,
      },
      motion: {
        observed: motionObserved,
        at_rest: restMoved,
        on_scroll_holds: scrollMoved,
        on_hover: hoverMoved,
        on_transition: transition.moved === true,
      },
      notes,
    };
    const outFile = path.join(args.outDir, `${args.id}-observation.json`);
    fs.writeFileSync(outFile, JSON.stringify(record, null, 2) + "\n", "utf8");
    process.stdout.write(
      JSON.stringify(
        {
          ok: true,
          observation: outFile,
          frames: frames.length,
          motion_observed: motionObserved,
          scroll_holds_with_motion: scrollMoved,
          hovers_with_response: hoverMoved,
          transition_animated: transition.moved === true,
        },
        null,
        2
      ) + "\n"
    );
  } catch (error) {
    fail("observation-failed", String(error).slice(0, 400));
  } finally {
    await browser.close().catch(() => {});
  }
}

main();
