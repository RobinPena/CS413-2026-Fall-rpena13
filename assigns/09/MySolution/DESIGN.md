# In-Memory Database Service for LAMBDA-studio — Design

This document records the requirements baseline, the architecture, and the
design decisions for Assignment 09. The REST contract itself is in `API.md`.
Test evidence is in `TESTING.md`.

## 1. Sources

| Source | What it contributes |
| --- | --- |
| `../Assign09.md` | The assignment. It is authoritative for routes, status codes, envelopes, entities, and rules. |
| `../../07/Assign07.md`, `../../07/MySolution/` | The LAMBDA3 JSON-RPC service that executes stored test cases. It is used unchanged. |
| `../../08/Assign08.md`, `../../08/MySolution/` | The N-Queens stream service and browser client. Only patterns are reused (see D6). |
| `../../03/LAMBDA-UI-informal-requirements.md`, `../../03/MySolution/REQUIREMENTS.md` | The studio's stakeholder needs: named tests, expected answers or errors, surviving reloads, keeping work when the compiler is unreachable. |

## 2. Requirements baseline

The identifiers below are used in `API.md`, `TESTING.md`, and test names.
Each group corresponds to one of the five equally weighted rubric categories.
`AI-TRANSCRIPT.md` is the student's own work and is not tracked here.

### Rubric 1 — REST contract, HTTP semantics, validation, and errors

| ID | Requirement |
| --- | --- |
| CON-1 | A versioned contract (`/api/v1`) is documented in `API.md` before routes are implemented. It includes a route table, complete request and response schemas, examples, status codes, and error codes. |
| CON-2 | A machine-readable description exists for all request and response bodies: OpenAPI or JSON Schema. |
| CON-3 | `GET /api/v1/health` returns `200 {"status":"ok","version":"1.0"}`. |
| CON-4 | Successful reads and writes return JSON with `Content-Type: application/json`. Successful program and collection deletes return `204`. |
| CON-5 | Request bodies must be JSON. Any other media type gets `415`. |
| CON-6 | Malformed JSON and invalid fields or parameters get `400 invalid_request`. |
| CON-7 | A missing record or an unknown route gets `404 record_not_found`. |
| CON-8 | A known route called with an unsupported method gets `405`, using a documented code. |
| CON-9 | An oversized request body gets `413`, using a documented code. |
| CON-10 | A duplicate name gets `409 duplicate_name`. A stale revision gets `409 revision_conflict`. A capacity limit gets `409 capacity_limit`. |
| CON-11 | An unexpected failure gets `500 internal_error`, without leaking internal details. |
| CON-12 | Every error uses the same JSON envelope `{"error":{"code","message",...}}` with `Content-Type: application/json`. |
| VAL-1 | Unknown request fields are rejected, including server-managed fields (`id`, timestamps, `revision`, `cases`). |
| VAL-2 | A name is a required string. It is trimmed, must not be blank, and the trimmed value is stored and returned. |
| VAL-3 | A source is a required, nonempty string. It is stored exactly as sent, with no trimming. |
| VAL-4 | A description is an optional string that defaults to `""`. |
| VAL-5 | `expected` is exactly one of `{"kind":"value","value":string}`, `{"kind":"error","category":"syntax"}`, or `{"kind":"error","category":"type"}`. Extra or mixed fields are rejected. |
| VAL-6 | Documented limits apply to source size, description length, page size, cases per collection, and total records. Exceeding a limit returns a useful error. |
| VAL-7 | Route and query parameters (`limit`, `cursor`, IDs) are validated. |

### Rubric 2 — In-memory data model and CRUD behavior

| ID | Requirement |
| --- | --- |
| DATA-1 | A program has these fields: `id`, `name`, `source`, `description`, `created_at`, `updated_at`, `revision`. |
| DATA-2 | A collection has these fields: `id`, `name`, `description`, `created_at`, `updated_at`, `revision`, and `cases` (an ordered array). |
| DATA-3 | A case has these fields: `id` (unique within its collection), `name`, `source`, `expected`, `description`. |
| DATA-4 | The service generates opaque string IDs. Clients never supply them. |
| DATA-5 | Timestamps are UTC ISO 8601 strings. |
| DATA-6 | Programs support create, list, get, update (full replacement of name, source, and description), and delete. |
| DATA-7 | Collections support create, list, get, update, and delete. An update changes metadata only and leaves cases and their order unchanged. |
| DATA-8 | Adding a case appends it. Updating a case changes it in place, keeping its ID and position. Deleting a case keeps the remaining order. Every case mutation returns the parent collection. |
| DATA-9 | Trimmed names are unique among programs, among collections, and among the cases of one collection. Equal names are allowed across those scopes. |
| DATA-10 | Deleting a collection removes its cases. |
| DATA-11 | Updating or deleting a program never changes any test case. A case holds its own source snapshot. |
| DATA-12 | Records live only in process memory: no SQLite, files, browser storage, or other database. A restart clears everything. The documentation and the studio both say so. |
| DATA-13 | The database service never parses, type-checks, interprets, compiles, or executes LAMBDA source. |

### Rubric 3 — Revisions, atomic mutations, and pagination

| ID | Requirement |
| --- | --- |
| REV-1 | A new record starts at revision 1. Each successful update increments the revision by exactly 1. Each case mutation increments the parent collection's revision by exactly 1. A delete does not create a new revision. |
| REV-2 | A strong ETag (`"<revision>"`) is sent on GET and on every mutation response, including case deletion. |
| REV-3 | Updates and deletes require `If-Match` with the exact current ETag. A missing record returns `404`, whatever its precondition. An existing record without `If-Match` returns `428`. |
| REV-4 | A stale `If-Match` returns `409 revision_conflict` with `current_revision`, and the record is left unchanged. |
| REV-5 | Mutations are atomic. A failed validation, uniqueness, capacity, or revision check leaves no partial effect. |
| REV-6 | When two updates are sent concurrently with the same revision, exactly one succeeds and the other gets `409`. |
| PAGE-1 | `limit` has a documented default and maximum, and invalid values are rejected. |
| PAGE-2 | Lists use a deterministic order. |
| PAGE-3 | Cursors are opaque. The first page creates a snapshot, and every later page in its chain returns the captured representations in the same order. Records added later are excluded. Records updated or deleted later keep their captured form. |
| PAGE-4 | A malformed, unknown, or expired cursor gets a documented `400` error. |
| PAGE-5 | Cursors stop working when the process stops. Snapshot storage, memory cost, and lifetime are documented, and valid snapshots are never evicted silently. |
| PAGE-6 | List items are full representations. Collection items include their ordered cases. |

### Rubric 4 — LAMBDA-studio adapter and end-to-end workflows

| ID | Requirement |
| --- | --- |
| STU-1 | One storage adapter contains all REST URLs, payloads, pagination, error decoding, ETags, and `If-Match` handling. UI code holds none of these details. |
| STU-2 | Flow 1: list saved programs, create one, open one, edit it, and save the changes. |
| STU-3 | Flow 2: a stale-revision conflict is shown. The newer server copy is never overwritten silently, and the user can reload it explicitly. Local edits are not discarded automatically, and a stale mutation is never retried automatically. |
| STU-4 | Flow 3: create a named collection, add, edit, and delete cases, and reload the collection from the service. |
| STU-5 | Flow 4: running a collection sends each saved case to the real LAMBDA3 service, compares the outcome with the stored expectation, and shows a per-case pass/fail summary. One failure does not stop the remaining cases. |
| STU-6 | Flow 5: unsaved edits are clearly marked, and the page explains that database contents are cleared when the service stops. |
| STU-7 | Network, HTTP, API, and validation errors are shown as actionable messages. |
| STU-8 | Each run result is tied to the case ID, source snapshot, and expectation captured when the run started. An edit made during the run cannot mislabel the result. |
| STU-9 | Comparison rules: a value expectation matches only a successful run whose formatted value is exactly equal. `syntax` matches only a LAMBDA3 syntax error, and `type` matches only a type-check error. A timeout, transport failure, runtime error, or unexpected server error never matches. |

### Rubric 5 — Automated tests, architecture, and reproducible documentation

| ID | Requirement |
| --- | --- |
| DOC-1 | `README.md` covers versions, setup, dependency installation, test and start commands, service URLs, client instructions, limits, examples, and memory/reset behavior. It explains how the Assign07 service is obtained and started. |
| DOC-2 | `TESTING.md` maps behaviors to test names and records observed results. |
| DOC-3 | An architecture diagram shows studio → storage adapter → REST API → in-memory store, and studio → LAMBDA3, with the database separate from execution. |
| DOC-4 | Automated HTTP tests cover Assign09 test items 1–8 through the HTTP test client, using data created through the public API. |
| DOC-5 | A studio-level integration demonstration saves and reloads a program, then creates and runs a collection through the real LAMBDA3 service, reporting an expected success and an expected error (Assign09 test item 9). |
| DOC-6 | The submission contains no virtual environments, caches, installed dependencies, secrets, or runtime database dumps. |

## 3. Architecture

Three local processes:

```text
 Browser: LAMBDA-studio page, served by the studio host
 ┌────────────────────────────────────────────────────────┐
 │  UI (main.js): programs, collections, run results      │
 │       │                      │                         │
 │  storage adapter           LAMBDA3 client, run logic   │
 │  (storage.js)              (lambda3.js, runner.js)     │
 └───────┼──────────────────────┼─────────────────────────┘
         │ REST, ETag/If-Match  │ JSON-RPC 2.0, same origin
         ▼                      ▼
 ┌────────────────────┐  ┌─────────────────────┐   ┌────────────────────┐
 │ Database service   │  │ Studio host         │   │ LAMBDA3 service    │
 │ (Assign09) :8009   │  │ (Assign09) :8010    │──▶│ (Assign07) :8000   │
 │ /api/v1/...        │  │ static page files   │   │ POST /rpc          │
 │ routes             │  │ POST /lambda/rpc    │   │ parse, type-check, │
 │ → validation       │  │ forwarder           │   │ interpret          │
 │ → business rules   │  │ (no LAMBDA logic)   │   │ (unchanged)        │
 │ → in-memory store  │  └─────────────────────┘   └────────────────────┘
 │ (no LAMBDA code)   │
 └────────────────────┘
```

The page comes from the studio host, so its calls to the database service
are cross-origin. The database service answers them with CORS headers for
that one origin (D4).

- **Saving and reloading a program.** UI → `storage.createProgram` → `POST
  /api/v1/programs` → validation → service (one lock: capacity, uniqueness,
  insert) → `201 {program}` and an `ETag`. After a browser reload, the page
  calls `storage.listPrograms` → `GET /api/v1/programs` (snapshot pages) →
  open → `GET /api/v1/programs/{id}` with its `ETag` → edit (marked unsaved)
  → `PUT` with `If-Match` → either `200` with a new `ETag`, or `409` with a
  conflict panel and an explicit "Reload server copy" button.
- **Running a collection.** UI → `storage.getCollection` → the run logic
  freezes `{case id, name, source, expected}` for every case → each case in
  turn goes to `lambda3.interpret(source)` → `POST /lambda/rpc` on the studio
  host, which forwards it to Assign07's `POST /rpc` → the outcome is
  classified and compared → a row is recorded per case → the run moves to the
  next case even after a failure → a summary is shown.

## 4. Decisions

| # | Decision | Reason and evidence |
| --- | --- | --- |
| D1 | Flask 3.1.3 (Werkzeug 3.1.9) is the HTTP framework. | The instructor names it: Assign07.md, "Use Flask, FastAPI, or another instructor-approved Python web framework." Assign07 and Assign08 used it. |
| D2 | Python ≥ 3.12, tested with 3.14.10. The only extra dependency is `jsonschema` 4.26.0, used by the tests. | Assign09 requires 3.12+. The same `jsonschema` version validated Assign07's schema. |
| D3 | The client is a new small demonstration studio: plain HTML, CSS, and ES-module JavaScript, with no build step. | Assign03 produced requirements only, with no studio code. Assign08's client is an N-Queens animator. Assign09 allows "an equivalent small demonstration client". Assign08's injectable-`fetch` RPC client pattern is reused. |
| D4 | A small studio host serves the page and forwards `POST /lambda/rpc` unchanged to the Assign07 service. The database service sends CORS headers only for the configured studio origin, exposing `ETag` and allowing `If-Match`. | Observed on 2026-11-23: Assign07 answers the CORS preflight `OPTIONS /rpc` with `405` and sends no `Access-Control-Allow-Origin`, so a browser page cannot call it from another origin. Earlier assignments are not modified. The forwarder holds no LAMBDA logic and lives outside the database service, so the database stays free of execution. |
| D5 | Cases run through Assign07's `lambda.interpret`. `-32010` is the syntax category and `-32011` the type category. Every other outcome fails an error expectation: `-32012` timeout, `-32013` runtime error, `-326xx`, HTTP or transport failures. | Probed on the real service: `fact(6)` gives `{"type":"sint","value":"720"}`, `if then` gives `-32010`, `(lam (x: sint) => x)(true)` gives `-32011`, and `1 / 0` gives `-32013`. |
| D6 | Assign08's service is not used for execution. | It exposes only the fixed N-Queens solver and deliberately refuses arbitrary source, so it cannot run stored cases. |
| D7 | One lock in the in-memory store covers each operation from start to finish: existence, revision, uniqueness, and capacity checks, the mutation, and capturing the response. Flask runs threaded. No network calls happen in the database service. | This is the simplest model that makes mutations atomic under Flask's threaded server. |
| D8 | Stored records are immutable values (frozen dataclasses, cases as tuples). An update replaces a record. A list snapshot holds references to the captured values. | Returned and snapshotted data cannot be mutated through the store. A snapshot costs one reference per record rather than a deep copy. This avoids both slicing live data and storing IDs for later lookup. |
| D9 | The machine-readable contract is JSON Schema 2020-12 (`api.schema.json`), with one `$defs` entry per request and response body. Tests check the schema itself and validate every response against it. | Assign09 accepts JSON Schema for all bodies. It reuses the Assign07 tooling, with no extra validator package. |
| D10 | API tests use `unittest` with Flask's test client. Client tests use Node's built-in test runner (no npm packages). An integration test starts the real database service, studio host, and Assign07 service on free ports. | These are the same tools Assign07 and Assign08 used. Successful execution is only ever tested against the real LAMBDA3. |
| D11 | The Assign07 service is started from `../07` with its own documented command. The studio host takes `--lambda-url`, and the database service takes `--studio-origin`. | Instructions use relative paths and command options, never absolute paths. |
| D12 | Request validation runs before the store is consulted. Inside the lock the order is: existence → `If-Match` present → `If-Match` well formed → revision → uniqueness → capacity (API.md §9). | Assign09 requires only that a missing record wins over a missing or stale precondition. Validating first keeps the work under the lock small. |
| D13 | `If-Match` must be exactly one strong quoted revision. `*`, weak tags, lists, and unquoted values return `400 malformed_if_match` (API.md §5). | `*` would let a client overwrite a newer revision without seeing it, which is exactly what Assign09 forbids. |
| D14 | Limits: source 65,536 UTF-8 bytes (Assign07's own limit), names 100 characters, descriptions 1,000 characters, expected values 8,192 bytes, 500 programs, 100 collections, 100 cases per collection, pages 1–100 (default 50), 1 MiB bodies (API.md §4). | All five supplied LAMBDA3 libraries together are 21,603 bytes, so a test case can embed them. Any stored source can be sent to LAMBDA3 unchanged. |
| D15 | List snapshots expire 600 s after their last use. At most 100 are open; a new multi-page first page past that cap returns `409 capacity_limit` (`list_snapshots`), and valid snapshots are never evicted early. A list that fits in one page creates no snapshot (API.md §6). | This honours Assign09's promise that a cursor chain stays stable, while bounding memory. Snapshots share immutable record values (D8), so each costs one reference per record. |

## 5. Proposed file layout

```text
assigns/09/MySolution/
├── __init__.py
├── __main__.py          python -m MySolution: the database service
├── app.py               Flask app: thin routes, JSON/error normalization, CORS
├── validation.py        request bodies, query parameters, If-Match → checked input values
├── service.py           business rules: revisions, uniqueness, capacity, cases, list capture
├── store.py             small Storage interface and the in-memory backend (with lock)
├── models.py            immutable Program / Collection / Case records and their JSON form
├── pagination.py        snapshot registry and opaque cursor tokens
├── limits.py            the documented limits as one value
├── errors.py            ApiError and the stable error codes
├── studio/
│   ├── __main__.py      python -m MySolution.studio: static files + /lambda/rpc forwarder
│   └── static/          index.html, style.css, js/{storage,lambda3,runner,main}.js
├── tests/               test_unit_*.py: business rules without HTTP; test_*.py: HTTP suite
│                        (http_support.py, race_support.py); js/ adapter, runner, integration
├── API.md               the REST contract
├── api.schema.json      JSON Schema for all request and response bodies
├── DESIGN.md            this document
├── README.md            setup, commands, URLs, limits, examples
├── TESTING.md           requirement → test mapping and observed results
├── requirements.txt     pinned dependencies
└── .gitignore           .venv/, __pycache__/
```

Module names may be merged while the code is written if a split turns out to
be trivial. The boundaries stay the same: routes, validation, business rules,
and storage.

## 6. Requirement traceability

`API.md` cites every contract requirement (CON, VAL, DATA, REV, PAGE) in
brackets at the place that defines it.

| Requirement IDs | Delivered by | Verified by |
| --- | --- | --- |
| CON-1, CON-2 | `API.md`, `api.schema.json` | Schema self-check, validation of every API.md example body against its route's schema, and a route- and status-table cross-check against Assign09.md (`tests/test_schema.py`) |
| CON-3 … CON-12 | `app.py`, `errors.py` | `tests/test_transport.py`, `tests/test_failures.py`; error statuses in every HTTP test |
| VAL-1 … VAL-7 | `validation.py`, `limits.py` | `tests/test_unit_validation.py`; `tests/test_validation.py`, `tests/test_capacity.py`, `tests/test_pagination.py`, `tests/test_transport.py` (HTTP) |
| DATA-1 … DATA-11 | `models.py`, `service.py`, `store.py` | `tests/test_unit_service.py`; `tests/test_programs.py`, `tests/test_collections.py`, `tests/test_cases.py`, `tests/test_validation.py` (uniqueness) (HTTP) |
| DATA-12, DATA-13 | `store.py`; absence of LAMBDA imports; README and studio banner | Restart test in the integration suite; code inspection; UI check |
| REV-1 … REV-5 | `service.py`, `store.py`, `validation.py` | `tests/test_unit_service.py`; `tests/test_revisions.py`, and unchanged-after-failure checks in `tests/test_validation.py`, `tests/test_capacity.py`, `tests/test_failures.py` (HTTP) |
| REV-6 | `store.py` lock | `tests/test_unit_concurrency.py`; `tests/test_concurrency.py` (threaded HTTP server, barrier-synchronized requests) |
| PAGE-1 … PAGE-6 | `pagination.py`, `service.py` | `tests/test_unit_pagination.py`; `tests/test_pagination.py`, `tests/test_capacity.py` (snapshot cap) (HTTP) |
| STU-1 … STU-9 | `studio/static/js/*`, `studio/__main__.py` | `tests/js/*.test.mjs` (adapter and runner); integration test with real LAMBDA3; browser demonstration |
| DOC-1 … DOC-6 | `README.md`, `TESTING.md`, diagram, file inventory | Following the README from a clean state; Git status/inventory review |

## 7. Storage, concurrency, and snapshots

### Layers

| Module | Responsibility | Does not |
| --- | --- | --- |
| `validation.py` | Turns a decoded JSON body, query parameters, and `If-Match` into checked values (`ProgramFields`, `PageRequest`, `IfMatch`, …), or raises the first `invalid_request`. | Touch the store. A failed validation therefore cannot change state. |
| `service.py` | The business rules: existence, preconditions, uniqueness, capacity, revisions, timestamps, IDs, case order, and capturing lists. | Know about HTTP, or look inside LAMBDA source or expectations. |
| `store.py` | The `Storage` interface (keep, find, list, count, `transaction()`) and `InMemoryStore`, which is two dictionaries and one lock. | Enforce any rule. Another backend would only need to implement `Storage`. |
| `pagination.py` | `SnapshotRegistry`: snapshots, cursors, the idle lifetime, and the snapshot cap. | Read the store. It receives an already-captured tuple. |
| `models.py` | The immutable records and their JSON form. | Hold any mutable state. |

### Synchronization

Flask's development server runs each request in its own thread (D7). Every
service operation that reads or changes records is one
`with store.transaction():` block. Inside it, in order:

1. existence of the record, then of the case;
2. `If-Match` present, well formed, and current;
3. name uniqueness;
4. capacity;
5. the change;
6. returning the new immutable record.

That record is the captured response: turning it into JSON happens after the
lock is released, and nothing can change it in the meantime. The store lock
is a plain `threading.Lock`. It is never held while waiting on I/O, and the
service makes no network calls at all.

The snapshot registry has its own lock. A first page is captured under the
store lock (`all_programs()` builds the tuple at a single instant) and then
registered under the registry lock. The two locks are never held together,
so they cannot deadlock.

### Immutability and copy isolation

- Records are frozen dataclasses, and a collection's cases are a tuple. An
  update builds a new value with `dataclasses.replace`.
- A value that has been returned, or captured in a snapshot, can never
  change. The tests check that assigning to one raises `FrozenInstanceError`.
- The `*_json` functions build new dictionaries on every call, so changing a
  response dictionary cannot reach stored state.
- A snapshot is a tuple of references, never a copy.

### Costs

These are by inspection; no benchmarks were needed.

- **Record operations.** Get, save, and delete are O(1) dictionary operations.
  A dictionary keeps insertion order, and assigning to an existing key keeps
  its position, so creation order needs no sequence numbers.
- **Name uniqueness** is a linear scan, at most 500 programs, 100 collections,
  or 100 cases. A name index would be faster, but it is a second structure
  to keep consistent on every rename and delete, which these sizes don't
  justify.
- **Case operations** (add, replace, delete) rebuild the case tuple: O(k) with
  k ≤ 100, inside the lock.
- **A first list page** builds one tuple of at most 500 references under the
  lock. Later pages slice the snapshot in O(limit) and do not take the store
  lock.
- **Snapshot memory** is one reference per captured record. Record values that
  have since been updated or deleted stay alive only while a snapshot refers
  to them, that is, at most 600 s after the snapshot's last use, with at most
  100 snapshots. Expired snapshots are removed oldest-used first, stopping at
  the first live one.

### Evidence

`tests/test_unit_*.py` (76 tests) check these invariants:

- revision increments;
- the precondition order, including a missing record winning;
- uniqueness scopes and renames;
- capacities;
- no change after any failure;
- the ordered case lifecycle;
- cascade deletion;
- program/case independence;
- immutable and detached records;
- snapshot stability, expiry, and the cap;
- concurrent same-revision updates, case appends, same-name creates, and
  capacity.

The concurrency tests use a `RendezvousStore` that makes the first two
readers of a record wait for each other. With the lock in place that wait
times out harmlessly. Without the lock, both threads would read the same
revision. A deliberate removal of the lock was detected this way.
`tests/test_concurrency.py` repeats the same-revision races through a real
threaded Werkzeug server, with the same store, and detects the same removal
through HTTP alone.
