// Runs the browser checklist (TESTING.md section 2, B1-B12) in headless Chrome
// against the real server, by clicking the page's own controls.
//
//   node MySolution/tests/browser/checklist.mjs        (from assigns/08/)
//
// Needs Google Chrome; nothing is installed. Chrome is driven over its
// DevTools protocol with Node's built-in WebSocket. Environment variables:
//   PYTHON  interpreter with Flask (default MySolution/.venv/bin/python)
//   CHROME  Chrome executable (default: the usual macOS location)
// The server log, browser profile and screenshots go to a temporary folder,
// never into the submission.
import { spawn } from "node:child_process";
import { mkdtempSync, openSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const A08 = resolve(new URL("../../..", import.meta.url).pathname);
const PY = process.env.PYTHON ?? join(A08, "MySolution/.venv/bin/python");
const CHROME = process.env.CHROME ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const OUT = mkdtempSync(join(tmpdir(), "queens-checklist-"));
const SHOTS = OUT;
const LOG = join(OUT, "server.log");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const freePort = () => new Promise((resolve) => {
  const s = createServer().listen(0, "127.0.0.1", () => { const { port } = s.address(); s.close(() => resolve(port)); });
});

const results = [];
function check(id, ok, label, detail = "") {
  results.push({ id, ok, label });
  console.log(`${ok ? "PASS" : "FAIL"} ${id} ${label}${ok || !detail ? "" : `  -- ${detail}`}`);
}

const port = await freePort();
const BASE = `http://127.0.0.1:${port}`;
let server;
function startServer() {
  server = spawn(PY, ["-B", "-m", "MySolution", "--port", String(port)], {
    cwd: A08, stdio: ["ignore", openSync(LOG, "a"), openSync(LOG, "a")],
  });
}
async function waitForServer() {
  for (let i = 0; i < 100; i += 1) {
    try { if ((await fetch(BASE + "/")).ok) return; } catch {}
    await sleep(100);
  }
  throw new Error("server did not start");
}
startServer();
await waitForServer();

const debugPort = await freePort();
const profile = join(OUT, "profile");
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--window-size=1280,1000", "about:blank"],
  { stdio: "ignore" });
let target;
for (let i = 0; i < 100 && !target; i += 1) {
  try { target = (await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json()).find((t) => t.type === "page"); } catch {}
  if (!target) await sleep(100);
}

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let nextId = 0;
const pending = new Map();
const listeners = [];
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  else listeners.forEach((l) => l(msg));
});
const cdp = (method, params = {}) => new Promise((resolve, reject) => {
  nextId += 1;
  pending.set(nextId, (msg) => (msg.error ? reject(new Error(`${method}: ${msg.error.message}`)) : resolve(msg.result)));
  ws.send(JSON.stringify({ id: nextId, method, params }));
});
const js = async (expression) => {
  const r = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(`${expression}: ${r.exceptionDetails.exception?.description}`);
  return r.result.value;
};
const shot = async (name) => {
  const { data } = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  writeFileSync(`${SHOTS}/${name}.png`, Buffer.from(data, "base64"));
};

// Record every request the page makes.
const requests = [];
listeners.push((msg) => {
  if (msg.method === "Network.requestWillBeSent") {
    const { url, method, postData } = msg.params.request;
    requests.push({ url, method, body: postData ? JSON.parse(postData) : null });
  }
});
const rpcCalls = (name) => requests.filter((r) => r.body?.method === name);
const consoleErrors = [];
listeners.push((msg) => {
  if (msg.method === "Runtime.exceptionThrown") consoleErrors.push(msg.params.exceptionDetails.exception?.description);
  if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") consoleErrors.push(JSON.stringify(msg.params.args));
});

await cdp("Page.enable");
await cdp("Runtime.enable");
await cdp("Network.enable");
const loaded = new Promise((r) => listeners.push((msg) => msg.method === "Page.loadEventFired" && r()));
await cdp("Page.navigate", { url: BASE + "/" });
await loaded;
await sleep(300);

const click = (id) => js(`document.getElementById(${JSON.stringify(id)}).click()`);
const text = (id) => js(`document.getElementById(${JSON.stringify(id)}).textContent`);
const ui = () => js(`(() => {
  const sq = [...document.querySelectorAll("#board .square")];
  const n = Math.round(Math.sqrt(sq.length));
  const at = (r, c) => sq[r * n + c];
  return {
    n, squares: sq.length,
    marks: sq.map((s, i) => s.dataset.mark ? [Math.floor(i / n), i % n, s.dataset.mark, s.textContent] : null).filter(Boolean),
    attacker: sq.findIndex((s) => s.dataset.attacker), path: sq.filter((s) => s.dataset.path).length,
    lines: document.querySelectorAll("#attack-line line").length,
    status: document.getElementById("status").textContent,
    frame: document.getElementById("board-frame").dataset.state,
    milestone: document.getElementById("milestone").hidden ? null : document.getElementById("milestone").textContent,
    error: document.getElementById("error").hidden ? null : document.getElementById("error").textContent,
    solutions: +document.getElementById("count-solutions").textContent,
    events: +document.getElementById("count-events").textContent,
    mode: document.getElementById("mode").textContent,
    log: document.getElementById("log").children.length,
    buttons: Object.fromEntries([...document.querySelectorAll(".controls button")].map((b) => [b.id, { label: b.textContent, disabled: b.disabled }])),
    activeRow: [...document.querySelectorAll("#row-labels span")].findIndex((s) => s.classList.contains("active")),
  };
})()`);
const until = async (predicate, ms = 30000) => {
  const end = Date.now() + ms;
  while (Date.now() < end) { const s = await ui(); if (predicate(s)) return s; await sleep(50); }
  return ui();
};
const setSpeed = (v) => js(`(() => { const s = document.getElementById("speed"); s.value = ${v}; s.dispatchEvent(new Event("input")); })()`);

try {
  // B1
  let s = await ui();
  check("B1", s.squares === 64 && s.marks.length === 0 && s.solutions === 0 && s.events === 0 && s.mode === "Ready"
    && s.status.startsWith("Press Start") && Object.values(s.buttons).every((b) => b.label.trim()),
    "empty 8x8 board, labeled controls, Ready, 0 solutions");
  check("B1", requests.every((r) => r.url.startsWith(BASE)) && rpcCalls("queens.open").length === 0,
    "page loaded only local assets and opened no stream before a control was used",
    JSON.stringify(requests.map((r) => r.url)));
  await shot("01-initial");

  // B2
  const statuses = [];
  for (let i = 0; i < 3; i += 1) { await click("step"); s = await until((u) => u.events === i + 1); statuses.push(s.status); }
  check("B2", JSON.stringify(statuses) === JSON.stringify(["Try row 0, column 0", "Place queen at row 0, column 0", "Try row 1, column 0"]),
    "Step x3 shows try(0,0), place(0,0), try(1,0)", JSON.stringify(statuses));
  check("B2", JSON.stringify(s.marks) === JSON.stringify([[0, 0, "queen", "♛︎"], [1, 0, "try", "♛︎"]]) && s.activeRow === 1,
    "candidate drawn separately from the committed queen; row 1 marked active", JSON.stringify(s.marks));
  check("B2", rpcCalls("queens.next").every((r) => r.body.params.limit === 1) && rpcCalls("queens.next").length === 3,
    "each Step requested exactly one event (limit 1)");
  await shot("02-try");

  // B3
  await click("step");
  s = await until((u) => u.events === 4);
  check("B3", s.status === "Reject row 1, column 0: same column as the queen in row 0"
    && s.marks.some(([r, c, m, t]) => r === 1 && c === 0 && m === "reject" && t === "✕") && s.attacker === 0 && s.lines === 1,
    "reject shows a red X, outlines the attacker, draws the attack line, and names the reason", JSON.stringify(s));
  for (let i = 0; i < 2; i += 1) await click("step"), await until((u) => u.events === 5 + i);
  s = await ui();
  check("B3", s.status === "Reject row 1, column 1: on a diagonal with the queen in row 0" && s.lines === 1,
    "diagonal rejection is explained too", s.status);
  await shot("03-reject");

  // B4
  await setSpeed(100);
  await click("play");
  await sleep(700);
  s = await ui();
  check("B4", s.mode === "Playing" && s.buttons.play.label === "Pause" && s.events > 20, "Play advances the search", `${s.events} events`);
  await click("play");
  await sleep(100);
  const frozen = { events: (await ui()).events, calls: rpcCalls("queens.next").length };
  await sleep(800);
  s = await ui();
  check("B4", s.mode === "Paused" && s.events === frozen.events && rpcCalls("queens.next").length === frozen.calls,
    "Pause stops events and requests", JSON.stringify({ frozen, now: s.events, calls: rpcCalls("queens.next").length }));
  check("B4", rpcCalls("queens.next").every((r) => r.body.params.limit <= 32), "no request asked for more than 32 events");

  // B5
  await setSpeed(0);
  check("B5", (await text("speed-value")) === "1000 ms per event", "slider shows 1000 ms per event at its slowest");
  await click("play");
  await sleep(150);
  const before = (await ui()).events;
  await sleep(2200);
  const slowGain = (await ui()).events - before;
  await setSpeed(100);
  await sleep(1300); // the slow tick in progress finishes first
  const fastStart = (await ui()).events;
  await sleep(1000);
  const fastGain = (await ui()).events - fastStart;
  await click("play");
  check("B5", slowGain >= 1 && slowGain <= 3 && fastGain >= 20, "speed change applies from the next tick",
    `slow: ${slowGain} events in 2.2 s, fast: ${fastGain} events in 1 s`);

  // B6 + B7
  await click("reset");
  await until((u) => u.events === 0);
  await click("next-solution");
  s = await until((u) => u.solutions === 1 && u.mode === "Paused");
  check("B6", s.frame === "solution" && s.milestone === "Solution 1" && s.status === "Solution 1: [0, 4, 7, 5, 2, 6, 1, 3]" && s.events === 1858,
    "Next solution stops on solution 1 (event 1,858) with gold styling", JSON.stringify({ status: s.status, events: s.events, frame: s.frame }));
  const batches = rpcCalls("queens.next").slice(-59).map((r) => r.body.params.limit);
  check("B6", batches.every((l) => l === 32), "Next solution read in batches of 32 (about 59 requests)");
  await shot("04-solution");
  await click("step");
  s = await until((u) => u.events === 1859);
  check("B6", s.status === "Backtrack: remove the queen from row 7, column 3", "Step after the solution continues with backtrack(3, 7)", s.status);
  check("B7", s.marks.some(([r, c, m, t]) => r === 7 && c === 3 && m === "backtrack" && t === "↩")
    && s.marks.filter(([, , m]) => m === "queen").length === 7 && s.frame === "",
    "backtrack shows the removed square and the restored 7-queen board", JSON.stringify(s.marks));
  await shot("05-backtrack");

  // B8
  await setSpeed(100);
  await click("play");
  await sleep(300);
  const closesBefore = rpcCalls("queens.close").length;
  await click("reset");
  await sleep(600);
  s = await ui();
  check("B8", s.events === 0 && s.marks.length === 0 && s.log === 0 && s.solutions === 0 && s.mode === "Ready",
    "Reset clears board, counters and log, and nothing repaints afterwards", JSON.stringify(s));
  check("B8", rpcCalls("queens.close").length === closesBefore + 1, "Reset sent queens.close for the old stream");

  // B9
  await js(`(() => { const s = document.getElementById("size"); s.value = "4"; s.dispatchEvent(new Event("change")); })()`);
  await js(`(() => { const c = document.getElementById("pause-at-solution"); c.checked = false; c.dispatchEvent(new Event("change")); })()`);
  await click("start");
  s = await until((u) => u.mode === "Complete", 20000);
  check("B9", s.n === 4 && s.solutions === 2 && s.events === 139 && s.milestone === "Search complete: 2 solutions" && s.frame === "done"
    && s.buttons.start.label === "Restart" && s.buttons.step.disabled && s.buttons.play.disabled && s.buttons["next-solution"].disabled,
    "4x4 runs to completion: 2 solutions, blue completion banner, Restart offered", JSON.stringify(s));
  await shot("06-complete");

  // B10
  server.kill();
  await new Promise((r) => server.once("exit", r));
  await click("start");
  s = await until((u) => u.error !== null, 5000);
  check("B10", s.mode === "Stopped by an error" && /Could not reach the server.*Restart/.test(s.error ?? ""),
    "with the server down, a visible error explains what to do", s.error);
  await shot("07-error");
  startServer();
  await waitForServer();
  await click("start");
  s = await until((u) => u.events > 0 && u.error === null, 5000);
  check("B10", s.error === null && s.events > 0, "after the server is back, Restart works");
  await click("reset");

  // B11
  const order = [];
  await js("document.activeElement.blur(); window.scrollTo(0, 0)");
  for (let i = 0; i < 9; i += 1) {
    await cdp("Input.dispatchKeyEvent", { type: "keyDown", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
    await cdp("Input.dispatchKeyEvent", { type: "keyUp", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
    order.push(await js(`(() => { const a = document.activeElement; const s = getComputedStyle(a);
      return [a.id, s.outlineStyle, s.outlineWidth]; })()`));
  }
  const ids = order.map(([id]) => id);
  check("B11", JSON.stringify(ids.slice(0, 8)) === JSON.stringify(["start", "step", "play", "next-solution", "reset", "speed", "size", "pause-at-solution"]),
    "Tab reaches every control in order", JSON.stringify(ids));
  check("B11", order.slice(0, 8).every(([, style, width]) => style === "solid" && width === "3px"), "each focused control shows a 3px focus ring", JSON.stringify(order));
  await js("document.activeElement.blur()");
  await cdp("Input.dispatchKeyEvent", { type: "keyDown", key: "s", code: "KeyS", text: "s" });
  await cdp("Input.dispatchKeyEvent", { type: "keyUp", key: "s", code: "KeyS" });
  s = await until((u) => u.events === 1, 3000);
  check("B11", s.events === 1, "the S shortcut steps once");
  await click("reset");
  await js(`document.getElementById("step").focus()`);
  await shot("08-focus");

  // B12
  await js(`(() => { const s = document.getElementById("size"); s.value = "8"; s.dispatchEvent(new Event("change")); })()`);
  await cdp("Emulation.setDeviceMetricsOverride", { width: 400, height: 900, deviceScaleFactor: 1, mobile: true });
  await sleep(300);
  for (let i = 0; i < 6; i += 1) await click("step"), await until((u) => u.events === i + 1);
  const layout = await js(`(() => { const b = document.getElementById("board").getBoundingClientRect();
    return { scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth, boardLeft: b.left, boardRight: b.right, boardWidth: b.width }; })()`);
  check("B12", layout.scroll <= layout.client && layout.boardLeft >= 0 && layout.boardRight <= 400 && layout.boardWidth >= 280,
    "at 400 px wide: no horizontal scroll and the board stays legible", JSON.stringify(layout));
  await shot("09-narrow");
  await cdp("Emulation.clearDeviceMetricsOverride");

  // Size 10 renders and stays lazy.
  await js(`(() => { const s = document.getElementById("size"); s.value = "10"; s.dispatchEvent(new Event("change")); })()`);
  await click("step");
  s = await until((u) => u.events === 1);
  check("extra", s.n === 10 && s.squares === 100 && s.status === "Try row 0, column 0", "10x10 board renders and steps");
  check("extra", consoleErrors.length === 0, "no JavaScript errors in the page", JSON.stringify(consoleErrors));
} finally {
  ws.close();
  chrome.kill();
  server.kill();
  await sleep(300);
  rmSync(join(OUT, "profile"), { recursive: true, force: true });
}
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} browser checks passed; screenshots in ${SHOTS}`);
process.exit(failed.length ? 1 : 0);
