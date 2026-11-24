# Animated N-Queens search with CPS and lazy streams

A local web application that animates a depth-first N-Queens search one event
at a time. The search is written in LAMBDA3 in continuation-passing style
([`solver.lam`](solver.lam)), and its trace is a lazy stream: the server
computes an event only when the browser asks for it, through a small
JSON-RPC 2.0 service.

- How it works: [DESIGN.md](DESIGN.md) (architecture diagram, solver
  invariant, continuations, laziness, stream lifecycle, RPC contract, client).
- What is tested and the observed results: [TESTING.md](TESTING.md).
- How AI was used: [AI-TRANSCRIPT.md](AI-TRANSCRIPT.md).

## Requirements

- **Python 3.12 or later**, because the supplied `LAMBDA3/lambda3.py` uses
  `type` statements. Tested with Python 3.14.10.
- **Flask 3.1.3**, pinned with its dependencies in
  [`requirements.txt`](requirements.txt). Nothing else is installed.
- **Node.js** for the client tests only, using its built-in test runner (no
  npm packages). Tested with Node 26.13.1.
- **Google Chrome** for the optional automated browser checklist only.
  Tested with Chrome 158.

Everything was tested on macOS 27 (Apple silicon). Other systems were not
tested.

## Setup

Run every command in this README from `assigns/08/`. The solution uses the
interpreter in `assigns/08/LAMBDA3/` and checks at startup that it is that
copy.

```sh
python3 -m venv MySolution/.venv
MySolution/.venv/bin/python -m pip install -r MySolution/requirements.txt
```

If `python3 --version` reports a version older than 3.12, create the virtual
environment with a newer interpreter, for example `python3.14 -m venv
MySolution/.venv`. Git ignores `MySolution/.venv/` and Python caches.

## Run

```sh
MySolution/.venv/bin/python -m MySolution
```

Then open **http://127.0.0.1:8000/**. The JSON-RPC endpoint is
`http://127.0.0.1:8000/rpc`. Stop the server with Ctrl+C.

| Option | Default | Meaning |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Interface to bind. The default accepts local connections only. |
| `--port` | `8000` | TCP port. |
| `--stream-ttl` | `300` | Seconds an unused stream stays open before it expires. |

The server prints one access-log line per request.

## Test

```sh
MySolution/.venv/bin/python -B -m unittest discover -s MySolution/tests -t . -v
node --test MySolution/tests/js/
node MySolution/tests/browser/checklist.mjs
```

1. The **Python suite** (79 tests, about 50 seconds) checks the solver, its
   laziness, the adapter, the stream table, and the JSON-RPC service over
   HTTP, including a complete 8×8 run through a real local server. Most of
   the time is the interpreter exhausting the 8×8 search twice.
2. The **client suite** (17 tests, under a second) checks playback, the
   controls' request behavior, stale responses, errors and the JSON-RPC
   client.
3. The **browser checklist** (about 15 seconds) starts the server, opens the
   page in headless Chrome, and works through the checklist in
   [TESTING.md section 2](TESTING.md#2-browser-checklist) by clicking the
   page's controls. It uses `MySolution/.venv/bin/python`; set `PYTHON` or
   `CHROME` to use other paths. Its server log and screenshots go to a
   temporary folder, whose path it prints.

`-B` stops Python from writing `__pycache__` folders into the instructor's
`LAMBDA3/` directory.

## Using the page

**Start** opens a new search and plays it. **Step** shows exactly one event.
**Play/Pause** runs or stops the animation at the speed set by the slider.
**Next solution** jumps to the next solution, or to the end of the search.
**Reset** stops and clears everything. The keys S, P, N and R do the same as
Step, Play/Pause, Next solution and Reset. The board size can be set from
4×4 to 10×10 (8×8 by default), and "Pause at each solution" stops playback on
every solution.

| On the board | Meaning |
| --- | --- |
| Ochre queen in an ochre ring | The candidate being tried (`try`). |
| Green queen | The candidate was safe and is placed (`place`). |
| Red ✕, with a dashed red line to an outlined queen | The candidate is rejected; the line runs to the queen that attacks it, and the status line says whether they share a column or a diagonal (`reject`). |
| Violet ↩ | A queen was removed because its branch is finished (`backtrack`). |
| Gold border and "Solution k" banner | A complete solution (`solution`). |
| Blue border and "Search complete" banner | The search is finished (`done`). |

The highlighted row number is the row being searched. It moves down as queens
are placed and back up on a backtrack.

Playback requests events only as it needs them: Step and Play ask for one
event at a time, and Next solution asks for batches of 32, keeping any events
after the solution for later. A network or RPC failure stops playback and
shows a message; **Restart** starts over.

## JSON-RPC API

One endpoint, `POST /rpc`, with `Content-Type: application/json`. Calls and
JSON-RPC errors are answered with HTTP 200; notifications (requests without
an `id`) with an empty HTTP 204. Batches are not supported.

| Method | Params | Result |
| --- | --- | --- |
| `service.health` | none, or `{}` | `{"status": "ok", "version": "1.0"}` |
| `queens.open` | `{"size": n}`, an integer from 4 to 10 | `{"stream_id": "<uuid>", "size": n}` |
| `queens.next` | `{"stream_id": s, "limit": k}`, `k` an integer from 1 to 32 | `{"events": [ … at most k … ], "done": bool}` |
| `queens.close` | `{"stream_id": s}` | `{"closed": true}` |

With the server running:

```sh
curl -s http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "service.health", "params": {}, "id": 1}'
# {"jsonrpc": "2.0", "result": {"status": "ok", "version": "1.0"}, "id": 1}

curl -s http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "queens.open", "params": {"size": 8}, "id": 2}'
# {"jsonrpc": "2.0", "result": {"stream_id": "<a new UUID>", "size": 8}, "id": 2}
```

Copy the `stream_id` from that answer into `ID`:

```sh
ID=paste-the-stream-id-here
curl -s http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "queens.next", "params": {"stream_id": "'$ID'", "limit": 3}, "id": 3}'
# {"jsonrpc": "2.0", "result": {"events": [{"event": "try", "column": 0, "row": 0, "board": []}, {"event": "place", "column": 0, "row": 0, "board": [0]}, {"event": "try", "column": 0, "row": 1, "board": [0]}], "done": false}, "id": 3}

curl -s http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "queens.close", "params": {"stream_id": "'$ID'"}, "id": 4}'
# {"jsonrpc": "2.0", "result": {"closed": true}, "id": 4}
```

Events are JSON objects. Boards list the queen's column for each filled row,
in row order, and rows and columns start at 0.

| `event` | Other fields | Board |
| --- | --- | --- |
| `try` | `column`, `row`, `board` | Before the candidate is considered. |
| `place` | `column`, `row`, `board` | After the safe candidate is added. |
| `reject` | `column`, `row`, `board` | Unchanged; the candidate is attacked. |
| `backtrack` | `column`, `row`, `board` | Restored, after removing the queen at (`row`, `column`). |
| `solution` | `board` | A complete solution. |
| `done` | none | The last event, exactly once. |

The 8×8 stream has 33,589 events, among them 92 solutions in lexicographic
order; the first solution, `[0, 4, 7, 5, 2, 6, 1, 3]`, is event 1,858. More
exchanges, including the end of a stream and errors, are in
[DESIGN.md section 7.6](DESIGN.md#76-example-exchanges).

### Errors

| Code | Message | When |
| --- | --- | --- |
| `-32700` | Parse error | The body is not valid UTF-8 JSON. |
| `-32600` | Invalid Request | The envelope is malformed, or the body is a batch. |
| `-32601` | Method not found | Any method other than the four above. |
| `-32602` | Invalid params | Missing, extra or wrongly typed params; `data` names the field and the reason. Booleans, `8.0` and `"8"` are not integers. |
| `-32603` | Internal error | An unexpected failure; `data` holds only an incident ID, and the details go to the server log. |
| `-32020` | Stream not found | The stream ID is unknown, closed or expired. |
| `-32021` | Too many open streams | 64 streams are already open. |

A wrong `Content-Type` gets HTTP 415, another HTTP method on `/rpc` gets 405,
and a body over 64 KiB gets 413, each with a short plain-text body.

### Stream lifecycle

- `queens.open` builds the search without running it; `queens.next` computes
  at most `limit` events and never the one after them.
- The response that contains `done` sets `"done": true`. The server then
  drops the solver state and keeps a small record, so later `queens.next`
  calls return `{"events": [], "done": true}`.
- A stream expires after 300 seconds without `queens.open` or `queens.next`
  activity (`--stream-ttl`). Expired streams are removed at the next request.
  `queens.close` removes a stream at once.
- All state is in memory, so restarting the server invalidates every stream
  ID.

## Files

| Path | Contents |
| --- | --- |
| `solver.lam` | The LAMBDA3 solver: CPS search, CPS safety check, pure board and event helpers, lazy stream. |
| `lambda_adapter.py` | Loads and type-checks `solver.lam`, opens streams, forces cells with LAMBDA3's own `lazy_eval`, converts events to JSON. |
| `streams.py` | The stream table: IDs, lazy cursors, locking, expiry, exhausted records. |
| `methods.py` | The four methods and their parameter checks. |
| `rpc.py`, `errors.py` | JSON-RPC decoding, envelope checks, dispatch, error objects. |
| `app.py`, `__main__.py` | The Flask app (`POST /rpc`, the page and its files) and the command line. |
| `static/` | The page: `index.html`, `style.css`, and the modules in `static/js/`. |
| `tests/` | Python tests, client tests in `tests/js/`, and the browser checklist in `tests/browser/`. |

## Reuse and attribution

- `app.py`, `rpc.py` and `errors.py` are adapted from my Assignment 07
  service. The kept parts are strict JSON decoding, envelope checks,
  dispatch, incident-ID internal errors, the media-type check and 204
  handling. The `lambda.*` methods and worker processes were removed, batches
  are refused, and the stream errors and static files were added.
- The safety check walks a newest-first board with distance 1, 2, …, an idea
  taken from the instructor's `LAMBDA3/mytest/eight_queens.lam`. Its
  direct-style search and one-queen-per-column board are not used.
  `eight_queens_stream.lam` is not reused.
- The empty stream has the shape of `strm_nil` in `LAMBDA3/mylib/strm.lam`.
- The supplied `LAMBDA3/` interpreter is used unchanged.
- AI assistance is described in [AI-TRANSCRIPT.md](AI-TRANSCRIPT.md).

## Limitations

- The interpreter is slow, about 0.43 ms per event, so reading the whole 8×8
  trace takes about 15 seconds. The animation is not affected.
- One lock serves all streams, one request at a time. This is fine for local
  use.
- Expired streams are removed at the next request, not at the exact moment
  they expire.
- JSON-RPC batches are not supported (they get `-32600`).
- Only macOS was tested, and the browser checklist expects Chrome at its
  usual macOS location unless `CHROME` is set.
