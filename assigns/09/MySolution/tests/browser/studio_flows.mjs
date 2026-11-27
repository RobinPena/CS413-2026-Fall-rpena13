// Drives the LAMBDA-studio flows (DESIGN.md STU-2 to STU-9, DATA-12) in headless
// Chrome by using the page's own controls, against the real services:
//
//   - the Assign07 LAMBDA3 service, started unchanged from ../07;
//   - the database service (python -m MySolution);
//   - the studio host (python -m MySolution.studio);
//
// each on a free local port. Nothing is mocked. Run from assigns/09/:
//
//   node MySolution/tests/browser/studio_flows.mjs
//
// Needs Google Chrome and both virtual environments; nothing is installed.
// Environment variables: PYTHON (default MySolution/.venv/bin/python),
// LAMBDA_PYTHON (default ../07/MySolution/.venv/bin/python), CHROME (default:
// the usual macOS location). Service logs, the browser profile, and
// screenshots go to a temporary folder, never into the submission. The
// exit status is 1 if any check fails.

import { spawn } from "node:child_process";
import { mkdtempSync, openSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const A09 = resolve(new URL("../../..", import.meta.url).pathname);
const A07 = resolve(A09, "../07");
const PYTHON = process.env.PYTHON ?? join(A09, "MySolution/.venv/bin/python");
const LAMBDA_PYTHON = process.env.LAMBDA_PYTHON ?? join(A07, "MySolution/.venv/bin/python");
const CHROME = process.env.CHROME ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const OUT = mkdtempSync(join(tmpdir(), "studio-flows-"));

const FACTORIAL = "let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end";
const FIB_26 = "let fib : sint -> sint = fix fib(n: sint): sint => if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(26) end";

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
const freePort = () => new Promise((done) => {
  const probe = createServer().listen(0, "127.0.0.1", () => {
    const { port } = probe.address();
    probe.close(() => done(port));
  });
});

// ------------------------------------------------------------------ checks

const results = [];
function expect(condition, message) {
  if (!condition) throw new Error(message);
}
function expectEqual(actual, expected, what) {
  const [a, e] = [JSON.stringify(actual), JSON.stringify(expected)];
  if (a !== e) throw new Error(`${what}: expected ${e}, got ${a}`);
}
async function check(id, label, body) {
  try {
    await body();
    results.push({ id, ok: true });
    console.log(`PASS ${id} ${label}`);
  } catch (error) {
    results.push({ id, ok: false });
    console.log(`FAIL ${id} ${label}  -- ${error.message}`);
    await shot(`failed-${id}`).catch(() => {});
  }
}

// ---------------------------------------------------------------- services

function startService(name, python, cwd, args, ready) {
  const log = openSync(join(OUT, `${name}.log`), "a");
  const child = spawn(python, ["-B", "-m", ...args], { cwd, stdio: ["ignore", log, log] });
  const service = {
    child,
    async waitUntilReady() {
      for (let i = 0; i < 200; i += 1) {
        try {
          if (await ready()) return;
        } catch { /* not up yet */ }
        await sleep(50);
      }
      throw new Error(`${name} did not start; see ${OUT}/${name}.log`);
    },
    async stop() {
      if (child.exitCode !== null || child.signalCode !== null) return;   // already stopped
      const exited = new Promise((done) => child.once("exit", done));
      child.kill("SIGTERM");
      await exited;
    },
  };
  return service;
}

const [lambdaPort, dbPort, studioPort] = [await freePort(), await freePort(), await freePort()];
const LAMBDA_URL = `http://127.0.0.1:${lambdaPort}/rpc`;
const DB = `http://127.0.0.1:${dbPort}/api/v1`;
const STUDIO = `http://127.0.0.1:${studioPort}`;

const lambdaReady = async () => (await fetch(LAMBDA_URL, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ jsonrpc: "2.0", method: "service.health", params: {}, id: 1 }),
})).ok;
const startLambda3 = () => startService("lambda3", LAMBDA_PYTHON, A07, ["MySolution", "--port", String(lambdaPort)], lambdaReady);
const startDatabase = () => startService("database", PYTHON, A09,
  ["MySolution", "--port", String(dbPort), "--studio-origin", STUDIO], async () => (await fetch(`${DB}/health`)).ok);

let lambda3 = startLambda3();
let database = startDatabase();
const studio = startService("studio", PYTHON, A09, ["MySolution.studio", "--port", String(studioPort),
  "--database-url", DB, "--lambda-url", LAMBDA_URL], async () => (await fetch(`${STUDIO}/config.json`)).ok);
await Promise.all([lambda3.waitUntilReady(), database.waitUntilReady(), studio.waitUntilReady()]);

/** A direct REST call, standing in for another browser tab or checking what the server holds. */
async function rest(method, path, { body, ifMatch } = {}) {
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (ifMatch) headers["If-Match"] = ifMatch;
  const response = await fetch(DB + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const text = await response.text();
  return { status: response.status, etag: response.headers.get("ETag"), body: text ? JSON.parse(text) : null };
}

// ------------------------------------------------------------------ Chrome

const debugPort = await freePort();
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${debugPort}`,
  `--user-data-dir=${join(OUT, "profile")}`, "--no-first-run", "--no-default-browser-check",
  "--hide-scrollbars", "--window-size=1280,1000", "about:blank"], { stdio: "ignore" });
let target;
for (let i = 0; i < 200 && !target; i += 1) {
  try {
    target = (await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json()).find((t) => t.type === "page");
  } catch { /* not up yet */ }
  if (!target) await sleep(50);
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((done) => ws.addEventListener("open", done, { once: true }));

let nextId = 0;
const pending = new Map();
const listeners = [];
ws.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  } else {
    listeners.forEach((listener) => listener(message));
  }
});
const cdp = (method, params = {}) => new Promise((done, fail) => {
  nextId += 1;
  pending.set(nextId, (message) => (message.error ? fail(new Error(`${method}: ${message.error.message}`)) : done(message.result)));
  ws.send(JSON.stringify({ id: nextId, method, params }));
});
async function js(expression) {
  const reply = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (reply.exceptionDetails) throw new Error(`${expression}: ${reply.exceptionDetails.exception?.description}`);
  return reply.result.value;
}
async function shot(name) {
  const { data } = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  writeFileSync(join(OUT, `${name}.png`), Buffer.from(data, "base64"));
}

// Every request the page makes, every dialog it opens (accepted, like a user
// clicking OK), and every uncaught error.
const requests = [];
const dialogs = [];
const pageErrors = [];
listeners.push((message) => {
  if (message.method === "Network.requestWillBeSent") {
    const { url, method, headers, postData } = message.params.request;
    requests.push({ url, method, headers, body: postData ?? null });
  } else if (message.method === "Page.javascriptDialogOpening") {
    dialogs.push(message.params.message);
    cdp("Page.handleJavaScriptDialog", { accept: true });
  } else if (message.method === "Runtime.exceptionThrown") {
    pageErrors.push(message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text);
  }
});
await cdp("Page.enable");
await cdp("Runtime.enable");
await cdp("Network.enable");

async function load(navigate) {
  const loaded = new Promise((done) => {
    const listener = (message) => {
      if (message.method === "Page.loadEventFired") {
        listeners.splice(listeners.indexOf(listener), 1);
        done();
      }
    };
    listeners.push(listener);
  });
  await navigate();
  await loaded;
  await waitFor(`!document.getElementById("db-status").textContent.includes("checking")`);
}

// ---------------------------------------------------------- page helpers

const q = JSON.stringify;
const el = (id) => `document.getElementById(${q(id)})`;
const click = (id) => js(`${el(id)}.click()`);
const text = (id) => js(`${el(id)}.textContent.trim()`);
const value = (id) => js(`${el(id)}.value`);
const shown = (id) => js(`(() => { const e = ${el(id)}; return !e.hidden && e.offsetParent !== null; })()`);
const message = () => js(`${el("message")}.hidden ? "" : ${el("message")}.textContent`);
async function fill(id, text) {
  await js(`(() => { const e = ${el(id)}; e.value = ${q(text)};
    e.dispatchEvent(new Event("input", { bubbles: true })); e.dispatchEvent(new Event("change", { bubbles: true })); })()`);
}
async function waitFor(expression, timeout = 10_000) {
  const deadline = Date.now() + timeout;
  for (;;) {
    const result = await js(expression);
    if (result) return result;
    if (Date.now() > deadline) throw new Error(`timed out waiting for ${expression}`);
    await sleep(50);
  }
}
const waitForMessage = (fragment, timeout) =>
  waitFor(`!${el("message")}.hidden && ${el("message")}.textContent.includes(${q(fragment)})`, timeout);

const listNames = (listId) => js(`[...document.querySelectorAll("#${listId} .record-name")].map((e) => e.textContent)`);
async function openFromList(listId, name) {
  await js(`[...document.querySelectorAll("#${listId} button.record")]
    .find((b) => b.querySelector(".record-name").textContent === ${q(name)}).click()`);
}
const caseNames = () => js(`[...document.querySelectorAll("#case-list > li strong")].map((e) => e.textContent)`);
async function caseButton(name, kind) {
  await js(`[...document.querySelectorAll("#case-list > li")]
    .find((li) => li.querySelector("strong").textContent.endsWith(". " + ${q(name)}))
    .querySelector(".case-${kind}").click()`);
}
async function addCase(name, source, kind, expectedValue = "") {
  await fill("case-name", name);
  await fill("case-source", source);
  await fill("case-expected-kind", kind);
  await fill("case-expected-value", expectedValue);
  await click("case-save");
  await waitForMessage(`Added the case "${name}"`);
}
const runRows = () => js(`[...document.querySelectorAll("#run-results tr")].map((tr) => ({
  name: tr.cells[1].querySelector("div").childNodes[0].textContent,
  expected: tr.cells[2].textContent, actual: tr.cells[3].textContent, verdict: tr.cells[4].textContent,
  note: tr.querySelector(".badge")?.textContent ?? null, source: tr.querySelector("pre").textContent }))`);
// The run section is numbered per run and says when its run is over, so a
// test never mistakes an earlier run's rows for the new run's.
const runSection = el("run-section");
async function startRun() {
  const before = await js(`Number(${runSection}.dataset.run ?? 0)`);
  await click("collection-run");
  await waitFor(`Number(${runSection}.dataset.run ?? 0) > ${before}`);
  return before + 1;
}
const runFinished = (number) =>
  waitFor(`${runSection}.dataset.run === "${number}" && ${runSection}.dataset.state === "finished"`, 30_000);
async function runAll() {
  await runFinished(await startRun());
}
const requestsTo = (prefix, method) => requests.filter((r) => r.url.startsWith(prefix) && (!method || r.method === method));

// ------------------------------------------------------------------ flows

await load(() => cdp("Page.navigate", { url: `${STUDIO}/` }));

await check("S1", "page loads, both services connected, memory warning shown", async () => {
  expectEqual(await text("db-status"), "Database: connected", "database chip");
  expectEqual(await text("lambda-status"), "LAMBDA3: connected", "LAMBDA3 chip");
  expect(await shown("memory-warning"), "memory warning hidden");
  expect((await text("memory-warning")).includes("erased when the database service stops or restarts"), "warning text");
  expect(await shown("program-list-empty"), "empty program list not reported");
});

let factorialId;
await check("F1a", "create a program and run it; unsaved edits are marked until saved", async () => {
  await fill("program-name", "  factorial ");
  await fill("program-source", FACTORIAL);
  expect(await shown("program-unsaved"), "no unsaved marker while editing");
  expect((await js("document.title")).startsWith("●"), "title does not show unsaved changes");
  await click("program-save");
  await waitForMessage('Saved "factorial" as revision 1');
  expect(!(await shown("program-unsaved")), "unsaved marker still shown after saving");
  expectEqual(await text("program-meta"), "revision 1", "revision shown");
  expectEqual(await listNames("program-list"), ["factorial"], "program list");
  const { body } = await rest("GET", "/programs");
  expectEqual(body.items.map((p) => [p.name, p.source, p.revision]), [["factorial", FACTORIAL, 1]], "server copy");
  factorialId = body.items[0].id;
  await click("program-run");
  await waitFor(`!${el("program-run")}.disabled`);
  expectEqual(await text("program-output"), "720 : sint", "Run in LAMBDA3 output");
});

await check("F1b", "after a browser reload the program is listed, opens, and saves changes", async () => {
  await load(() => cdp("Page.reload", { ignoreCache: true }));
  await waitFor(`document.querySelectorAll("#program-list button.record").length === 1`);
  expectEqual(await value("program-name"), "", "editor starts empty");
  await openFromList("program-list", "factorial");
  await waitFor(`${el("program-meta")}.textContent === "revision 1"`);
  expectEqual([await value("program-name"), await value("program-source")], ["factorial", FACTORIAL], "opened program");
  await fill("program-description", "six factorial");
  expect(await shown("program-unsaved"), "no unsaved marker");
  await click("program-save");
  await waitForMessage("as revision 2");
  const { body } = await rest("GET", `/programs/${factorialId}`);
  expectEqual([body.program.revision, body.program.description], [2, "six factorial"], "saved on the server");
});

await check("F1c", "a second program is listed after the first", async () => {
  await click("program-new");
  await fill("program-name", "square");
  await fill("program-source", "(lam (x: sint) => x * x)(7)");
  await click("program-save");
  await waitForMessage('Saved "square"');
  await waitFor(`document.querySelectorAll("#program-list button.record").length === 2`);
  expectEqual(await listNames("program-list"), ["factorial", "square"], "creation order");
  await openFromList("program-list", "factorial");
  await waitFor(`${el("program-meta")}.textContent === "revision 2"`);
});

const OTHER_TAB_SOURCE = FACTORIAL.replace("fact(6)", "fact(5)");
const MY_SOURCE = FACTORIAL.replace("fact(6)", "fact(8)");
await check("F2a", "a stale save shows a conflict, keeps local edits, and overwrites nothing", async () => {
  // Another tab saves revision 3 while this page still holds revision 2.
  const other = await rest("PUT", `/programs/${factorialId}`, { ifMatch: '"2"',
    body: { name: "factorial", source: OTHER_TAB_SOURCE, description: "from the other tab" } });
  expectEqual(other.status, 200, "other tab's save");
  await fill("program-source", MY_SOURCE);
  const putsBefore = requestsTo(DB, "PUT").length;
  await click("program-save");
  await waitFor(`!${el("program-conflict")}.hidden`);
  const conflict = await text("program-conflict-text");
  expect(conflict.includes("revision 2") && conflict.includes("revision 3"), `conflict text: ${conflict}`);
  expectEqual(await value("program-source"), MY_SOURCE, "local edits kept in the editor");
  expect(await shown("program-unsaved"), "edits no longer marked unsaved");
  await sleep(300);
  expectEqual(requestsTo(DB, "PUT").length - putsBefore, 1, "PUT requests for one save (no automatic retry)");
  const { body } = await rest("GET", `/programs/${factorialId}`);
  expectEqual([body.program.revision, body.program.source], [3, OTHER_TAB_SOURCE], "server copy after the conflict");
  await shot("conflict");
});

await check("F2b", "Reload server copy loads revision 3 and keeps the user's version visible", async () => {
  await click("program-conflict-reload");
  await waitFor(`${el("program-meta")}.textContent === "revision 3"`);
  expectEqual([await value("program-source"), await value("program-description")],
    [OTHER_TAB_SOURCE, "from the other tab"], "editor after reload");
  expect(!(await shown("program-conflict")), "conflict panel still shown");
  expect(!(await shown("program-unsaved")), "reloaded copy marked unsaved");
  expect((await text("program-kept-text")).includes("fact(8)"), "the user's version was not kept");
  await fill("program-source", FACTORIAL);
  await click("program-save");
  await waitForMessage("as revision 4");
});

let smokeId;
await check("F3a", "create a collection and add cases of each expected kind", async () => {
  await click("tab-collections");
  await fill("new-collection-name", "smoke tests");
  await js(`document.querySelector("#collection-create button[type=submit]").click()`);
  await waitForMessage('Created the test collection "smoke tests"');
  expectEqual(await text("collection-title"), "smoke tests", "collection title");
  await click("case-use-program");                            // copy the factorial source from the editor
  expectEqual(await value("case-source"), FACTORIAL, "copied source");
  await fill("case-name", "factorial 6");
  await fill("case-expected-value", "720");
  await click("case-save");
  await waitForMessage('Added the case "factorial 6"');
  await addCase("bad syntax", "if then", "syntax");
  await addCase("bad argument", "(lam (x: sint) => x)(true)", "type");
  await addCase("wrong on purpose", "6 * 7", "value", "41");
  await addCase("runtime error", "1 / 0", "syntax");
  await addCase("temporary", "0", "value", "0");
  expectEqual((await caseNames()).length, 6, "case count");
  smokeId = (await rest("GET", "/collections")).body.items[0].id;
});

await check("F3b", "edit a case in place and delete another; order is kept", async () => {
  await caseButton("bad syntax", "edit");
  expectEqual(await text("case-form-title"), "Edit case: bad syntax", "form title");
  await fill("case-source", "let x = in x end");
  expect(await shown("case-unsaved"), "case form not marked unsaved");
  await click("case-save");
  await waitForMessage('Saved the case "bad syntax"');
  await caseButton("temporary", "delete");
  await waitForMessage('Deleted the case "temporary"');
  const expected = ["1. factorial 6", "2. bad syntax", "3. bad argument", "4. wrong on purpose", "5. runtime error"];
  expectEqual(await caseNames(), expected, "cases on the page");
  const { body } = await rest("GET", `/collections/${smokeId}`);
  expectEqual(body.collection.cases.map((c) => c.name), expected.map((n) => n.slice(3)), "cases on the server");
  expectEqual(body.collection.cases[1].source, "let x = in x end", "edited source");
  expectEqual(body.collection.revision, 9, "collection revision (1 + 6 adds + 1 edit + 1 delete)");
});

await check("F3c", "the collection reloads from the service, also after a browser reload", async () => {
  await click("collection-reload");
  await waitForMessage("Loaded revision 9");
  await load(() => cdp("Page.reload", { ignoreCache: true }));
  await click("tab-collections");
  await waitFor(`document.querySelectorAll("#collection-list button.record").length === 1`);
  await openFromList("collection-list", "smoke tests");
  await waitFor(`document.querySelectorAll("#case-list > li").length === 5`);
  expectEqual((await caseNames())[4], "5. runtime error", "last case after reload");
});

await check("F4", "running the collection uses the real LAMBDA3, reports each case, and continues after failures", async () => {
  const before = requests.length;
  await runAll();
  const rows = await runRows();
  expectEqual(rows.map((r) => [r.name, r.verdict]), [
    ["factorial 6", "PASS"], ["bad syntax", "PASS"], ["bad argument", "PASS"],
    ["wrong on purpose", "FAIL"], ["runtime error", "FAIL"]], "verdicts");
  expectEqual(rows[0].actual, "720 : sint", "factorial result");
  expect(rows[1].actual.includes("(-32010)") && rows[2].actual.includes("(-32011)"), "error categories");
  expectEqual(rows[3].actual, "42 : sint", "mismatched value");
  expect(rows[4].actual.includes("(-32013)"), "a runtime error never matches an expected syntax error");
  expectEqual(await text("run-summary"),
    "3 of 5 passed, 2 failed. Each row shows the case as it was when the run started.", "summary");
  const calls = requests.slice(before).filter((r) => r.url === `${STUDIO}/lambda/rpc`);
  expectEqual(calls.map((r) => JSON.parse(r.body).method), Array(5).fill("lambda.interpret"), "LAMBDA3 calls");
  expect(requests.slice(before).filter((r) => r.url.startsWith(DB)).every((r) => r.method === "GET"),
    "the run changed something in the database");
  await shot("run");
});

await check("F4b", "a run uses the cases saved on the server, not a stale page or unsaved form text", async () => {
  // Another tab fixes "wrong on purpose" (revision 9 -> 10); this page still shows revision 9.
  const { body } = await rest("GET", `/collections/${smokeId}`);
  const wrong = body.collection.cases[3];
  const fix = await rest("PUT", `/collections/${smokeId}/cases/${wrong.id}`, { ifMatch: '"9"',
    body: { name: wrong.name, source: "6 * 7", expected: { kind: "value", value: "42" }, description: "" } });
  expectEqual(fix.status, 200, "other tab's fix");
  // This page starts editing "factorial 6" but does not save.
  await caseButton("factorial 6", "edit");
  await fill("case-source", "1 / 0");
  await runAll();
  const rows = await runRows();
  expectEqual(rows.map((r) => r.verdict), ["PASS", "PASS", "PASS", "PASS", "FAIL"], "verdicts");
  expectEqual([rows[0].source, rows[3].expected], [FACTORIAL, 'value "42"'], "what ran");
  expectEqual(await value("case-source"), "1 / 0", "unsaved form text kept");
  await click("case-cancel");                          // discard it (the confirmation is accepted)
});

await check("STU-8", "editing a case during a run cannot mislabel its result", async () => {
  await fill("new-collection-name", "identity");
  await js(`document.querySelector("#collection-create button[type=submit]").click()`);
  await waitForMessage('Created the test collection "identity"');
  await addCase("slow", FIB_26, "syntax");             // times out after LAMBDA3's 2-second deadline
  await addCase("answer", "6 * 7", "value", "42");
  const run = await startRun();
  await waitFor(`document.querySelector("#run-results tr")?.cells[3].textContent === "running…"`);
  // While "slow" is still running, edit "answer" through the page.
  await caseButton("answer", "edit");
  await fill("case-source", "1 + 1");
  await fill("case-expected-value", "2");
  await click("case-save");
  await waitForMessage('Saved the case "answer"');
  expect(await js(`${runSection}.dataset.state === "running"`), "the run ended before the edit");
  await runFinished(run);
  const rows = await runRows();
  expectEqual(rows.map((r) => [r.name, r.verdict, r.expected, r.source, r.note]), [
    ["slow", "FAIL", "syntax error", FIB_26, null],
    ["answer", "PASS", 'value "42"', "6 * 7", "edited since this run"]], "results after the edit");
  expect(rows[0].actual.includes("(-32012)"), "a timeout never matches an expected error");
  expectEqual(rows[1].actual, "42 : sint", "answer's result");
  const { body } = await rest("GET", "/collections");
  const identity = body.items.find((c) => c.name === "identity");
  expectEqual([identity.cases[1].source, identity.cases[1].expected.value], ["1 + 1", "2"], "the edit was saved");
  await shot("run-identity");
});

await check("STU-6", "unsaved collection and case edits are marked, and leaving warns", async () => {
  await fill("case-name", "half typed");
  expect(await shown("case-unsaved"), "case form not marked unsaved");
  await js(`document.getElementById("collection-details-box").open = true`);
  await fill("collection-name", "identity renamed");
  expect(await shown("collection-unsaved"), "collection details not marked unsaved");
  expect((await js("document.title")).startsWith("●"), "title does not show unsaved changes");
  const warned = await js(`(() => { const e = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(e); return e.defaultPrevented; })()`);
  expect(warned, "leaving the page does not warn about unsaved edits");
  await click("collection-reload");                   // reloading keeps what was typed
  await waitForMessage("Loaded revision");
  expectEqual([await value("case-name"), await value("collection-name")], ["half typed", "identity renamed"],
    "typed text after reload");
  await click("case-cancel");                          // discards the case text (confirmed)
  await fill("collection-name", "identity");
});

await check("STU-7a", "validation and duplicate-name errors are shown and nothing is saved", async () => {
  await click("tab-programs");
  await click("program-new");
  await fill("program-name", "   ");
  await fill("program-source", "1");
  await click("program-save");
  await waitForMessage("Not saved: name must contain a non-whitespace character.");
  await fill("program-name", "factorial ");
  await click("program-save");
  await waitForMessage("Not saved: Another program is already named 'factorial'.");
  expectEqual((await rest("GET", "/programs")).body.items.length, 2, "programs on the server");
});

await check("STU-7b", "with LAMBDA3 stopped, every case fails as a transport failure and the run continues", async () => {
  await lambda3.stop();
  await click("tab-collections");
  await openFromList("collection-list", "smoke tests");
  await waitFor(`${el("collection-title")}.textContent === "smoke tests"`);
  await runAll();
  const rows = await runRows();
  expect(rows.every((r) => r.verdict === "FAIL" && r.actual.startsWith("LAMBDA3 unavailable: HTTP 502")),
    `rows: ${JSON.stringify(rows.map((r) => r.actual))}`);
  await waitForMessage("Run finished: 0 of 5 cases passed, 5 failed.");
});

await check("STU-7c", "with the database stopped, network errors are actionable and edits are kept", async () => {
  await database.stop();
  await click("tab-programs");
  await click("programs-refresh");
  await waitForMessage(`Could not load the saved programs: Cannot reach the database service at ${DB}`);
  await fill("program-name", "kept");
  await fill("program-source", "1 + 1");
  await click("program-save");
  await waitForMessage("Not saved: Cannot reach the database service");
  expectEqual([await value("program-name"), await value("program-source")], ["kept", "1 + 1"], "editor text");
});

await check("DATA-12", "the page shows both services down; a restarted database service starts empty", async () => {
  await fill("program-name", "");                     // nothing unsaved, so the reloads are not held up
  await fill("program-source", "");
  await load(() => cdp("Page.reload", { ignoreCache: true }));   // LAMBDA3 and the database are both stopped
  await waitFor(`!${el("lambda-status")}.textContent.includes("checking")`);
  expectEqual([await text("db-status"), await text("lambda-status")],
    ["Database: unreachable", "LAMBDA3: unreachable"], "status chips while stopped");
  database = startDatabase();
  await database.waitUntilReady();
  await load(() => cdp("Page.reload", { ignoreCache: true }));
  expectEqual(await text("db-status"), "Database: connected", "database chip after the restart");
  await waitFor(`!${el("program-list-empty")}.hidden`);
  expectEqual(await listNames("program-list"), [], "programs after restart");
  await click("tab-collections");
  await waitFor(`!${el("collection-list-empty")}.hidden`);
  expectEqual((await rest("GET", "/collections")).body.items, [], "collections on the server");
});

await check("STU-1", "every database change carried If-Match; no LAMBDA3 call went to the database", async () => {
  // Updates, deletes, and case additions need If-Match; creating a program or collection does not.
  const changes = requestsTo(DB).filter((r) => ["PUT", "DELETE"].includes(r.method)
    || (r.method === "POST" && r.url.endsWith("/cases")));
  expect(changes.length >= 14, `only ${changes.length} changes recorded`);
  expect(changes.every((r) => /^"\d+"$/.test(r.headers["If-Match"] ?? "")), "a change without If-Match");
  expect(requestsTo(DB).every((r) => !(r.body ?? "").includes("jsonrpc")), "a JSON-RPC body was sent to the database");
  expectEqual(pageErrors, [], "uncaught page errors");
});

// ---------------------------------------------------------------- finish

ws.close();
const chromeExited = chrome.exitCode !== null || chrome.signalCode !== null
  ? Promise.resolve() : new Promise((done) => chrome.once("exit", done));
chrome.kill();
await Promise.all([chromeExited, lambda3.stop(), database.stop(), studio.stop()]);
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed. `
  + `Dialogs accepted: ${dialogs.length}. Logs and screenshots: ${OUT}`);
// Chrome's helper processes may still be closing profile files just after it exits.
if (!failed.length) rmSync(join(OUT, "profile"), { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
process.exit(failed.length ? 1 : 0);
