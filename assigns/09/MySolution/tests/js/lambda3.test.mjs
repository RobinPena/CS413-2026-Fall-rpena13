// LAMBDA3 client tests (studio/static/js/lambda3.js). Run from assigns/09/ with:
//   node --test MySolution/tests/js/
//
// The answers below are the shapes the Assign07 service produces (its RPC.md
// section 7). The real service is exercised by tests/test_studio_host.py and
// the browser flows.

import assert from "node:assert/strict";
import { test } from "node:test";

import { createLambda3Client, describeOutcome } from "../../studio/static/js/lambda3.js";

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** A client whose fake fetch answers each call with `respond(requestBody)`. */
function clientAnswering(respond) {
  const sent = [];
  const client = createLambda3Client(async (url, options) => {
    const body = JSON.parse(options.body);
    sent.push({ url, options, body });
    return respond(body);
  });
  return { client, sent };
}

const rpcError = (code, message, data) => (request) => json({ jsonrpc: "2.0", error: { code, message, data }, id: request.id });

test("interpret sends lambda.interpret through the studio host and returns the value", async () => {
  const { client, sent } = clientAnswering((request) =>
    json({ jsonrpc: "2.0", result: { type: "sint", value: "720" }, id: request.id }));
  assert.deepEqual(await client.interpret("fact(6)"), { kind: "value", type: "sint", value: "720" });
  await client.interpret("1");
  assert.deepEqual(sent.map((s) => s.body), [
    { jsonrpc: "2.0", method: "lambda.interpret", params: { source: "fact(6)" }, id: 1 },
    { jsonrpc: "2.0", method: "lambda.interpret", params: { source: "1" }, id: 2 },
  ]);
  assert.equal(sent[0].url, "/lambda/rpc");
  assert.equal(sent[0].options.method, "POST");
  assert.equal(sent[0].options.headers["Content-Type"], "application/json");
});

test("LAMBDA3 error codes map to outcome categories", async () => {
  const cases = [
    [-32010, "LAMBDA syntax error", { diagnostic: "Expected an expression", line: 1, column: 4 }, "syntax"],
    [-32011, "LAMBDA type error", { diagnostic: "function application: expected sint, got bool" }, "type"],
    [-32012, "Execution timed out", { limit_seconds: 2.0 }, "timeout"],
    [-32013, "LAMBDA runtime error", { diagnostic: "division by zero" }, "runtime"],
    [-32602, "Invalid params", { param: "source", reason: "too_large" }, "rejected"],
    [-32603, "Internal error", { incident: "0123456789ab" }, "internal"],
    [-32600, "Invalid Request", { reason: "bad_jsonrpc" }, "protocol"],
    [-32601, "Method not found", undefined, "protocol"],
  ];
  for (const [code, message, data, category] of cases) {
    const { client } = clientAnswering(rpcError(code, message, data));
    const outcome = await client.interpret("x");
    assert.deepEqual([outcome.kind, outcome.category, outcome.code], ["error", category, code], message);
    assert.match(outcome.message, new RegExp(`\\(${code}\\)`));
  }
  const { client } = clientAnswering(rpcError(-32010, "LAMBDA syntax error",
    { diagnostic: "Expected an expression", line: 1, column: 4 }));
  assert.equal(describeOutcome(await client.interpret("if then")),
    "LAMBDA syntax error (-32010): Expected an expression at line 1, column 4");
});

test("anything other than a JSON-RPC answer is a transport outcome, never thrown", async () => {
  const cases = {
    "network failure": async () => { throw new TypeError("fetch failed"); },
    "502 from the studio host": async () => new Response("502 Bad Gateway: no LAMBDA3.\n", { status: 502 }),
    "415 from LAMBDA3": async () => new Response("415 Unsupported Media Type\n", { status: 415 }),
    "204 for a call": async () => new Response(null, { status: 204 }),
    "body not JSON": async () => new Response("<html>", { status: 200 }),
    "id mismatch": async () => json({ jsonrpc: "2.0", result: { type: "sint", value: "1" }, id: 99 }),
    "null body": async () => json(null),
  };
  for (const [label, fetchFn] of Object.entries(cases)) {
    const outcome = await createLambda3Client(fetchFn).interpret("1");
    assert.equal(outcome.kind, "error", label);
    assert.equal(outcome.category, "transport", label);
    assert.match(outcome.message, /^LAMBDA3 unavailable: /, label);
  }
  const outcome = await createLambda3Client(cases["502 from the studio host"]).interpret("1");
  assert.equal(outcome.message, "LAMBDA3 unavailable: HTTP 502: 502 Bad Gateway: no LAMBDA3.");
});

test("a malformed result is a protocol outcome", async () => {
  const { client } = clientAnswering((request) => json({ jsonrpc: "2.0", result: { type: "sint" }, id: request.id }));
  assert.equal((await client.interpret("1")).category, "protocol");
});

test("isAvailable reports whether service.health answers", async () => {
  const up = clientAnswering((request) => json({ jsonrpc: "2.0", result: { status: "ok", version: "1.0" }, id: request.id }));
  assert.equal(await up.client.isAvailable(), true);
  assert.equal(up.sent[0].body.method, "service.health");
  assert.equal(await createLambda3Client(async () => { throw new TypeError("down"); }).isAvailable(), false);
});

test("describeOutcome shows a value with its type", () => {
  assert.equal(describeOutcome({ kind: "value", type: "sint", value: "720" }), "720 : sint");
});
