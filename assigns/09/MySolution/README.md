# LAMBDA-studio In-Memory Database Service (Assign09)

This assignment has two parts:

- **A REST service** that keeps LAMBDA-studio's named programs and test
  collections in memory.
- **A small browser studio** that saves programs, organizes test cases, and
  runs them through the Assign07 LAMBDA3 service.

> **Saved data lives only in memory.** Programs and collections survive
> browser reloads and new tabs while the database service is running. They
> are erased when that process stops or restarts. Nothing is written to files,
> SQLite, or browser storage. The studio repeats this warning at the top of
> the page.

Other documents in this folder:

| File | What it holds |
| --- | --- |
| [`API.md`](API.md) | The REST contract: routes, fields, limits, revisions, lists, errors, and worked examples |
| [`api.schema.json`](api.schema.json) | JSON Schema for every request and response body |
| [`DESIGN.md`](DESIGN.md) | Requirements (IDs such as CON-1 and STU-5), design decisions, and the storage and concurrency design |
| [`TESTING.md`](TESTING.md) | The tests for each requirement, and the observed results of the runs and the demonstration |

## Contents

1. [Architecture](#architecture)
2. [Requirements](#requirements)
3. [Setup](#setup)
4. [Starting the services](#starting-the-services)
5. [Using the studio](#using-the-studio)
6. [How outcomes are compared](#how-outcomes-are-compared)
7. [A short tour of the studio](#a-short-tour-of-the-studio)
8. [REST API examples](#rest-api-examples)
9. [Limits](#limits)
10. [Running the tests](#running-the-tests)
11. [Files](#files)
12. [Troubleshooting](#troubleshooting)

## Architecture

The solution runs as three local processes.

- **Database service:** stores data only. It never parses, type-checks, or
  runs LAMBDA source.
- **LAMBDA3 service:** the only process that parses, type-checks, or runs
  LAMBDA source.
- **Studio host:** serves the page and passes the page's LAMBDA3 requests on
  to the LAMBDA3 service.

```text
 Browser: the LAMBDA-studio page, served by the studio host
 ┌──────────────────────────────────────────────────────────────┐
 │ UI (main.js): programs, collections, run results             │
 │      │                                 │                     │
 │      ▼                                 ▼                     │
 │ storage adapter (storage.js)     run logic (runner.js)       │
 │ every REST detail: URLs,         snapshots, comparison,      │
 │ bodies, cursors, errors,         summary                     │
 │ ETag and If-Match                      │                     │
 │      │                                 ▼                     │
 │      │                           LAMBDA3 client (lambda3.js) │
 └──────┼─────────────────────────────────┼─────────────────────┘
        │ REST over HTTP, JSON            │ JSON-RPC 2.0, same origin
        │ (cross-origin, CORS)            │
        ▼                                 ▼
 ┌─────────────────────────────┐   ┌──────────────────────────────┐
 │ Database service      :8009 │   │ Studio host            :8010 │
 │ python -m MySolution        │   │ python -m MySolution.studio  │
 │                             │   │                              │
 │ REST API /api/v1  (app.py)  │   │ serves the page and          │
 │   ▼                         │   │ /config.json; forwards       │
 │ validation (validation.py)  │   │ POST /lambda/rpc unchanged   │
 │   ▼                         │   │ (no data, no LAMBDA code)    │
 │ business rules (service.py) │   └──────────────┬───────────────┘
 │   ▼                         │                  │
 │ in-memory store (store.py)  │                  ▼
 │                             │   ┌──────────────────────────────┐
 │ stores data only: no LAMBDA │   │ LAMBDA3 service        :8000 │
 │ code, no files, no SQLite   │   │ Assign07, unchanged          │
 └─────────────────────────────┘   │ POST /rpc: parse, type-check,│
                                   │ interpret                    │
                                   └──────────────────────────────┘
```

- **Running a collection.** The run logic first reads the collection through
  the storage adapter. It then sends each case to LAMBDA3 by way of the studio
  host.
- **Why the studio host exists.** The Assign07 service does not answer a
  browser's cross-origin preflight. The studio host therefore serves the page
  and forwards its `POST /lambda/rpc` body to Assign07 unchanged. The host has
  no data and loads no database code (DESIGN.md D4).
- **Who may call the database.** The database service accepts cross-origin
  calls only from the studio's address. By default that is
  `http://127.0.0.1:8010` and `http://localhost:8010`.

## Requirements

- **Python 3.12 or later.** Tested with Python 3.14.10 on macOS.
- **Python packages:**
  - Flask 3.1.3, with Werkzeug 3.1.9.
  - jsonschema 4.26.0, used by the tests only.

  These and their dependencies are pinned in
  [`requirements.txt`](requirements.txt).
- **The Assign07 LAMBDA3 service.** It is in this same repository, in
  `assigns/07`, and uses the supplied LAMBDA3 implementation in
  `assigns/07/LAMBDA3`. Assign09 does not change it.
- **A current web browser.** Tested with Google Chrome 158.
- **For the studio tests only:** Node 18 or later (tested with 26.13.1) and
  Google Chrome.
- **`curl`**, for the examples.

## Setup

From the repository root, set up this service:

```sh
cd assigns/09
python3 -m venv MySolution/.venv
MySolution/.venv/bin/python -m pip install -r MySolution/requirements.txt
```

Then set up the Assign07 LAMBDA3 service in its own folder, with its own
virtual environment. Its own `README.md` describes it in full.

```sh
cd ../07
python3 -m venv MySolution/.venv
MySolution/.venv/bin/python -m pip install -r MySolution/requirements.txt
cd ../09
```

If `python3 --version` shows a version older than 3.12, create the virtual
environments with a newer interpreter, for example
`python3.14 -m venv MySolution/.venv`.

On Windows (not tested), use `py -3.14 -m venv MySolution\.venv`. Then type
`MySolution\.venv\Scripts\python` wherever this README says
`MySolution/.venv/bin/python`.

The commands in the rest of this README run from `assigns/09`, unless a
command block starts by changing directory.

## Starting the services

Use three terminals and leave each command running. The `-B` flag stops
Python from writing `__pycache__` folders into the solution.

**1. The LAMBDA3 service (Assign07),** from `assigns/07`:

```sh
cd ../07
MySolution/.venv/bin/python -B -m MySolution
```

It is ready when it prints `Running on http://127.0.0.1:8000`.

**2. The database service,** from `assigns/09`:

```sh
MySolution/.venv/bin/python -B -m MySolution
```

When it starts, it logs the API address and the studio addresses it allows.
It then logs `Records are kept in process memory only and are lost when this
process stops.` and finally `Running on http://127.0.0.1:8009`.

**3. The studio host,** from `assigns/09`:

```sh
MySolution/.venv/bin/python -B -m MySolution.studio
```

It is ready when it prints `Running on http://127.0.0.1:8010`.

**4. Open http://127.0.0.1:8010/ in a browser.** Two chips at the top should
read `Database: connected` and `LAMBDA3: connected`. They are checked when
the page loads, so if you start a service later, reload the page.

To stop a service, press Ctrl-C in its terminal. Stopping the database service
erases all saved programs and collections. Stopping the studio host or
LAMBDA3 erases nothing.

### Service URLs

| What | URL |
| --- | --- |
| Studio page | http://127.0.0.1:8010/ or http://localhost:8010/ |
| Database REST API | http://127.0.0.1:8009/api/v1 (for example `GET /api/v1/health`) |
| LAMBDA3 JSON-RPC (Assign07) | http://127.0.0.1:8000/rpc. The page reaches it through the studio host at http://127.0.0.1:8010/lambda/rpc |
| Studio configuration | http://127.0.0.1:8010/config.json, which tells the page where the database is |

### Options

| Command | Option | Default |
| --- | --- | --- |
| `python -m MySolution` (database) | `--host` | `127.0.0.1` |
| | `--port` | `8009` |
| | `--studio-origin ORIGIN` | `http://127.0.0.1:8010` and `http://localhost:8010`. Repeat the option for several origins; the values replace the defaults. |
| `python -m MySolution.studio` (studio host) | `--host` | `127.0.0.1` |
| | `--port` | `8010` |
| | `--database-url` | `http://127.0.0.1:8009/api/v1` (the address as the browser reaches it) |
| | `--lambda-url` | `http://127.0.0.1:8000/rpc` |
| | `--lambda-timeout` | `10` seconds for each LAMBDA3 answer |
| `python -m MySolution` in `assigns/07` (LAMBDA3) | `--port` | `8000`. Its README lists its other options. |

The demonstration in `TESTING.md` ran everything on other ports, like this:

```sh
# in assigns/07
MySolution/.venv/bin/python -B -m MySolution --port 18000
# in assigns/09, two terminals
MySolution/.venv/bin/python -B -m MySolution --port 18009 --studio-origin http://127.0.0.1:18010
MySolution/.venv/bin/python -B -m MySolution.studio --port 18010 \
  --database-url http://127.0.0.1:18009/api/v1 --lambda-url http://127.0.0.1:18000/rpc
```

Open the page only at an address the database service allows, such as
http://127.0.0.1:18010/ in this example. From any other address the browser
blocks the database calls. The page then shows `Database: unreachable` and
`Cannot reach the database service at …`.

## Using the studio

Below the header, a banner warns that saved work is temporary. The two tabs
are **Programs** and **Test collections**.

### Programs

- **Create:** click **New program**, then enter a name, an optional
  description, and the source. Click **Save**. Saved programs are listed on the
  left; click one to open it.
- **Unsaved changes:** this marker appears next to the title whenever the
  editor differs from the copy last saved or loaded. If you leave the page
  with unsaved edits, the browser asks you to confirm.
- **Run in LAMBDA3:** runs the editor's current text, saved or not, and shows
  the value and type, or the error.
- **Reload from server:** replaces the editor with the server's copy. If you
  have unsaved edits, it asks you to confirm first. Your version stays visible
  under **Your unsaved version, kept after reloading**.
- **Delete:** removes the program. Test cases never depend on a program,
  because each case keeps its own copy of the source.

### Conflicts

Suppose the program was saved somewhere else, such as another tab, after you
opened it. Then **Save** is refused, and the studio does three things:

- A panel shows your revision and the server's.
- Your edits stay in the editor.
- Nothing is retried automatically.

You then choose one of two buttons:

- **Reload server copy** loads the newer version. Your version stays below so
  that you can copy from it, and you can then save again.
- **Keep editing** closes the panel.

Collections behave the same way. A change to a collection, its name, or any
of its cases is refused if another tab has changed the collection since you
loaded it. In that case, **Reload collection** fetches the current copy.

### Test collections

- **Create a collection:** use the form on the left. The new collection opens
  straight away. To open a collection later, click it in the list.
- **Add a case:** enter a name and the source. The **Copy the program
  editor's source** button copies the source from the Programs tab. Choose the
  expected outcome:
  - **A value,** written exactly as LAMBDA3 formats it, such as `720` or
    `true`;
  - **A syntax error;**
  - **A type error.**

  An optional description can be added. Then click **Add case**.
- **Order:** cases run in the order listed.
- **Edit or delete a case:** use the buttons next to it.
- **Name and description:** **Save name and description** changes the
  collection's own name and description.
- **Reload collection:** fetches the server's copy. Text typed into the case
  form is kept.

### Running a collection

**Run all cases** reads the collection from the database, then sends each case
to LAMBDA3, one at a time.

- **Results:** each row shows the case, its expectation, the actual outcome,
  and PASS or FAIL. A failing case does not stop the run.
- **Summary:** a line at the top gives the totals, for example `3 of 5
  passed, 2 failed`.
- **The cases as they were:** rows describe each case as it was when the run
  started. A case edited after that is marked `edited since this run`.
- **Only saved cases run.** Text in the case form that has not been added is
  not part of the run.

## How outcomes are compared

The database service only stores expectations; the studio's run logic
(`studio/static/js/runner.js`) compares them with LAMBDA3's answers.

| Expected outcome | The case passes only when |
| --- | --- |
| A value, such as `720` | LAMBDA3 runs the source successfully, and its formatted value is exactly the expected text: the same characters, with nothing trimmed. The type LAMBDA3 reports (shown as `720 : sint`) is displayed but not compared. |
| A syntax error | LAMBDA3 answers with its syntax-error code, `-32010`. |
| A type error | LAMBDA3 answers with its type-error code, `-32011`. |

Everything else is a FAIL, whatever was expected:

- a runtime error (`-32013`, for example `1 / 0`);
- LAMBDA3's 2-second deadline (`-32012`);
- invalid parameters (`-32602`);
- an internal LAMBDA3 error (`-32603`), or any other JSON-RPC error;
- a transport failure:
  - LAMBDA3 is not running (the studio host answers `502`);
  - LAMBDA3 sends no answer within `--lambda-timeout` (`504`);
  - the studio host cannot be reached.

## A short tour of the studio

With the three services running and the page open:

1. **Save and reload a program.**
   1. On **Programs**, click **New program** and name it `factorial`.
   2. Enter this source, then click **Save**:
      ```
      let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end
      ```
   3. Click **Run in LAMBDA3**. It shows `720 : sint`.
   4. Reload the browser page. The program is still listed; open it.
2. **See a conflict.**
   1. Open the same program in a second tab.
   2. Change and save it in one tab.
   3. Change and save it in the other tab. The save is refused and the
      conflict panel appears.
   4. Click **Reload server copy**, then save again.
3. **Run a test collection.** On **Test collections**, create `demo` and add
   these cases:

   | Case name | Source | Expected outcome |
   | --- | --- | --- |
   | factorial | **Copy the program editor's source** | A value: `720` |
   | bad syntax | `if then` | A syntax error |
   | bad argument | `(lam (x: sint) => x)(true)` | A type error |
   | wrong on purpose | `6 * 7` | A value: `41` |
   | runtime error | `1 / 0` | A syntax error |

   Click **Run all cases**. The summary reads `3 of 5 passed, 2 failed`.
   `wrong on purpose` fails because LAMBDA3 gives `42`. `runtime error` fails
   because a runtime error is never a syntax or type error.
4. **See that data lives only in memory.**
   1. Press Ctrl-C in the database terminal. Reloading the page now shows
      `Database: unreachable`.
   2. Start the database service again and reload. The programs and
      collections are gone.
5. **Take LAMBDA3 away.** Stop the LAMBDA3 service and run a collection.
   Every case is still attempted, and each fails with `LAMBDA3 unavailable:
   HTTP 502`. Saved data is unaffected.

The browser checks in `tests/browser/studio_flows.mjs` perform the same steps
automatically against the real services (see [Running the tests](#running-the-tests)).

## REST API examples

These were run against a fresh database service. The `curl -i` output is
trimmed to the headers that matter. IDs and times will differ.

```sh
API=http://127.0.0.1:8009/api/v1
JSON='Content-Type: application/json'
```

**Health.**

```sh
curl -s $API/health
```
```json
{"status": "ok", "version": "1.0"}
```

**Save a program.** The response gives revision 1 in `ETag`.

```sh
curl -s -i -X POST $API/programs -H "$JSON" -d '{"name": "answer", "source": "6 * 7"}'
```
```text
HTTP/1.1 201 CREATED
Content-Type: application/json
ETag: "1"
Location: /api/v1/programs/prg_ZiNtbNjBNh43NO4T

{"program": {"id": "prg_ZiNtbNjBNh43NO4T", "name": "answer", "source": "6 * 7", "description": "", "created_at": "2026-11-27T07:52:40.257Z", "updated_at": "2026-11-27T07:52:40.257Z", "revision": 1}}
```

**Read it back,** with the ID from your own response:

```sh
ID=prg_ZiNtbNjBNh43NO4T
curl -s -i $API/programs/$ID
```
```text
HTTP/1.1 200 OK
ETag: "1"

{"program": {"id": "prg_ZiNtbNjBNh43NO4T", "name": "answer", "source": "6 * 7", "description": "", ..., "revision": 1}}
```

**Update it.** Send the current revision in `If-Match`:

```sh
curl -s -i -X PUT $API/programs/$ID -H "$JSON" -H 'If-Match: "1"' \
  -d '{"name": "answer", "source": "6 * 7", "description": "the answer"}'
```
```text
HTTP/1.1 200 OK
ETag: "2"

{"program": {..., "description": "the answer", ..., "revision": 2}}
```

**Send the same stale revision again.** The update is refused and the program
is not changed:

```sh
curl -s -i -X PUT $API/programs/$ID -H "$JSON" -H 'If-Match: "1"' -d '{"name": "answer", "source": "6 * 8"}'
```
```text
HTTP/1.1 409 CONFLICT

{"error": {"code": "revision_conflict", "message": "If-Match \"1\" is stale; the program is at revision 2.", "current_revision": 2}}
```

**Create a collection and add a case.** A case change uses the collection's
`ETag`.

```sh
curl -s -i -X POST $API/collections -H "$JSON" -d '{"name": "demo"}'
CID=col_oYlS1EdMbgdUlk_A        # the ID from the response
curl -s -i -X POST $API/collections/$CID/cases -H "$JSON" -H 'If-Match: "1"' \
  -d '{"name": "answer", "source": "6 * 7", "expected": {"kind": "value", "value": "42"}}'
```
```text
HTTP/1.1 201 CREATED
ETag: "2"

{"collection": {"id": "col_oYlS1EdMbgdUlk_A", "name": "demo", "description": "", ..., "revision": 2, "cases": [{"id": "case_4QhXwU_PERcVH7jV", "name": "answer", "source": "6 * 7", "expected": {"kind": "value", "value": "42"}, "description": ""}]}}
```

**List programs, then send an invalid parameter.**

```sh
curl -s "$API/programs?limit=10"
curl -s "$API/programs?limit=0"
```
```json
{"items": [{"id": "prg_ZiNtbNjBNh43NO4T", "name": "answer", ..., "revision": 2}], "next_cursor": null}
{"error": {"code": "invalid_request", "message": "limit must be a whole number from 1 to 100.", "field": "limit", "reason": "out_of_range", "limit": 100}}
```

**Delete the program.** Without `If-Match`, the service answers
`428 precondition_required`. With the current revision:

```sh
curl -s -i -X DELETE $API/programs/$ID -H 'If-Match: "2"'
```
```text
HTTP/1.1 204 NO CONTENT
```

**Run LAMBDA3 through the studio host,** the same way the page does:

```sh
curl -s -X POST http://127.0.0.1:8010/lambda/rpc -H "$JSON" \
  -d '{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "6 * 7"}, "id": 1}'
```
```json
{"jsonrpc": "2.0", "result": {"type": "sint", "value": "42"}, "id": 1}
```

With `"source": "if then"`, the answer is instead:

```json
{"jsonrpc": "2.0", "error": {"code": -32010, "message": "LAMBDA syntax error", "data": {"diagnostic": "Expected an expression", "line": 1, "column": 4}}, "id": 2}
```

[`API.md`](API.md) §11 has complete request and response examples for every
route.

## Limits

[`API.md`](API.md) §4 gives the full rules. Exceeding a limit returns the error
shown.

| Limit | Value | Error |
| --- | --- | --- |
| HTTP request body | 1,048,576 bytes | `413 payload_too_large` |
| Name, after trimming | 1–100 characters | `400 invalid_request` |
| Source | 1–65,536 UTF-8 bytes (Assign07's own limit) | `400 invalid_request` |
| Description | 0–1,000 characters | `400 invalid_request` |
| Expected value | 0–8,192 UTF-8 bytes | `400 invalid_request` |
| Programs | 500 | `409 capacity_limit` |
| Collections | 100 | `409 capacity_limit` |
| Cases per collection | 100 | `409 capacity_limit` |
| Page size (`limit`) | 1–100, default 50 | `400 invalid_request` |
| Open list snapshots | 100, each expiring 600 s after its last use | `409 capacity_limit` |

The studio host refuses a LAMBDA3 request body over 1,048,576 bytes and a
reply over 16 MiB. It waits `--lambda-timeout` seconds (default 10) for each
answer. LAMBDA3 itself stops every evaluation after 2 seconds.

## Running the tests

[`TESTING.md`](TESTING.md) records the results and maps every requirement to
its tests. None of the suites use the default ports, so they can run while
your own services are up.

**Python** (204 tests, about 5 seconds):

```sh
MySolution/.venv/bin/python -B -m unittest discover -s MySolution/tests -t .
```

- **The API tests** go through Flask's test client and need no running
  server.
- **`test_concurrency.py`** starts a real threaded server on a free port.
- **`test_studio_host.py`** starts the real Assign07 service from `../07`,
  using that assignment's virtual environment, also on a free port. If that
  environment is missing, those four tests are skipped and the reason is
  printed.

**Studio modules** (25 tests; Node 18 or later, no packages):

```sh
node --test MySolution/tests/js/*.test.mjs
```

**Studio flows in headless Chrome** (18 checks, under 10 seconds):

```sh
node MySolution/tests/browser/studio_flows.mjs
```

- **What it does:** it starts its own LAMBDA3 service, database service, and
  studio host on free ports. It then drives the page through every flow in the
  tour above, plus error cases.
- **What it prints:** one PASS or FAIL line per check, and the path of a
  temporary folder with the service logs and screenshots.
- **Settings:** set `CHROME` if Chrome is not installed in its usual macOS
  location. Set `PYTHON` or `LAMBDA_PYTHON` to use interpreters other than the
  two virtual environments.

## Files

| Path | Contents |
| --- | --- |
| `__main__.py` | `python -m MySolution`: command-line options and startup |
| `app.py` | HTTP routes, JSON decoding, headers, CORS, and error responses |
| `validation.py`, `limits.py` | Request validation and the documented limits |
| `service.py` | Business rules: uniqueness, revisions, capacity |
| `store.py`, `models.py`, `pagination.py` | The in-memory store, immutable records, and list snapshots |
| `errors.py` | The stable error codes |
| `studio/host.py`, `studio/__main__.py` | The studio host: the page, `/config.json`, and the LAMBDA3 forwarder |
| `studio/static/` | The page: `index.html`, `style.css`, and `js/` (`storage.js`, `lambda3.js`, `runner.js`, `main.js`) |
| `tests/` | Python unit and HTTP tests, `js/` Node tests, and `browser/` studio flows |
| `requirements.txt` | Pinned Python dependencies |

[`DESIGN.md`](DESIGN.md) §5 describes the layout in more detail.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| `Address already in use` when starting a service | Another process holds the port. Stop it, or choose other ports with the options above. |
| `Database: unreachable`, or `Cannot reach the database service at …` | Start the database service. Then check that the page's address is one the database allows (`--studio-origin`) and that `--database-url` points at the service. |
| `LAMBDA3: unreachable`, or cases fail with `LAMBDA3 unavailable: HTTP 502` | Start the Assign07 service, or correct `--lambda-url`. |
| Saved programs disappeared | The database service was restarted. Its data lives in memory only. |
