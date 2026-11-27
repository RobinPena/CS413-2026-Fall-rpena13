// Run-logic tests (studio/static/js/runner.js). Run from assigns/09/ with:
//   node --test MySolution/tests/js/
//
// Comparison rules, continuing after failures, one case at a time, and
// results tied to the snapshot taken when the run started.

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  changeSinceRun, describeExpected, matches, runCases, snapshotCases, summarize,
} from "../../studio/static/js/runner.js";

const value = (v) => ({ kind: "value", value: v });
const syntax = { kind: "error", category: "syntax" };
const type = { kind: "error", category: "type" };
const got = (v, t = "sint") => ({ kind: "value", type: t, value: v });
const failed = (category, code = null) => ({ kind: "error", category, code, message: category });

function collectionWith(...cases) {
  return {
    id: "col_1",
    cases: cases.map(([id, source, expected]) => ({ id, name: `case ${id}`, source, expected, description: "" })),
  };
}

test("a value expectation matches only a successful run with exactly that value", () => {
  assert.equal(matches(value("720"), got("720")), true);
  assert.equal(matches(value("720"), got("720", "sint")), true);
  assert.equal(matches(value(""), got("")), true);
  for (const outcome of [got("721"), got(" 720"), got("720 "), got("720.0"), failed("syntax", -32010),
    failed("timeout", -32012), failed("transport")]) {
    assert.equal(matches(value("720"), outcome), false, JSON.stringify(outcome));
  }
});

test("syntax and type expectations match only that LAMBDA3 error", () => {
  assert.equal(matches(syntax, failed("syntax", -32010)), true);
  assert.equal(matches(type, failed("type", -32011)), true);
  assert.equal(matches(syntax, failed("type", -32011)), false);
  assert.equal(matches(type, failed("syntax", -32010)), false);
  // Timeouts, runtime errors, transport failures, and unexpected server errors never match.
  for (const category of ["timeout", "runtime", "transport", "internal", "rejected", "protocol"]) {
    assert.equal(matches(syntax, failed(category)), false, category);
    assert.equal(matches(type, failed(category)), false, category);
  }
  assert.equal(matches(syntax, got("1")), false);
});

test("snapshots are frozen deep copies in stored order", () => {
  const collection = collectionWith(["a", "1 + 1", value("2")], ["b", "if then", { ...syntax, extra: "x" }]);
  const snapshots = snapshotCases(collection);
  assert.deepEqual(snapshots, [
    { caseId: "a", name: "case a", source: "1 + 1", expected: { kind: "value", value: "2" } },
    { caseId: "b", name: "case b", source: "if then", expected: { kind: "error", category: "syntax" } },
  ]);
  assert.ok(Object.isFrozen(snapshots) && Object.isFrozen(snapshots[0]) && Object.isFrozen(snapshots[0].expected));
  collection.cases[0].source = "changed";
  collection.cases[0].expected.value = "changed";
  assert.equal(snapshots[0].source, "1 + 1");
  assert.equal(snapshots[0].expected.value, "2");
});

test("one failure does not stop the run, even if interpret throws", async () => {
  const collection = collectionWith(["a", "1 / 0", value("0")], ["b", "boom", value("1")],
    ["c", "if then", syntax], ["d", "6 * 7", value("42")]);
  const answers = { "1 / 0": failed("runtime", -32013), "if then": failed("syntax", -32010), "6 * 7": got("42") };
  const interpret = async (source) => {
    if (source === "boom") throw new Error("socket closed");
    return answers[source];
  };
  const seen = [];
  const results = await runCases(snapshotCases(collection), interpret, { onResult: (r) => seen.push(r.caseId) });
  assert.deepEqual(results.map((r) => [r.caseId, r.passed]), [["a", false], ["b", false], ["c", true], ["d", true]]);
  assert.deepEqual(seen, ["a", "b", "c", "d"]);
  assert.equal(results[1].outcome.category, "transport");
  assert.match(results[1].outcome.message, /socket closed/);
  assert.deepEqual(summarize(results), { total: 4, passed: 2, failed: 2 });
});

test("cases run one at a time, in order", async () => {
  let running = 0;
  let most = 0;
  const order = [];
  const interpret = async (source) => {
    running += 1;
    most = Math.max(most, running);
    order.push(source);
    await new Promise((resolve) => setTimeout(resolve, 5));
    running -= 1;
    return got(source);
  };
  await runCases(snapshotCases(collectionWith(["a", "1", value("1")], ["b", "2", value("2")], ["c", "3", value("3")])),
    interpret);
  assert.equal(most, 1);
  assert.deepEqual(order, ["1", "2", "3"]);
});

test("editing or deleting cases during a run cannot change what the results say", async () => {
  const collection = collectionWith(["a", "slow", value("1")], ["b", "6 * 7", value("42")], ["c", "2", value("2")]);
  const snapshots = snapshotCases(collection);
  const interpret = async (source) => {
    if (source === "slow") {
      // While the first case runs, the user edits case b and deletes case c.
      collection.cases[1] = { ...collection.cases[1], source: "0", expected: value("0") };
      collection.cases.splice(2, 1);
      return got("1");
    }
    return got(source === "6 * 7" ? "42" : source);
  };
  const results = await runCases(snapshots, interpret);
  assert.deepEqual(results.map((r) => [r.caseId, r.source, r.expected.value, r.passed]),
    [["a", "slow", "1", true], ["b", "6 * 7", "42", true], ["c", "2", "2", true]]);
  assert.equal(changeSinceRun(results[0], collection), null);
  assert.equal(changeSinceRun(results[1], collection), "edited since this run");
  assert.equal(changeSinceRun(results[2], collection), "deleted since this run");
});

test("changeSinceRun notices a changed expectation", () => {
  const collection = collectionWith(["a", "1", value("1")]);
  const [snapshot] = snapshotCases(collection);
  collection.cases[0].expected = syntax;
  assert.equal(changeSinceRun(snapshot, collection), "edited since this run");
});

test("describeExpected", () => {
  assert.equal(describeExpected(value("720")), 'value "720"');
  assert.equal(describeExpected(type), "type error");
});
