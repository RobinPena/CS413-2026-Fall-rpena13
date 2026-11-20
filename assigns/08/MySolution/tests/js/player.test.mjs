// Client playback tests (TESTING.md R10). Run from assigns/08/ with:
//   node --test MySolution/tests/js/
//
// The fake server replays the real 4x4 trace produced by solver.lam
// (fixtures/size4-trace.json, kept equal to the solver by
// AdapterTests.test_client_fixture_matches_solver) and can hold responses
// back, so tests control exactly when each request completes.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  BATCH_LIMIT, LOG_LIMIT, applyEvent, controlState, createPlayer, delayForSpeed, emptyView, explainReject,
} from "../../static/js/player.js";
import { RpcError, TransportError } from "../../static/js/transport.js";

const TRACE = JSON.parse(readFileSync(new URL("./fixtures/size4-trace.json", import.meta.url)));
const FIRST_SOLUTION = TRACE.findIndex((e) => e.event === "solution"); // 56

// An in-memory queens.* server. With hold: true, each call waits until the
// test calls release() on it.
function fakeServer({ hold = false, failWith = null } = {}) {
  const calls = [];
  const waiting = [];
  const streams = new Map();
  let opened = 0;

  function answer(method, params) {
    if (failWith && method !== "queens.close") throw failWith;
    if (method === "queens.open") {
      opened += 1;
      const id = `stream-${opened}`;
      streams.set(id, 0);
      return { stream_id: id, size: params.size };
    }
    if (!streams.has(params.stream_id)) throw new RpcError(-32020, "Stream not found");
    if (method === "queens.close") {
      streams.delete(params.stream_id);
      return { closed: true };
    }
    const start = streams.get(params.stream_id);
    const events = TRACE.slice(start, start + params.limit);
    const doneAt = events.findIndex((e) => e.event === "done");
    const sent = doneAt === -1 ? events : events.slice(0, doneAt + 1);
    streams.set(params.stream_id, start + sent.length);
    return { events: sent, done: start + sent.length >= TRACE.length };
  }

  const rpc = {
    call(method, params) {
      calls.push({ method, params });
      if (!hold) return Promise.resolve().then(() => answer(method, params));
      return new Promise((resolve, reject) => {
        waiting.push({ method, release: () => { try { resolve(answer(method, params)); } catch (e) { reject(e); } } });
      });
    },
  };
  // Release the oldest held call; returns its method name.
  const release = async () => {
    const call = waiting.shift();
    call.release();
    await flush();
    return call.method;
  };
  return { rpc, calls, waiting, release, streams, methods: () => calls.map((c) => c.method) };
}

function fakeTimers() {
  const timers = new Map();
  let ids = 0;
  return {
    schedule: (fn, ms) => { ids += 1; timers.set(ids, { fn, ms }); return ids; },
    cancel: (id) => { timers.delete(id); },
    get count() { return timers.size; },
    delays: () => [...timers.values()].map((t) => t.ms),
    async runNext() {
      const [id, timer] = timers.entries().next().value;
      timers.delete(id);
      timer.fn();
      await flush();
    },
  };
}

async function flush() {
  for (let i = 0; i < 10; i += 1) await new Promise((resolve) => setImmediate(resolve));
}

function setup(serverOptions = {}) {
  const server = fakeServer(serverOptions);
  const timers = fakeTimers();
  const player = createPlayer({
    rpc: server.rpc, schedule: timers.schedule, cancel: timers.cancel, size: 4, delay: 100,
  });
  return { server, timers, player, state: player.state };
}

test("applyEvent handles each kind", () => {
  let view = emptyView(4);
  view = applyEvent(view, { event: "try", column: 1, row: 1, board: [3] });
  assert.deepEqual(view.board, [3]); // the candidate is not committed
  assert.deepEqual(view.focus, { row: 1, column: 1, kind: "try" });
  view = applyEvent(view, { event: "reject", column: 2, row: 1, board: [3] });
  assert.deepEqual(view.board, [3]);
  assert.deepEqual(view.attack, { row: 0, column: 3, reason: "diagonal", path: [] });
  view = applyEvent(view, { event: "place", column: 0, row: 1, board: [3, 0] });
  assert.deepEqual([view.board, view.focus.kind, view.attack], [[3, 0], "place", null]);
  view = applyEvent(view, { event: "backtrack", column: 0, row: 1, board: [3] });
  assert.deepEqual([view.board, view.focus], [[3], { row: 1, column: 0, kind: "backtrack" }]);
  view = applyEvent(view, { event: "solution", board: [1, 3, 0, 2] });
  assert.deepEqual([view.solutions, view.lastSolution, view.focus], [1, [1, 3, 0, 2], null]);
  view = applyEvent(view, { event: "done" });
  assert.equal(view.complete, true);
  assert.deepEqual(view.counts, { try: 1, place: 1, reject: 1, backtrack: 1, solution: 1 });
  assert.deepEqual(view.log.map((e) => e.text), [
    "Try row 1, column 1",
    "Reject row 1, column 2: on a diagonal with the queen in row 0",
    "Place queen at row 1, column 0",
    "Backtrack: remove the queen from row 1, column 0",
    "Solution 1: [1, 3, 0, 2]",
    "Search complete: 1 solution",
  ]);
});

test("explainReject finds column and both diagonals", () => {
  assert.deepEqual(explainReject([2], 2, 1), { row: 0, column: 2, reason: "column", path: [] });
  assert.deepEqual(explainReject([2, 0], 2, 2), { row: 0, column: 2, reason: "column", path: [[1, 2]] });
  assert.deepEqual(explainReject([1, 5], 3, 2), { row: 0, column: 1, reason: "diagonal", path: [[1, 2]] });
  assert.deepEqual(explainReject([3, 6], 1, 2), { row: 0, column: 3, reason: "diagonal", path: [[1, 2]] });
  assert.equal(explainReject([1, 3, 0], 0, 3).row, 2); // nearest attacker first
  assert.equal(explainReject([1, 3, 0], 2, 3), null);
  for (const e of TRACE.filter((e) => e.event === "reject")) {
    assert.notEqual(explainReject(e.board, e.column, e.row), null, JSON.stringify(e));
  }
});

test("step shows one event with limit 1", async () => {
  const { server, player, state } = setup();
  await player.step();
  assert.deepEqual(server.calls, [
    { method: "queens.open", params: { size: 4 } },
    { method: "queens.next", params: { stream_id: "stream-1", limit: 1 } },
  ]);
  assert.deepEqual([state.view.seq, state.view.lastEvent, state.mode], [1, TRACE[0], "paused"]);
  await player.step();
  assert.deepEqual(server.calls.at(-1), { method: "queens.next", params: { stream_id: "stream-1", limit: 1 } });
  assert.deepEqual([state.view.seq, state.view.lastEvent], [2, TRACE[1]]);
  assert.equal(server.calls.length, 3);
});

test("play schedules and pause stops consumption", async () => {
  const { server, timers, player, state } = setup();
  player.play();
  await flush();
  assert.deepEqual([state.mode, state.view.seq, timers.delays()], ["playing", 1, [100]]);
  await timers.runNext();
  await timers.runNext();
  assert.equal(state.view.seq, 3);
  player.setDelay(40);
  await timers.runNext();
  assert.deepEqual(timers.delays(), [40]); // a new speed applies from the next tick
  player.pause();
  const sent = server.calls.length;
  await flush();
  assert.deepEqual([state.mode, timers.count, server.calls.length], ["paused", 0, sent]);
});

test("pause while a request is in flight buffers the event instead of losing it", async () => {
  const { server, timers, player, state } = setup({ hold: true });
  player.play();
  assert.equal(await server.release(), "queens.open");
  assert.equal(server.waiting[0].method, "queens.next");
  player.pause();
  await server.release();
  assert.deepEqual([state.view.seq, state.buffer, timers.count], [0, [TRACE[0]], 0]);
  const sent = server.calls.length;
  await player.step(); // shown from the buffer, no new request
  assert.deepEqual([state.view.lastEvent, server.calls.length], [TRACE[0], sent]);
});

test("play pressed during a pending step keeps playing", async () => {
  const { server, timers, player, state } = setup({ hold: true });
  const stepping = player.step();
  await server.release(); // open
  player.play();
  assert.equal(state.mode, "playing");
  await server.release(); // the step's next
  await stepping;
  assert.deepEqual([state.view.seq, timers.count], [1, 1]);
  await timers.runNext();
  await server.release();
  assert.equal(state.view.seq, 2);
});

test("next solution stops at solution and buffers the rest", async () => {
  const { server, player, state } = setup();
  await player.nextSolution();
  const reads = server.calls.filter((c) => c.method === "queens.next");
  assert.deepEqual(reads.map((c) => c.params.limit), [BATCH_LIMIT, BATCH_LIMIT]); // event 57 is in the 2nd batch
  assert.deepEqual([state.mode, state.view.seq, state.view.solutions], ["paused", FIRST_SOLUTION + 1, 1]);
  assert.deepEqual(state.view.lastEvent, TRACE[FIRST_SOLUTION]);
  assert.equal(state.buffer.length, 2 * BATCH_LIMIT - (FIRST_SOLUTION + 1));
  const sent = server.calls.length;
  await player.step();
  assert.deepEqual([state.view.lastEvent, server.calls.length], [TRACE[FIRST_SOLUTION + 1], sent]);
  await player.nextSolution();
  assert.deepEqual(state.view.lastSolution, [2, 0, 3, 1]);
});

test("pause at solutions stops playback on a solution", async () => {
  const { timers, player, state } = setup();
  player.play();
  await flush();
  while (state.mode === "playing") await timers.runNext();
  assert.deepEqual([state.mode, state.view.lastEvent.event, timers.count], ["paused", "solution", 0]);
});

test("done disables playback and enables restart", async () => {
  const { server, timers, player, state } = setup();
  player.setPauseAtSolution(false);
  player.play();
  await flush();
  for (let i = 0; i < 200 && state.mode === "playing"; i += 1) await timers.runNext();
  assert.deepEqual([state.mode, state.view.seq, state.view.solutions, state.view.complete], ["done", 139, 2, true]);
  assert.deepEqual(server.calls.at(-1), { method: "queens.close", params: { stream_id: "stream-1" } });
  const controls = controlState(state);
  assert.deepEqual([controls.step.enabled, controls.play.enabled, controls.nextSolution.enabled], [false, false, false]);
  assert.deepEqual(controls.start, { enabled: true, label: "Restart" });
  const sent = server.calls.length;
  await player.step();
  player.play();
  await player.nextSolution();
  assert.equal(server.calls.length, sent);
  player.start();
  await flush();
  assert.deepEqual(server.calls[sent], { method: "queens.open", params: { size: 4 } });
  assert.deepEqual([state.mode, state.view.seq, state.view.solutions], ["playing", 1, 0]);
});

test("reset closes the stream and ignores stale responses", async () => {
  const { server, player, state } = setup({ hold: true });
  player.step();
  await server.release(); // open
  assert.equal(server.waiting[0].method, "queens.next");
  player.reset();
  assert.deepEqual(server.calls.at(-1), { method: "queens.close", params: { stream_id: "stream-1" } });
  assert.deepEqual([state.mode, state.inFlight, state.streamId], ["idle", false, null]);
  await server.release(); // the old next answers late
  assert.deepEqual([state.view.seq, state.buffer, state.mode], [0, [], "idle"]);
});

test("stale open result is closed", async () => {
  const { server, player, state } = setup({ hold: true });
  player.step();
  player.reset();
  await server.release(); // the open answers after the reset
  assert.equal(state.streamId, null);
  assert.deepEqual(server.calls.at(-1), { method: "queens.close", params: { stream_id: "stream-1" } });
  assert.equal(state.view.seq, 0);
});

test("only one request in flight", async () => {
  const { server, player, state } = setup({ hold: true });
  player.step();
  await server.release(); // open
  assert.equal(controlState(state).step.enabled, false);
  player.step();
  player.step();
  player.nextSolution();
  await flush(); // give any request these presses might start time to be sent
  assert.deepEqual(server.methods(), ["queens.open", "queens.next"]);
  await server.release();
  assert.equal(state.view.seq, 1);
});

test("transport and RPC errors are visible and recoverable", async () => {
  for (const [error, expected] of [
    [new TransportError("network error: connection refused"), /Could not reach the server.*Restart/],
    [new RpcError(-32020, "Stream not found"), /expired.*Restart/],
    [new RpcError(-32603, "Internal error"), /error -32603.*Restart/],
  ]) {
    const { server, player, state } = setup({ failWith: error });
    await player.step();
    assert.equal(state.mode, "error");
    assert.match(state.error, expected);
    const controls = controlState(state);
    assert.deepEqual([controls.step.enabled, controls.start.label], [false, "Restart"]);
    server.rpc.call = fakeServer().rpc.call; // the server is back
    player.start();
    await flush();
    assert.deepEqual([state.mode, state.error, state.view.seq], ["playing", null, 1]);
  }
});

test("event log is bounded", () => {
  let view = emptyView(4);
  for (let i = 0; i < 250; i += 1) view = applyEvent(view, TRACE[i % 138]);
  assert.equal(view.log.length, LOG_LIMIT);
  assert.deepEqual([view.log[0].seq, view.log.at(-1).seq], [51, 250]);
});

test("speed slider maps to delays from 1000 ms to 10 ms", () => {
  assert.deepEqual([0, 50, 100].map(delayForSpeed), [1000, 100, 10]);
  // Faster never means slower; whole milliseconds can repeat near 10 ms.
  for (let p = 1; p <= 100; p += 1) assert.ok(delayForSpeed(p) <= delayForSpeed(p - 1), `position ${p}`);
});
