// Running a test collection: snapshot the cases, run them one at a time,
// and compare each outcome with the case's stored expectation.
//
//   const cases = snapshotCases(collection);           // frozen at run start
//   const results = await runCases(cases, lambda3.interpret, { onResult });
//   const { total, passed, failed } = summarize(results);
//
// Each result carries the case ID, source, and expectation captured when the
// run started, so editing a case while the run is going on cannot change
// what a result says it ran. Cases run in order, one at a time; a failing or
// crashing case is recorded and the run moves on to the next one.

/** Deep, frozen copies of a collection's cases, in their stored order. */
export function snapshotCases(collection) {
  return Object.freeze(collection.cases.map((item) => Object.freeze({
    caseId: item.id,
    name: item.name,
    source: item.source,
    expected: Object.freeze(item.expected.kind === "value"
      ? { kind: "value", value: item.expected.value }
      : { kind: "error", category: item.expected.category }),
  })));
}

/**
 * Whether an outcome satisfies an expectation (README.md, "How outcomes are compared"):
 * a value matches only a successful run with exactly the same formatted value;
 * "syntax" and "type" match only that LAMBDA3 error. Timeouts, runtime errors,
 * transport failures, and other errors never match an expected error.
 */
export function matches(expected, outcome) {
  if (expected.kind === "value") return outcome.kind === "value" && outcome.value === expected.value;
  return outcome.kind === "error" && outcome.category === expected.category;
}

/** Run every snapshot in order through `interpret` (source -> outcome). */
export async function runCases(snapshots, interpret, { onStart, onResult } = {}) {
  const results = [];
  for (const [index, snapshot] of snapshots.entries()) {
    onStart?.(snapshot, index);
    let outcome;
    try {
      outcome = await interpret(snapshot.source);
    } catch (error) {
      // interpret is not expected to throw; if it does, the case fails and the run goes on.
      outcome = { kind: "error", category: "transport", code: null, message: `could not run: ${error?.message ?? error}` };
    }
    const result = Object.freeze({ ...snapshot, outcome, passed: matches(snapshot.expected, outcome) });
    results.push(result);
    onResult?.(result, index);
  }
  return results;
}

export function summarize(results) {
  const passed = results.filter((result) => result.passed).length;
  return { total: results.length, passed, failed: results.length - passed };
}

/** A short description of an expectation, for display. */
export function describeExpected(expected) {
  return expected.kind === "value" ? `value ${JSON.stringify(expected.value)}` : `${expected.category} error`;
}

/** How a case in the current collection differs from what a result ran, or null. */
export function changeSinceRun(result, collection) {
  const current = collection?.cases.find((item) => item.id === result.caseId);
  if (!current) return "deleted since this run";
  const unchanged = current.source === result.source && sameExpected(current.expected, result.expected);
  return unchanged ? null : "edited since this run";
}

function sameExpected(a, b) {
  return a.kind === b.kind && (a.kind === "value" ? a.value === b.value : a.category === b.category);
}
