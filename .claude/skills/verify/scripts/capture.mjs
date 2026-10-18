#!/usr/bin/env node
/**
 * The capture half of /verify: drive the running app the way a person does,
 * and write down what it showed. It measures; it judges only what a script
 * can decide (overflow, console errors, serious or critical accessibility
 * violations, whether the screen was reached at all). Whether a screen looks
 * like its design is the model's judgement, made by reading the screenshots
 * this writes. The skill is `.claude/skills/verify/SKILL.md`.
 *
 * Why a script captures and the model only judges: the product owner's
 * decision of 2026-09-01. Every capture the assistant interpreted by hand
 * needed correcting at least once, so no judgement is written without a file
 * behind it (`.claude/skills/bossman-mode/reference/Product_review.md`).
 *
 * Run it from `frontend/`, so it resolves the Playwright and
 * `@axe-core/playwright` installed there:
 *
 *   cd frontend
 *   node ../.claude/skills/verify/scripts/capture.mjs \
 *     --spec ../.claude/skills/verify/specs/home_and_answer.json --target develop
 *
 * An agent worktree has no `frontend/node_modules`. Run it from the main
 * checkout's `frontend/` with this script's worktree path; it still writes
 * into the checkout it lives in, since every output path is derived from the
 * script's own location, never from the working directory.
 *
 * Targets:
 *   develop  the deployed develop app, from `frontend/e2e/live-target.ts`
 *            (S3_LIVE_WEB_URL and S3_LIVE_API_URL override it, as there).
 *            The API's /health must report app_env "develop" or nothing is
 *            captured and the exit code is 2.
 *   local    the local stack on the ports `frontend/playwright.config.ts`
 *            fixes (Vite 5273, FastAPI 8931). /health must answer; its
 *            app_env is recorded, not required.
 *   --web and --api override either target with an https:// or loopback URL.
 *
 * Screens come from a JSON spec (--spec) or the command line
 * (--screen name=/path, repeatable, for a screen reached by its address
 * alone). A spec screen is:
 *
 *   { "name": "answer", "path": "/", "design": "<design file or 'missing'>",
 *     "steps": [ { "do": "disclaimer" }, { "do": "fill", ... }, ... ],
 *     "saveText": "main",
 *     "prototype": { "steps": [ ... ] } }
 *
 * Step actions: goto {path}, disclaimer, fill {selector, text},
 * click {selector}, press {key, selector?}, waitFor {selector, timeoutMs?,
 * state?}, wait {ms}. Selectors are Playwright selector strings.
 *
 * Widths: exactly 1280 and 390, by default 1280x900 and 390x844. A spec
 * whose widths are anything else is refused, because a failing screen could
 * otherwise pass by dropping the width it fails at. --allow-partial-widths
 * runs other widths for a diagnosis, and such a run says, on screen and in
 * results.json, that it cannot start the seven-day close.
 *
 * What it measures, per screen and per width, each width in a fresh browser
 * context so a phone-width page loads at phone width rather than being
 * resized after landing:
 *   - a full-page screenshot, and a first-screen one of what a person sees
 *     on landing. A sticky or fixed element, such as the app's footer band, is
 *     drawn where the first screen ends in the full-page shot, not at the
 *     bottom of the page: read it as pinned to the bottom of the screen.
 *   - horizontal overflow, documentElement scrollWidth minus clientWidth, and
 *     when it is above zero, up to five of the innermost elements whose right
 *     edge passes the screen's, as candidates for the cause
 *   - console errors and uncaught page errors
 *   - an axe scan with the WCAG 2.1 A and AA tags `e2e/accessibility.spec.ts`
 *     uses; serious and critical violations are listed and fail the check
 *   - the same screen in `docs/build/design/design-system/prototype/app.html`
 *     at the same width, when the spec says how to reach it there
 *
 * What it does not measure, stated so a gap is arguable: whether the screen
 * matches its design (the model reads the screenshot pair), keyboard traps,
 * screen-reader order, touch emulation (the phone width is a viewport, not a
 * mobile device profile), and contrast during an animation, since pages run
 * with reduced motion so axe reads the settled colours, as the accessibility
 * suite does.
 *
 * Writes, into testing/Developer/reports/<date>_verify_<topic>_<HHMMSS>Z/,
 * one new folder per run by the UTC time, unless --out names another folder
 * inside the repository. A folder that already holds files is refused unless
 * --overwrite is passed, so a rerun never overwrites committed evidence:
 *   - <screen>_<width>.png, <screen>_<width>_fold.png,
 *     prototype_<screen>_<width>.png
 *   - <screen>_<width>.txt when the screen names saveText
 *   - spec.json, the spec that ran
 *   - results.json, every measurement and one pass or fail line per check
 * No absolute local path is written: the repository root and the home folder
 * are replaced with <repo-root> and <home> before anything reaches disk.
 *
 * Exit codes: 0 every scripted check passed, 1 at least one failed or no
 * check ran at all, 2 the target was wrong or unreachable, or the arguments,
 * the widths or the output folder were refused.
 *
 * --self-test runs the guards above against fixed inputs, with no browser
 * and no network, and exits 1 if any guard no longer holds.
 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..", "..", "..");
const PROTOTYPE = path.join(
  REPO_ROOT, "docs", "build", "design", "design-system", "prototype", "app.html",
);
const LIVE_TARGET_TS = path.join(REPO_ROOT, "frontend", "e2e", "live-target.ts");
const PLAYWRIGHT_CONFIG_TS = path.join(REPO_ROOT, "frontend", "playwright.config.ts");

const DEFAULT_WIDTHS = [
  { width: 1280, height: 900 },
  { width: 390, height: 844 },
];
const REQUIRED_WIDTHS = [1280, 390];
const PARTIAL_WIDTHS_NOTE =
  "partial widths: this run does not cover exactly 1280 and 390, so it cannot start the seven-day close";
const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const STEP_TIMEOUT_MS = 30_000;
const NAME_RE = /^[a-z0-9][a-z0-9_-]{0,39}$/i;
const LOOPBACK = ["http://127.0.0.1:", "http://localhost:"];

class UsageError extends Error {}

function fail(message, code = 2) {
  console.error(`verify capture: ${message}`);
  process.exit(code);
}

// ------------------------------------------------------------------ args

function parseArgs(argv) {
  const args = {
    screens: [], target: "develop", settleMs: 1500, prototype: true,
    allowPartialWidths: false, overwrite: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const flag = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) throw new UsageError(`${flag} needs a value`);
      i += 1;
      return argv[i];
    };
    switch (flag) {
      case "--spec": args.spec = next(); break;
      case "--screen": args.screens.push(next()); break;
      case "--topic": args.topic = next(); break;
      case "--target": args.target = next(); break;
      case "--web": args.web = next(); break;
      case "--api": args.api = next(); break;
      case "--out": args.out = next(); break;
      case "--commit": args.commit = next(); break;
      case "--settle-ms": args.settleMs = Number(next()); break;
      case "--no-prototype": args.prototype = false; break;
      case "--allow-partial-widths": args.allowPartialWidths = true; break;
      case "--overwrite": args.overwrite = true; break;
      case "--self-test": args.selfTest = true; break;
      case "--help": case "-h": args.help = true; break;
      default: throw new UsageError(`unknown argument ${JSON.stringify(flag)}`);
    }
  }
  return args;
}

const USAGE = `usage: node capture.mjs (--spec <file.json> | --screen <name>=<path> ...)
         [--topic <slug>] [--target develop|local] [--web <url>] [--api <url>]
         [--out <dir inside the repository>] [--commit <deployed sha>]
         [--settle-ms <ms>] [--no-prototype] [--allow-partial-widths] [--overwrite]
       node capture.mjs --self-test`;

// --------------------------------------------------------------- targets

function readConst(file, name) {
  const text = fs.readFileSync(file, "utf8");
  const match = text.match(new RegExp(`const ${name} = "?([^";\\n]+)"?;`));
  if (!match) throw new UsageError(`${path.relative(REPO_ROOT, file)} no longer defines ${name}`);
  return match[1];
}

function requireHttpsOrLoopback(url, label) {
  if (LOOPBACK.some((prefix) => url.startsWith(prefix))) return url.replace(/\/$/, "");
  if (!url.startsWith("https://")) {
    throw new UsageError(`${label} must be an https:// URL or a loopback address, got ${JSON.stringify(url)}`);
  }
  return url.replace(/\/$/, "");
}

function resolveTarget(args) {
  let web;
  let api;
  if (args.target === "develop") {
    web = process.env.S3_LIVE_WEB_URL ?? readConst(LIVE_TARGET_TS, "DEVELOP_WEB");
    api = process.env.S3_LIVE_API_URL ?? readConst(LIVE_TARGET_TS, "DEVELOP_API");
  } else if (args.target === "local") {
    web = `http://127.0.0.1:${readConst(PLAYWRIGHT_CONFIG_TS, "FRONTEND_PORT")}`;
    api = `http://127.0.0.1:${readConst(PLAYWRIGHT_CONFIG_TS, "BACKEND_PORT")}`;
  } else {
    throw new UsageError(`--target must be develop or local, got ${JSON.stringify(args.target)}`);
  }
  if (args.web) web = args.web;
  if (args.api) api = args.api;
  return {
    name: args.target,
    web: requireHttpsOrLoopback(web, "the web URL"),
    api: requireHttpsOrLoopback(api, "the API URL"),
  };
}

async function readHealth(api) {
  try {
    const response = await fetch(`${api}/health`, { signal: AbortSignal.timeout(20_000) });
    const body = await response.json().catch(() => ({}));
    const appEnv = typeof body.app_env === "string" && body.app_env.trim() ? body.app_env.trim() : "unknown";
    return { status: response.status, app_env: appEnv };
  } catch (error) {
    return { status: null, app_env: "unreachable", error: String(error.message ?? error).slice(0, 200) };
  }
}

// ------------------------------------------------------------------ spec

const STEP_FIELDS = {
  goto: ["path"],
  disclaimer: [],
  fill: ["selector", "text"],
  click: ["selector"],
  press: ["key"],
  waitFor: ["selector"],
  wait: ["ms"],
};

function checkSteps(steps, where) {
  if (!Array.isArray(steps)) throw new UsageError(`${where}.steps must be a list`);
  steps.forEach((step, i) => {
    const required = STEP_FIELDS[step?.do];
    if (!required) throw new UsageError(`${where}.steps[${i}] has unknown action ${JSON.stringify(step?.do)}`);
    for (const field of required) {
      if (step[field] === undefined) throw new UsageError(`${where}.steps[${i}] (${step.do}) needs ${field}`);
    }
  });
}

/**
 * Refuse any widths but exactly 1280 and 390, unless partial widths are
 * allowed. Returns whether the widths are complete. An empty list is refused
 * either way, since it would run no check at all.
 */
function validateWidths(widths, allowPartial) {
  if (!Array.isArray(widths) || widths.length === 0) {
    throw new UsageError("widths must be a non-empty list: a run with no width checks nothing");
  }
  for (const [i, entry] of widths.entries()) {
    if (!Number.isInteger(entry?.width) || entry.width <= 0 || !Number.isInteger(entry?.height) || entry.height <= 0) {
      throw new UsageError(`widths[${i}] needs a positive integer width and height`);
    }
  }
  const given = widths.map((entry) => entry.width).sort((a, b) => a - b);
  const required = [...REQUIRED_WIDTHS].sort((a, b) => a - b);
  const complete = given.length === required.length && given.every((w, i) => w === required[i]);
  if (!complete && !allowPartial) {
    throw new UsageError(
      `widths must be exactly ${REQUIRED_WIDTHS.join(" and ")}, got ${given.join(", ")}. ` +
        "Pass --allow-partial-widths for a diagnosis run, which cannot start the seven-day close",
    );
  }
  return complete;
}

/** Refuse a folder that already holds files, unless overwriting was asked for. */
function checkOutDir(outDir, overwrite) {
  if (overwrite || !fs.existsSync(outDir)) return;
  if (!fs.statSync(outDir).isDirectory()) throw new UsageError(`${rel(outDir)} exists and is not a folder`);
  const held = fs.readdirSync(outDir);
  if (held.length > 0) {
    throw new UsageError(
      `${rel(outDir)} already holds ${held.length} file(s). A rerun never overwrites evidence: ` +
        "let the run take its own new folder, or pass --overwrite",
    );
  }
}

/** One new folder per run: the date and the UTC time to the second. */
function defaultOutDir(now, topic) {
  const iso = now.toISOString();
  const stamp = iso.slice(11, 19).replace(/:/g, "");
  return path.join(REPO_ROOT, "testing", "Developer", "reports", `${iso.slice(0, 10)}_verify_${topic}_${stamp}Z`);
}

/** 0 only when at least one check ran and none failed. */
function exitCodeFor(checks) {
  if (checks.length === 0) return 1;
  return checks.some((c) => c.result === "fail") ? 1 : 0;
}

function loadSpec(args) {
  let spec = { screens: [] };
  if (args.spec) {
    try {
      spec = JSON.parse(fs.readFileSync(path.resolve(args.spec), "utf8"));
    } catch (error) {
      throw new UsageError(`cannot read spec ${args.spec}: ${error.message}`);
    }
  }
  for (const item of args.screens) {
    const [name, screenPath] = item.split("=");
    if (!name || !screenPath || !screenPath.startsWith("/")) {
      throw new UsageError(`--screen takes <name>=/<path>, got ${JSON.stringify(item)}`);
    }
    spec.screens.push({ name, path: screenPath, steps: [{ do: "disclaimer" }] });
  }
  spec.topic = args.topic ?? spec.topic;
  if (!spec.topic || !/^[a-z0-9][a-z0-9_.-]{0,59}$/i.test(spec.topic)) {
    throw new UsageError("a topic is required (--topic or the spec's topic): letters, digits, _ . -");
  }
  if (!Array.isArray(spec.screens) || spec.screens.length === 0) {
    throw new UsageError("no screens: pass --spec or --screen");
  }
  const seen = new Set();
  for (const screen of spec.screens) {
    if (!NAME_RE.test(screen.name ?? "")) throw new UsageError(`bad screen name ${JSON.stringify(screen.name)}`);
    if (seen.has(screen.name)) throw new UsageError(`screen ${screen.name} is named twice`);
    seen.add(screen.name);
    screen.path = screen.path ?? "/";
    screen.steps = screen.steps ?? [];
    checkSteps(screen.steps, screen.name);
    if (screen.prototype) checkSteps(screen.prototype.steps ?? [], `${screen.name}.prototype`);
  }
  spec.widths = spec.widths ?? DEFAULT_WIDTHS;
  spec.widths_complete = validateWidths(spec.widths, args.allowPartialWidths);
  return spec;
}

// ------------------------------------------------------------ playwright

function loadModules() {
  const bases = [path.join(process.cwd(), "package.json"), path.join(REPO_ROOT, "frontend", "package.json")];
  const tried = [];
  for (const base of bases) {
    try {
      const require = createRequire(base);
      const { chromium } = require("@playwright/test");
      const axe = require("@axe-core/playwright");
      return { chromium, AxeBuilder: axe.default ?? axe.AxeBuilder };
    } catch (error) {
      tried.push(`${path.dirname(base)}: ${String(error.message).split("\n")[0]}`);
    }
  }
  throw new UsageError(
    "cannot load @playwright/test and @axe-core/playwright. Run from a frontend/ " +
      `folder whose node_modules has them.\n  ${tried.join("\n  ")}`,
  );
}

async function dismissDisclaimer(page) {
  const appModal = page.locator('[data-testid="disclaimer-modal"]');
  const protoModal = page.locator("#disclaimer");
  await Promise.race([
    appModal.waitFor({ state: "visible", timeout: 10_000 }),
    protoModal.waitFor({ state: "visible", timeout: 10_000 }),
  ]).catch(() => {});
  if (await appModal.isVisible().catch(() => false)) {
    await appModal.getByRole("checkbox").check();
    await appModal.getByRole("button", { name: /continue/i }).click();
    await appModal.waitFor({ state: "hidden", timeout: 10_000 });
  } else if (await protoModal.isVisible().catch(() => false)) {
    await page.locator("#dchk").check();
    await page.locator("#dgo").click();
    await protoModal.waitFor({ state: "hidden", timeout: 10_000 });
  }
}

async function runSteps(page, steps, base) {
  for (const step of steps) {
    const timeout = step.timeoutMs ?? STEP_TIMEOUT_MS;
    switch (step.do) {
      case "goto":
        await page.goto(new URL(step.path, base).href, { waitUntil: "domcontentloaded", timeout: 60_000 });
        break;
      case "disclaimer":
        await dismissDisclaimer(page);
        break;
      case "fill":
        await page.locator(step.selector).first().fill(step.text, { timeout });
        break;
      case "click":
        await page.locator(step.selector).first().click({ timeout });
        break;
      case "press":
        if (step.selector) await page.locator(step.selector).first().press(step.key, { timeout });
        else await page.keyboard.press(step.key);
        break;
      case "waitFor":
        await page.locator(step.selector).first().waitFor({ state: step.state ?? "visible", timeout });
        break;
      case "wait":
        await page.waitForTimeout(step.ms);
        break;
      default:
        throw new Error(`unknown step ${step.do}`);
    }
  }
}

async function measureOverflow(page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    return { scroll_width: root.scrollWidth, client_width: root.clientWidth };
  });
}

/** The innermost elements whose right edge passes the screen's. Candidates, not proof. */
async function overflowCandidates(page) {
  return page.evaluate(() => {
    const limit = document.documentElement.clientWidth + 0.5;
    const past = (el) => {
      const box = el.getBoundingClientRect();
      return box.width > 0 && box.right > limit;
    };
    const found = [];
    for (const el of document.body.querySelectorAll("*")) {
      if (!past(el) || [...el.children].some(past)) continue;
      found.push({
        tag: el.tagName.toLowerCase(),
        testid: el.closest("[data-testid]")?.getAttribute("data-testid") ?? null,
        right_px: Math.round(el.getBoundingClientRect().right),
        text: (el.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 80),
      });
      if (found.length === 5) break;
    }
    return found;
  });
}

// ------------------------------------------------------------- privacy

const REDACTIONS = [
  [pathToFileURL(REPO_ROOT).href, "<repo-root>"],
  [encodeURI(REPO_ROOT), "<repo-root>"],
  [REPO_ROOT, "<repo-root>"],
  [pathToFileURL(os.homedir()).href, "<home>"],
  [encodeURI(os.homedir()), "<home>"],
  [os.homedir(), "<home>"],
];

function redact(text) {
  let out = String(text);
  for (const [needle, placeholder] of REDACTIONS) out = out.split(needle).join(placeholder);
  return out;
}

const rel = (file) => path.relative(REPO_ROOT, file);

// ------------------------------------------------------------------ main

async function main() {
  let args;
  let spec;
  let target;
  try {
    args = parseArgs(process.argv.slice(2));
    if (args.help) {
      console.log(USAGE);
      return 0;
    }
    if (args.selfTest) return selfTest();
    spec = loadSpec(args);
    target = resolveTarget(args);
  } catch (error) {
    if (error instanceof UsageError) fail(`${error.message}\n${USAGE}`);
    throw error;
  }

  const now = new Date();
  const date = now.toISOString().slice(0, 10);
  const outDir = path.resolve(args.out ?? defaultOutDir(now, spec.topic));
  if (!outDir.startsWith(REPO_ROOT + path.sep)) fail("--out must be a folder inside the repository");
  try {
    checkOutDir(outDir, args.overwrite);
  } catch (error) {
    if (error instanceof UsageError) fail(error.message);
    throw error;
  }
  if (!spec.widths_complete) console.log(PARTIAL_WIDTHS_NOTE);

  const health = await readHealth(target.api);
  const results = {
    tool: "verify capture",
    format: 1,
    date,
    topic: spec.topic,
    target: { ...target, health },
    checkout_head: gitHead(),
    deployed_commit: args.commit ?? null,
    widths: spec.widths,
    widths_complete: spec.widths_complete,
    seven_day_close: spec.widths_complete ? "eligible if every check passes" : PARTIAL_WIDTHS_NOTE,
    context: { reduced_motion: "reduce", axe_tags: AXE_TAGS, settle_ms: args.settleMs },
    screens: [],
    checks: [],
    awaiting_judgement: [],
  };

  const wrongTarget =
    health.app_env === "unreachable" || (target.name === "develop" && health.app_env !== "develop");
  fs.mkdirSync(outDir, { recursive: true });
  const writeResults = () =>
    fs.writeFileSync(path.join(outDir, "results.json"), redact(JSON.stringify(results, null, 2)) + "\n");
  fs.writeFileSync(path.join(outDir, "spec.json"), redact(JSON.stringify(spec, null, 2)) + "\n");

  if (wrongTarget) {
    results.stopped = `the API's /health reported app_env ${JSON.stringify(health.app_env)}; nothing was captured`;
    writeResults();
    fail(`${results.stopped}. Evidence: ${rel(path.join(outDir, "results.json"))}`);
  }

  const { chromium, AxeBuilder } = (() => {
    try {
      return loadModules();
    } catch (error) {
      return fail(error.message);
    }
  })();
  const browser = await chromium.launch();
  results.context.browser = `chromium ${browser.version()}`;

  const check = (result, screen, width, name, value, evidence) => {
    results.checks.push({ result, screen, width, check: name, value, evidence });
  };

  try {
    for (const screen of spec.screens) {
      const record = { name: screen.name, path: screen.path, design: screen.design ?? null, captures: [] };
      results.screens.push(record);
      for (const { width, height } of spec.widths) {
        const shot = path.join(outDir, `${screen.name}_${width}.png`);
        const capture = { width, height, screenshot: rel(shot) };
        const context = await browser.newContext({ viewport: { width, height }, reducedMotion: "reduce" });
        const page = await context.newPage();
        const consoleErrors = [];
        page.on("console", (message) => {
          if (message.type() === "error") consoleErrors.push(redact(message.text()).slice(0, 400));
        });
        page.on("pageerror", (error) => consoleErrors.push(`uncaught: ${redact(error.message).slice(0, 400)}`));

        const started = Date.now();
        try {
          await page.goto(new URL(screen.path, target.web).href, { waitUntil: "domcontentloaded", timeout: 60_000 });
          await runSteps(page, screen.steps, target.web);
          capture.reached = true;
        } catch (error) {
          capture.reached = false;
          capture.error = redact(String(error.message ?? error)).split("\n")[0].slice(0, 300);
        }
        capture.seconds_to_ready = Math.round((Date.now() - started) / 100) / 10;
        await page.waitForTimeout(args.settleMs);
        await page.screenshot({ path: shot, fullPage: true });
        const fold = path.join(outDir, `${screen.name}_${width}_fold.png`);
        await page.screenshot({ path: fold });
        capture.first_screen = rel(fold);

        const overflow = await measureOverflow(page);
        capture.overflow_px = overflow.scroll_width - overflow.client_width;
        Object.assign(capture, overflow);
        if (capture.overflow_px > 0) {
          capture.overflow_candidates = (await overflowCandidates(page)).map((c) => ({
            ...c,
            text: redact(c.text),
          }));
        }
        capture.console_errors = consoleErrors;

        try {
          const scan = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
          const blocking = scan.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
          capture.axe = {
            serious_or_critical: blocking.map((v) => ({
              id: v.id,
              impact: v.impact,
              help: v.help,
              nodes: v.nodes.length,
              first_nodes: v.nodes.slice(0, 3).map((n) => ({
                target: redact(n.target.join(" ")).slice(0, 160),
                html: redact(n.html).slice(0, 200),
                summary: redact(n.failureSummary ?? "").replace(/\s+/g, " ").slice(0, 240),
              })),
            })),
            moderate: scan.violations.filter((v) => v.impact === "moderate").length,
            minor: scan.violations.filter((v) => v.impact === "minor").length,
          };
        } catch (error) {
          capture.axe = { error: redact(String(error.message ?? error)).split("\n")[0].slice(0, 300) };
        }

        if (screen.saveText) {
          const textFile = path.join(outDir, `${screen.name}_${width}.txt`);
          const text = await page.locator(screen.saveText).first().innerText({ timeout: 5_000 }).catch(() => "");
          fs.writeFileSync(textFile, redact(text) + "\n");
          capture.text_file = rel(textFile);
        }
        await context.close();

        const evidence = rel(path.join(outDir, "results.json"));
        check(capture.reached ? "pass" : "fail", screen.name, width, "screen reached",
          capture.reached ? `${capture.seconds_to_ready} s` : capture.error, capture.screenshot);
        check(capture.overflow_px <= 0 ? "pass" : "fail", screen.name, width, "horizontal overflow",
          `${capture.overflow_px} px`, evidence);
        check(consoleErrors.length === 0 ? "pass" : "fail", screen.name, width, "console errors",
          `${consoleErrors.length}`, evidence);
        if (capture.axe.error) {
          check("fail", screen.name, width, "accessibility scan", `did not run: ${capture.axe.error}`, evidence);
        } else {
          const ids = capture.axe.serious_or_critical.map((v) => v.id);
          check(ids.length === 0 ? "pass" : "fail", screen.name, width, "accessibility, serious or critical",
            ids.length === 0 ? "0" : `${ids.length}: ${ids.join(", ")}`, evidence);
        }

        if (args.prototype && screen.prototype) {
          const protoShot = path.join(outDir, `prototype_${screen.name}_${width}.png`);
          const protoContext = await browser.newContext({ viewport: { width, height }, reducedMotion: "reduce" });
          const protoPage = await protoContext.newPage();
          try {
            await protoPage.goto(pathToFileURL(PROTOTYPE).href, { waitUntil: "load" });
            await runSteps(protoPage, screen.prototype.steps ?? [], pathToFileURL(PROTOTYPE).href);
            capture.prototype_reached = true;
          } catch (error) {
            capture.prototype_reached = false;
            capture.prototype_error = redact(String(error.message ?? error)).split("\n")[0].slice(0, 300);
          }
          await protoPage.waitForTimeout(args.settleMs);
          await protoPage.screenshot({ path: protoShot, fullPage: true });
          const protoOverflow = await measureOverflow(protoPage);
          capture.prototype_screenshot = rel(protoShot);
          capture.prototype_overflow_px = protoOverflow.scroll_width - protoOverflow.client_width;
          await protoContext.close();
        } else {
          capture.prototype_screenshot = null;
        }
        results.awaiting_judgement.push({
          screen: screen.name,
          width,
          app: capture.screenshot,
          prototype: capture.prototype_screenshot,
          design: record.design,
        });
        record.captures.push(capture);
        writeResults();
      }
    }
  } finally {
    await browser.close();
  }

  const failed = results.checks.filter((c) => c.result === "fail").length;
  results.summary = { pass: results.checks.length - failed, fail: failed };
  writeResults();

  console.log(`target: web=${target.web} api=${target.api} app_env=${health.app_env}`);
  for (const c of results.checks) {
    console.log(`- ${c.result.toUpperCase()} | ${c.screen} at ${c.width} | ${c.check} | ${c.value} | ${c.evidence}`);
  }
  console.log(`awaiting judgement: ${results.awaiting_judgement.length} screenshot pairs`);
  console.log(`scripted checks: ${results.summary.pass} pass, ${results.summary.fail} fail`);
  if (results.checks.length === 0) console.log("no scripted check ran, so nothing passed");
  if (!spec.widths_complete) console.log(PARTIAL_WIDTHS_NOTE);
  console.log(`results: ${rel(path.join(outDir, "results.json"))}`);
  return exitCodeFor(results.checks);
}

// -------------------------------------------------------------- self-test

/**
 * The guards that keep a failing screen from passing, each asserted against
 * fixed inputs. Each assertion must go red when its guard is removed.
 */
function selfTest() {
  const failures = [];
  let ran = 0;
  const expect = (label, condition) => {
    ran += 1;
    if (!condition) failures.push(label);
  };
  const refuses = (fn, about = /./) => {
    try {
      fn();
      return false;
    } catch (error) {
      return error instanceof UsageError && about.test(error.message);
    }
  };

  // Widths: exactly 1280 and 390, or refused.
  expect("the default widths are complete", validateWidths(DEFAULT_WIDTHS, false) === true);
  expect("1280 and 390 in either order are complete",
    validateWidths([{ width: 390, height: 844 }, { width: 1280, height: 900 }], false) === true);
  expect("1280 alone is refused", refuses(() => validateWidths([{ width: 1280, height: 900 }], false)));
  expect("390 alone is refused", refuses(() => validateWidths([{ width: 390, height: 844 }], false)));
  expect("1280 twice is refused",
    refuses(() => validateWidths([{ width: 1280, height: 900 }, { width: 1280, height: 900 }], false)));
  expect("an extra width is refused",
    refuses(() => validateWidths([...DEFAULT_WIDTHS, { width: 768, height: 1024 }], false)));
  expect("an empty list is refused", refuses(() => validateWidths([], false)));
  expect("an empty list is refused even with partial widths allowed", refuses(() => validateWidths([], true)));
  expect("1280 alone runs with partial widths allowed, marked incomplete",
    validateWidths([{ width: 1280, height: 900 }], true) === false);
  expect("a spec with one width is refused by loadSpec", refuses(() => loadSpecFrom({
    topic: "t", widths: [{ width: 1280, height: 900 }], screens: [{ name: "home" }],
  }, false), /widths must be exactly/));
  expect("a spec with both widths loads and is marked complete", loadSpecFrom({
    topic: "t", widths: DEFAULT_WIDTHS, screens: [{ name: "home" }],
  }, false).widths_complete === true);

  // Exit code: no check is not a pass.
  expect("no check ran exits non-zero", exitCodeFor([]) !== 0);
  expect("one fail exits 1", exitCodeFor([{ result: "pass" }, { result: "fail" }]) === 1);
  expect("all passing exits 0", exitCodeFor([{ result: "pass" }]) === 0);

  // Output folder: never overwrite evidence.
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "verify-self-test-"));
  const held = path.join(scratch, "held");
  fs.mkdirSync(held);
  fs.writeFileSync(path.join(held, "results.json"), "{}\n");
  expect("a folder that holds files is refused", refuses(() => checkOutDir(held, false), /already holds/));
  expect("--overwrite lets a folder that holds files through", !refuses(() => checkOutDir(held, true)));
  const emptyDir = path.join(scratch, "empty");
  fs.mkdirSync(emptyDir);
  expect("an empty folder is accepted", !refuses(() => checkOutDir(emptyDir, false)));
  expect("a new folder is accepted", !refuses(() => checkOutDir(path.join(scratch, "new"), false)));
  fs.rmSync(scratch, { recursive: true, force: true });
  const first = defaultOutDir(new Date("2026-09-26T19:03:12Z"), "t");
  const second = defaultOutDir(new Date("2026-09-26T19:03:13Z"), "t");
  expect("two runs a second apart get different folders", first !== second);
  expect("the default folder carries the date and the UTC time",
    path.basename(first) === "2026-09-26_verify_t_190312Z");

  for (const label of failures) console.log(`self-test FAIL: ${label}`);
  console.log(`self-test: ${ran - failures.length} of ${ran} passed`);
  return failures.length === 0 ? 0 : 1;
}

function loadSpecFrom(spec, allowPartialWidths) {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "verify-spec-")), "spec.json");
  fs.writeFileSync(file, JSON.stringify(spec));
  try {
    return loadSpec({ spec: file, screens: [], allowPartialWidths });
  } finally {
    fs.rmSync(path.dirname(file), { recursive: true, force: true });
  }
}

function gitHead() {
  try {
    return execFileSync("git", ["rev-parse", "--short", "HEAD"], {
      cwd: REPO_ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return null;
  }
}

main().then(
  (code) => process.exit(code),
  (error) => fail(redact(String(error.stack ?? error))),
);
