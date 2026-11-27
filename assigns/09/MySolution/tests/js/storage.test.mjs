// Storage adapter tests (studio/static/js/storage.js). Run from assigns/09/ with:
//   node --test MySolution/tests/js/
//
// A fake fetch records every request and answers like the database service,
// so these tests pin down URLs, methods, headers, bodies, pagination, ETag
// handling, and error decoding without a server.

import assert from "node:assert/strict";
import { test } from "node:test";

import { StorageError, createStorage } from "../../studio/static/js/storage.js";

const BASE = "http://db.test/api/v1";
const PROGRAM = {
  id: "prg_1", name: "square", source: "7 * 7", description: "", revision: 3,
  created_at: "2026-11-24T15:00:00.000Z", updated_at: "2026-11-24T15:05:00.000Z",
};
const COLLECTION = {
  id: "col_1", name: "smoke", description: "", revision: 4, cases: [],
  created_at: "2026-11-24T15:00:00.000Z", updated_at: "2026-11-24T15:05:00.000Z",
};

function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

/** A fake fetch that answers each request with the next of `answers` and records the request. */
function fakeFetch(...answers) {
  const requests = [];
  const fetchFn = async (url, options) => {
    requests.push({ url, ...options, body: options.body === undefined ? undefined : JSON.parse(options.body) });
    const answer = answers.shift();
    if (answer instanceof Error) throw answer;
    return answer;
  };
  return { fetchFn, requests };
}

test("program routes: URL, method, If-Match, body, and the returned etag", async () => {
  const { fetchFn, requests } = fakeFetch(
    json({ program: PROGRAM }, 201, { ETag: '"1"' }),
    json({ program: PROGRAM }, 200, { ETag: '"3"' }),
    json({ program: { ...PROGRAM, revision: 4 } }, 200, { ETag: '"4"' }),
    new Response(null, { status: 204 }),
  );
  const storage = createStorage(fetchFn, BASE);

  assert.deepEqual(await storage.createProgram({ name: " square ", source: "7 * 7", description: "d", extra: 1 }),
    { program: PROGRAM, etag: '"1"' });
  assert.deepEqual(await storage.getProgram("prg_1"), { program: PROGRAM, etag: '"3"' });
  const saved = await storage.updateProgram("prg_1", '"3"', { name: "square", source: "8 * 8" });
  assert.equal(saved.etag, '"4"');
  assert.equal(await storage.deleteProgram("prg_1", '"4"'), undefined);

  assert.deepEqual(requests.map((r) => [r.method, r.url, r.headers["If-Match"]]), [
    ["POST", `${BASE}/programs`, undefined],
    ["GET", `${BASE}/programs/prg_1`, undefined],
    ["PUT", `${BASE}/programs/prg_1`, '"3"'],
    ["DELETE", `${BASE}/programs/prg_1`, '"4"'],
  ]);
  // Bodies hold exactly the accepted fields; the name is sent as typed (the service trims it).
  assert.deepEqual(requests[0].body, { name: " square ", source: "7 * 7", description: "d" });
  assert.deepEqual(requests[2].body, { name: "square", source: "8 * 8", description: "" });
  assert.equal(requests[0].headers["Content-Type"], "application/json");
  assert.equal(requests[1].headers["Content-Type"], undefined);    // no body, no media type
  assert.equal(requests[3].body, undefined);
  assert.ok(requests.every((r) => r.cache === "no-store"));
});

test("case routes use the collection etag and send exactly one expected shape", async () => {
  const answer = () => json({ collection: COLLECTION }, 200, { ETag: '"5"' });
  const { fetchFn, requests } = fakeFetch(answer(), answer(), answer(), answer());
  const storage = createStorage(fetchFn, BASE);

  await storage.addCase("col_1", '"4"', {
    name: "fact", source: "fact(6)", description: "", expected: { kind: "value", value: "720", category: "syntax" },
  });
  await storage.updateCase("col_1", "case_1", '"5"', {
    name: "bad", source: "if then", expected: { kind: "error", category: "syntax", value: "" },
  });
  const deleted = await storage.deleteCase("col_1", "case_1", '"6"');
  await storage.updateCollection("col_1", '"7"', { name: "renamed" });

  assert.deepEqual(requests.map((r) => [r.method, r.url, r.headers["If-Match"]]), [
    ["POST", `${BASE}/collections/col_1/cases`, '"4"'],
    ["PUT", `${BASE}/collections/col_1/cases/case_1`, '"5"'],
    ["DELETE", `${BASE}/collections/col_1/cases/case_1`, '"6"'],
    ["PUT", `${BASE}/collections/col_1`, '"7"'],
  ]);
  assert.deepEqual(requests[0].body.expected, { kind: "value", value: "720" });
  assert.deepEqual(requests[1].body, { name: "bad", source: "if then", expected: { kind: "error", category: "syntax" },
    description: "" });
  assert.deepEqual(requests[3].body, { name: "renamed", description: "" });
  assert.deepEqual(deleted, { collection: COLLECTION, etag: '"5"' });   // case delete answers with the collection
});

test("IDs are URL-encoded", async () => {
  const { fetchFn, requests } = fakeFetch(json({ program: PROGRAM }, 200, { ETag: '"1"' }));
  await createStorage(fetchFn, BASE).getProgram("a/b?c");
  assert.equal(requests[0].url, `${BASE}/programs/a%2Fb%3Fc`);
});

test("lists follow the cursor chain with the largest page size", async () => {
  const page = (items, next_cursor) => json({ items, next_cursor });
  const { fetchFn, requests } = fakeFetch(
    page([{ id: "a" }, { id: "b" }], "key.2"),
    page([{ id: "c" }], "key+/=.3"),
    page([], null),
  );
  const records = await createStorage(fetchFn, BASE).listPrograms();
  assert.deepEqual(records.map((r) => r.id), ["a", "b", "c"]);
  assert.deepEqual(requests.map((r) => r.url), [
    `${BASE}/programs?limit=100`,
    `${BASE}/programs?limit=100&cursor=key.2`,
    `${BASE}/programs?limit=100&cursor=key%2B%2F%3D.3`,
  ]);
});

test("a single-page list makes one request", async () => {
  const { fetchFn, requests } = fakeFetch(json({ items: [COLLECTION], next_cursor: null }));
  assert.deepEqual(await createStorage(fetchFn, BASE).listCollections(), [COLLECTION]);
  assert.deepEqual(requests.map((r) => r.url), [`${BASE}/collections?limit=100`]);
});

test("API errors are decoded, with conflict and not-found predicates", async () => {
  const conflict = json({ error: { code: "revision_conflict", message: "stale", current_revision: 7 } }, 409);
  const invalid = json({ error: { code: "invalid_request", message: "name must contain a non-whitespace character.",
    field: "name", reason: "blank" } }, 400);
  const missing = json({ error: { code: "record_not_found", message: "No program has ID 'x'." } }, 404);
  const { fetchFn } = fakeFetch(conflict, invalid, missing);
  const storage = createStorage(fetchFn, BASE);

  const stale = await storage.updateProgram("x", '"1"', { name: "a", source: "1" }).catch((e) => e);
  assert.ok(stale instanceof StorageError);
  assert.deepEqual([stale.kind, stale.status, stale.code, stale.currentRevision, stale.isConflict, stale.isNotFound],
    ["api", 409, "revision_conflict", 7, true, false]);

  const bad = await storage.createProgram({ name: " ", source: "1" }).catch((e) => e);
  assert.deepEqual([bad.code, bad.field, bad.reason, bad.message],
    ["invalid_request", "name", "blank", "name must contain a non-whitespace character."]);

  const gone = await storage.getProgram("x").catch((e) => e);
  assert.deepEqual([gone.isNotFound, gone.isConflict], [true, false]);
});

test("network failures and non-API answers become actionable StorageErrors", async () => {
  const cases = {
    network: [new TypeError("Failed to fetch"), "network", /Cannot reach the database service at http:\/\/db\.test/],
    "HTML error page": [new Response("<h1>Bad Gateway</h1>", { status: 502 }), "http", /HTTP 502/],
    "JSON without the envelope": [json({ detail: "nope" }, 500), "http", /HTTP 500/],
    "200 that is not JSON": [new Response("ok", { status: 200 }), "http", /unreadable/],
    "record without its ETag": [json({ program: PROGRAM }), "http", /ETag/],
  };
  for (const [label, [answer, kind, message]] of Object.entries(cases)) {
    const { fetchFn } = fakeFetch(answer);
    const error = await createStorage(fetchFn, BASE).getProgram("prg_1").catch((e) => e);
    assert.ok(error instanceof StorageError, label);
    assert.equal(error.kind, kind, label);
    assert.match(error.message, message, label);
    assert.equal(error.isConflict, false, label);
  }
});

test("health returns the service's answer", async () => {
  const { fetchFn, requests } = fakeFetch(json({ status: "ok", version: "1.0" }));
  assert.deepEqual(await createStorage(fetchFn, BASE).health(), { status: "ok", version: "1.0" });
  assert.equal(requests[0].url, `${BASE}/health`);
});
