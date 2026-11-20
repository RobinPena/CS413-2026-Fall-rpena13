// JSON-RPC client tests (TESTING.md R10). Run from assigns/08/ with:
//   node --test MySolution/tests/js/

import assert from "node:assert/strict";
import { test } from "node:test";

import { RpcError, TransportError, createRpcClient } from "../../static/js/transport.js";

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

test("rpc client sends JSON-RPC 2.0 requests with increasing ids", async () => {
  const sent = [];
  const client = createRpcClient(async (url, options) => {
    sent.push({ url, options, body: JSON.parse(options.body) });
    return jsonResponse({ jsonrpc: "2.0", result: { ok: sent.length }, id: sent.at(-1).body.id });
  }, "/rpc");
  assert.deepEqual(await client.call("queens.open", { size: 8 }), { ok: 1 });
  assert.deepEqual(await client.call("queens.next", { stream_id: "s", limit: 1 }), { ok: 2 });
  assert.deepEqual(sent.map((s) => s.body), [
    { jsonrpc: "2.0", method: "queens.open", params: { size: 8 }, id: 1 },
    { jsonrpc: "2.0", method: "queens.next", params: { stream_id: "s", limit: 1 }, id: 2 },
  ]);
  assert.equal(sent[0].url, "/rpc");
  assert.equal(sent[0].options.method, "POST");
  assert.equal(sent[0].options.headers["Content-Type"], "application/json");
});

test("rpc client maps errors", async () => {
  const error = await createRpcClient(async () => jsonResponse({
    jsonrpc: "2.0", error: { code: -32020, message: "Stream not found", data: { x: 1 } }, id: 1,
  })).call("queens.next", {}).catch((e) => e);
  assert.ok(error instanceof RpcError);
  assert.deepEqual([error.code, error.message, error.data], [-32020, "Stream not found", { x: 1 }]);

  const failures = {
    "network failure": async () => { throw new TypeError("fetch failed"); },
    "HTTP 415": async () => new Response("415 Unsupported Media Type", { status: 415 }),
    "HTTP 204 for a call": async () => new Response(null, { status: 204 }),
    "body not JSON": async () => new Response("<html>", { status: 200 }),
    "id mismatch": async () => jsonResponse({ jsonrpc: "2.0", result: {}, id: 99 }),
    "null body": async () => jsonResponse(null),
  };
  for (const [label, fetchFn] of Object.entries(failures)) {
    const caught = await createRpcClient(fetchFn).call("service.health", {}).catch((e) => e);
    assert.ok(caught instanceof TransportError, `${label}: ${caught}`);
  }
});
