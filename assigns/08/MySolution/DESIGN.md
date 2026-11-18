# Assignment 08 design: animated N-Queens search with CPS and lazy streams

Contents:

1. [Scope](#1-scope)
2. [Architecture](#2-architecture)
3. [Solver: state, invariant, continuations](#3-solver-state-invariant-continuations)
4. [From CPS search to lazy stream](#4-from-cps-search-to-lazy-stream)
5. [LAMBDA3 adapter](#5-lambda3-adapter)
6. [Stream table: lifetime, cleanup, limits](#6-stream-table-lifetime-cleanup-limits)
7. [JSON-RPC contract and errors](#7-json-rpc-contract-and-errors)
8. [Browser client](#8-browser-client)
9. [Security boundaries](#9-security-boundaries)
10. [Reuse and attribution](#10-reuse-and-attribution)
11. [Known limitations](#11-known-limitations)

## 1. Scope

- The solver is a depth-first backtracking search for board sizes 4 to 10,
  written in LAMBDA3 in continuation-passing style (CPS). Its trace is a lazy
  stream of `try`, `place`, `reject`, `backtrack`, `solution` and `done` events.
- The service is local and exposes that fixed solver through `POST /rpc`
  (JSON-RPC 2.0). It keeps each open stream's lazy cursor in process memory.
- A plain HTML/CSS/JavaScript page animates the search, asking the server for
  events only as playback needs them. Its default board is 8×8.
- Out of scope: accounts, persistence, public deployment, and evaluating any
  LAMBDA source sent by a client.

## 2. Architecture

Requests travel down the left side and responses come back up the right side.
Each layer knows only the one below it.

```text
Browser: index.html, main.js -> player.js -> render.js; transport.js does the HTTP
   |  POST /rpc {"jsonrpc":"2.0","method":"queens.next",          ^  HTTP 200 application/json
   |             "params":{"stream_id":"…","limit":1},"id":7}     |  {"jsonrpc":"2.0","result":{"events":[…],"done":false},"id":7}
   v                                                              |  (HTTP 204, empty body, for a notification)
app.py  HTTP endpoint: POST /rpc checks media type and size; GET / and /static/* serve the client
   |  raw request body                                            ^  response object, or None
   v                                                              |
rpc.py  JSON-RPC dispatcher: strict JSON decode, envelope, ids, method table, error objects
   |  method name + params                                        ^  result dict, or RpcError
   v                                                              |
methods.py  service.health, queens.open / queens.next / queens.close: parameter validation
   |  size  |  stream_id, limit  |  stream_id                     ^  JSON events + done flag
   v                                                              |
streams.py  StreamTable: uuid -> {cursor, size, exhausted, expires_at}, one lock, injected clock
   |  cursor (an unforced Strm value)                             ^  decoded events + new cursor
   v                                                              |
lambda_adapter.py  loads solver.lam once; applies queens_stream; forces cells with lazy_eval; decodes
   |  lazy_eval(cursor)                                           ^  stcn_cons(event tuple, unforced tail)
   v                                                              |
LAMBDA3 interpreter (assigns/08/LAMBDA3/lambda3.py) running solver.lam:
   CPS search whose continuations build the lazy event stream
```

Files in `MySolution/`:

| File | Responsibility |
| --- | --- |
| `solver.lam` | The CPS search, CPS safety check, pure board/event helpers, and lazy stream construction. No knowledge of HTTP or JSON. |
| `lambda_adapter.py` | Loads this assignment's LAMBDA3, type-checks `solver.lam`, opens streams, forces cells, converts events to JSON. Contains no search logic. |
| `streams.py` | Stream IDs, cursors, atomic consumption, close, expiry, exhausted records. |
| `methods.py` | The four RPC methods and their parameter validation. |
| `rpc.py`, `errors.py` | JSON-RPC envelope handling and error objects, adapted from Assign07. |
| `app.py`, `__main__.py` | Flask transport and command-line entry point (`python -m MySolution`). |
| `static/` | `index.html`, `style.css`, `js/transport.js`, `js/player.js`, `js/render.js`, `js/main.js`. |
| `tests/` | Python `unittest` suites and Node `node:test` suites for client logic. |
| `requirements.txt`, `.gitignore` | Pinned dependency (Flask), ignored virtual environment and caches. |

## 3. Solver: state, invariant, continuations

### 3.1 Board representation

- `n` is the board size, 4 ≤ `n` ≤ 10. Python validates it before calling the
  solver.
- Rows and columns are numbered from 0. Every row gets exactly one queen, so a
  board is described by the queen's column in each filled row: `c(0)`, `c(1)`, ….
- **Internal board** (`List[sint]` inside LAMBDA3): newest row first. A board
  with `k` queens is `[c(k-1), …, c(1), c(0)]`. Adding a queen is a single
  `list_cons`, and the safety check walks outward from the nearest earlier row
  with distance 1, 2, 3, ….
- **Public board** (JSON array): row order `[c(0), c(1), …, c(k-1)]`.
- The conversion happens **exactly once**, in `lambda_adapter.board_to_json`,
  which reverses the list while decoding it. Nothing else reverses boards.

### 3.2 Event encoding inside LAMBDA3

LAMBDA3 has no strings, records, sum types or type aliases, so an event is a
tagged tuple:

```text
E = (sint, sint, sint, List[sint])      # (tag, column, row, internal board)
tags: 0 try   1 place   2 reject   3 backtrack   4 solution   5 done
```

`solution` and `done` store `column = row = -1`, and `done` stores the empty
board. These tags and sentinels never leave the adapter. JSON events use names
and include only the fields listed in [section 7.4](#74-event-schema).

### 3.3 Search state and the partial-board invariant

Every call to the search carries the state `(n, row, column, board, sk, fk)`:

| Component | Meaning |
| --- | --- |
| `n` | Board size. |
| `row` | The row to fill next. It equals the number of queens already placed. |
| `column` | The next candidate column in `row`. Columns `0 … column-1` of this row have already been explored for this board. |
| `board` | The valid partial board for rows `0 … row-1` (internal order). |
| `sk` | Success continuation: what to do with a complete board. |
| `fk` | Failure continuation: what to do when `row` has no candidate columns left. |

**Valid partial board invariant.** This holds for every board passed to the
search and every board inside an event:

1. `length(board) = row`. There is exactly one queen in each of rows
   `0 … row-1`, so no two queens can ever share a row.
2. `0 ≤ c(r) < n` for every filled row `r`.
3. For all filled rows `r1 < r2`: `c(r1) ≠ c(r2)` (no shared column) and
   `|c(r1) − c(r2)| ≠ r2 − r1` (no shared diagonal in either direction).

**About "same row" in the required safety tests.** The assignment asks for a
"same row" safety test. That wording matches the supplied `eight_queens.lam`,
which stores one queen per *column*. In this assignment's one-queen-per-row
representation, a same-row conflict cannot arise during search (invariant
clause 1). The pure coordinate helper `queens_attacks(row1, col1, row2, col2)`
still checks same row, same column and both diagonals, and is tested directly
for all four. The search-level tests check clause 1 on every event, along with
same-column rejections and rejections on both diagonals.

### 3.4 Continuation types

LAMBDA3 defines `Strm[T] = Lazy[Stcn[T]]`. Because there are no type aliases,
`solver.lam` writes these types out in full.

| Continuation | Type | Called when |
| --- | --- | --- |
| Success `sk` | `(List[sint], unit -> Strm[E]) -> Strm[E]` | `row = n`. It receives the complete board and the failure continuation that resumes the search after this solution. |
| Failure `fk` | `unit -> Strm[E]` | The current row has no untried columns. A nested failure records the backtrack and tries the next column in the parent row. The root failure emits `done`. |
| Safe | `unit -> A` | The candidate survives every earlier queen. |
| Conflict | `unit -> A` | The first earlier queen that attacks the candidate is found. |

`queens_check_safe` is **polymorphic in its answer type `A`**. The search uses
it with `A = Strm[E]`. The tests use `A = sint` to see directly which
continuation was taken. LAMBDA3's type checker accepts this polymorphic `fix`,
and it runs at both types. The checker never returns a Boolean for the search
to inspect.

### 3.5 Declarations in `solver.lam`

`solver.lam` is a declaration file, like `LAMBDA3/mylib/*.lam`. The adapter
parses it with `d0cls_parse` and type-checks it with `d0cls_typecheck`. The
tests can then call each helper through LAMBDA3, not through a Python copy.

| Name | Type | Role |
| --- | --- | --- |
| `queens_attacks` | `(sint, sint, sint, sint) -> bool` | Pure. True if two squares `(row1, col1)` and `(row2, col2)` share a row, a column, or either diagonal. |
| `queens_place` | `(sint, List[sint]) -> List[sint]` | Pure. Extends a partial board with a queen in the next row. |
| `queens_ev_try`, `queens_ev_place`, `queens_ev_reject`, `queens_ev_backtrack` | `(sint, sint, List[sint]) -> E` | Pure event constructors taking `(column, row, board)`. |
| `queens_ev_solution` | `List[sint] -> E` | Pure. |
| `queens_ev_done` | `unit -> E` | Pure. |
| `queens_strm_nil[T]` | `unit -> Strm[T]` | The empty stream. |
| `queens_emit[T]` | `(T, unit -> Strm[T]) -> Strm[T]` | One lazy cell whose tail is suspended (the assignment's `emit_lazy`). |
| `queens_check_safe[A]` | `(sint, sint, sint, List[sint], unit -> A, unit -> A) -> A` | CPS safety recursion over `(row, column, distance, board, on_safe, on_conflict)`. |
| `queens_search` | `(sint, sint, sint, List[sint], Success, Failure) -> Strm[E]` | CPS search over `(n, row, column, board, sk, fk)`. |
| `queens_on_solution` | `Success` | Root success continuation. |
| `queens_root_exhausted` | `Failure` | Root failure continuation. Emits `done`. |
| `queens_stream` | `sint -> Strm[E]` | Factory. Builds a suspended search for size `n` without running it. |

### 3.6 Pseudocode for trying a candidate and resuming

The pseudocode below has the same shape as the LAMBDA3 code. In LAMBDA3 a
multi-argument call such as `f(a, b)` passes the tuple `(a, b)`, and `λ().`
stands for `lam (u: unit) =>`.

```text
emit(e, k) = lazy_make(λ(). stcn_cons(e, lazy_make(λ(). lazy_eval(k(())))))

check_safe(row, column, d, board, on_safe, on_conflict) =
  if list_nilq(board)                                     then on_safe(())
  else if attacks(row, column, row - d, list_head(board)) then on_conflict(())
  else check_safe(row, column, d + 1, list_tail(board), on_safe, on_conflict)

search(n, row, column, board, sk, fk) =
  if row == n         then sk(board, fk)             # complete board: success, hand over "resume"
  else if column == n then fk(())                    # no candidates left in this row: failure
  else emit(ev_try(column, row, board), λ().
         check_safe(row, column, 1, board,
           λ(). let next = place(column, board) in               # on_safe
                emit(ev_place(column, row, next), λ().
                  search(n, row + 1, 0, next, sk,
                    λ(). emit(ev_backtrack(column, row, board), λ().   # the child's failure:
                           search(n, row, column + 1, board, sk, fk)))), #   resume at next column
           λ(). emit(ev_reject(column, row, board), λ().             # on_conflict
                  search(n, row, column + 1, board, sk, fk))))       #   resume at next column

on_solution(board, resume) = emit(ev_solution(board), resume)
root_exhausted(())         = emit(ev_done(()), λ(). strm_nil(()))
queens_stream(n)           = lazy_make(λ(). lazy_eval(search(n, 0, 0, [], on_solution, root_exhausted)))
```

**How this maps to the assignment's sketch.** LAMBDA3's `fix` binds a single
recursive function, so mutual recursion between `search` and `try_column` is
not available. One function does both jobs: `search(n, row, 0, …)` plays the
role of the sketch's `search(row, …)`, and `search(n, row, column, …)` with
`column > 0` plays the role of `try_column`. Only the place branch increments
`row`, and it always passes `column = 0`, so a call with `row = n` is always a
fresh row, exactly as in the sketch.

**How continuations encode search order.** The failure continuation passed to
the child is a closure over the current search point (`row`, `column`, the
parent `board`, the parent `fk`). When the child's subtree is exhausted, that
closure emits `backtrack(column, row, board)` and then tries `column + 1` in
the same row. Columns are therefore tried left to right, and a child subtree
is finished before its next sibling starts, which is depth-first order. After
the last column of row 0, the root failure continuation emits `done`. After a
solution, `resume` is the failure continuation of row `n-1`, so the search
picks up exactly where it stopped.

**Tail positions.** Each branch of `search` and `check_safe` ends in a call:
`sk(board, fk)`, `fk(())`, `on_safe(())`, `on_conflict(())`, the recursive
`check_safe`, or `emit(…)`. Each continuation's body is itself a single call
to `check_safe`, `search` or `emit`. The interpreter still uses Python
recursion: tail position in LAMBDA source does not get tail-call
optimization. The stack stays small because every path reaches an `emit`
after a bounded number of steps, and `emit` returns at once
([section 4.3](#43-bounded-work-and-bounded-stack)).

### 3.7 Order, uniqueness and termination

- **Order.** Rows are filled in increasing order, and within a row columns are
  tried left to right with each child finished before its sibling. Solutions
  therefore appear in lexicographic order of their public boards. For `n = 4`
  that is `[1,3,0,2]` then `[2,0,3,1]`. The tests compare against a test-only
  reference enumerator.
- **Uniqueness.** A complete board corresponds to exactly one path (one column
  per row), and each path is visited once.
- **Termination.** The search tree is finite. The root failure continuation
  runs exactly once, after row 0's last column, and emits `done`. The tail of
  `done` is the empty stream.

Results of `solver.lam` on the supplied interpreter, checked by the tests in
`tests/test_solver.py`: size 4 produces 139 events with solutions `[1,3,0,2]`
then `[2,0,3,1]`. Size 8 produces 33,589 events: 15,720 `try`, 13,664
`reject`, 2,056 `place`, 2,056 `backtrack`, 92 `solution` and 1 `done`. All
92 boards are valid, distinct, and in lexicographic order. The first 8×8 solution, `[0,4,7,5,2,6,1,3]`, is event
number 1,858. The last 8×8 solution is `[7,3,0,2,5,1,6,4]`.

## 4. From CPS search to lazy stream

### 4.1 Construction does no search

`queens_stream(n)` evaluates `lazy_make(λ(). …)` and returns a new `Lazy`
value whose thunk has not been called. The search function is never applied
during construction. The call to `search(n, 0, 0, …)` sits inside the thunk on
purpose. Without it, opening a stream would already compute the first `try`
event.

### 4.2 What forcing one cell does

`emit(e, k)` returns `lazy_make(λ(). stcn_cons(e, lazy_make(λ(). lazy_eval(k(())))))`.

- LAMBDA3 is call-by-value, so `stcn_cons` evaluates both of its arguments.
  Its second argument is a `lazy_make(…)` expression. Evaluating it creates a
  new unforced `Lazy` value and does **not** call `k`. This is why a delivered
  event's tail stays unforced.
- The continuation `k` runs only when the consumer forces that tail. Calling
  `k(())` performs the search work up to the next `emit` and returns that
  emit's unforced `Lazy`. The surrounding `lazy_eval` turns it into the next
  cell, which only builds a `stcn_cons`. The trap to avoid is writing
  `stcn_cons(e, k(()))`, which would run the next step's work while building
  the current cell.
- `lazy_eval` memoizes. Forcing the same cell twice never repeats search work.

Work done when the tail after each event is forced:

| Event just delivered | Forcing its tail runs | Next event produced |
| --- | --- | --- |
| `try(c, r)` | `check_safe` against at most `r` earlier queens | `place(c, r)` or `reject(c, r)` |
| `place(c, r)` | `search(n, r+1, 0, …)` | `solution` if `r+1 = n`, otherwise `try(0, r+1)` |
| `reject(c, r)` or `backtrack(c, r)` | `search(n, r, c+1, …)` | `try(c+1, r)`. If `c+1 = n`, the parent's failure continuation runs instead: `backtrack` of the parent, or `done` at the root. |
| `solution` | `resume()`, the failure continuation of row `n-1` | `backtrack(c, n-1)` |
| `done` | the empty stream | nothing. The service never forces this tail. |

### 4.3 Bounded work and bounded stack

Each force does O(n) interpreter work: at most one safety walk plus a constant
number of continuation hops. The Python stack returns to the consumer after
every event. Measured through the adapter, the entire 8×8 run completes with
Python's recursion limit lowered to 105, and a 5,000-event 10×10 prefix
completes with the limit lowered to 120. Continuations do not pile up on the
stack (`LazinessTests.test_stack_depth_stays_bounded`).

### 4.4 Memory

The service keeps only the current cursor. Continuations capture boards and
outer continuations, never earlier stream cells, so cells already delivered
become unreachable and Python frees them. The live state of one stream is its
current cell plus at most `n` nested failure continuations. A test checks
this with a weak reference to a delivered cell.

### 4.5 How laziness is tested

Looking at a printed `<lazy>` value is not evidence. The tests use three
observable checks:

1. **Interpreter call counter.** The tests wrap `lambda3._d0val_apply`, the
   interpreter's application function, and count calls to the `search` and
   `check_safe` closures. Opening a stream must give zero calls. Taking `k`
   events must give a bounded count, and the stored cursor must be unevaluated.
2. **A tail that fails if forced.** The adapter's `take` is run on a LAMBDA3
   stream whose second cell would raise if it were ever computed.
3. **Weak reference.** A cell that has already been delivered must be freed.

## 5. LAMBDA3 adapter

`lambda_adapter.py` has five jobs and contains no search logic:

1. **Load the right interpreter.** It inserts `assigns/08/LAMBDA3`, computed
   from its own file path, into `sys.path`. It then checks that
   `lambda3.__file__` really is inside that directory, so another
   assignment's copy cannot be imported by accident.
2. **Load the solver once.** It parses and type-checks `solver.lam` at startup
   and checks that `queens_stream` has type `sint -> Lazy[Stcn[E]]`. It then
   evaluates `let <solver.lam> in queens_stream end` once to get the factory
   closure.
3. **Open.** `open_stream(size)` evaluates the application `make(size)` with
   `d0exp_evaluate` in an environment that binds `make` to the factory. The
   result is an unforced `Lazy` value.
4. **Force.** It evaluates the expression `lazy_eval(s)` with `d0exp_evaluate`
   in an environment that binds `s` to the cursor. This is the interpreter's
   own `lazy_eval`, including its memoization. There is no custom forcing
   routine.
5. **Decode.** It reads the cell's tag, column, row and board and builds the
   JSON event. The board is reversed into row order here, once.

`take(cursor, limit)` forces at most `limit` cells and returns
`(events, next_cursor, done)`. After the k-th event it keeps that cell's tail
**without forcing it**. When it decodes `done` it stops at once and returns
`next_cursor = None`, so the tail after `done` is never forced. If a stream
ended without `done`, which the construction rules out, `take` raises an
internal error instead of inventing a `done`.

## 6. Stream table: lifetime, cleanup, limits

Each entry holds `size`, `cursor` (a `Lazy` value, or `None` once released),
`exhausted` (bool) and `expires_at` (a monotonic time in seconds).

- **IDs.** `str(uuid.uuid4())`: 122 random bits, unguessable, valid only in
  this process. A server restart invalidates every ID.
- **Atomicity.** One `threading.Lock` guards the table and every forcing.
  Each method call is atomic: two requests never advance one stream at the
  same time, a `close` cannot interleave with a `next` in progress, and
  streams opened separately share nothing. Serializing all streams is
  acceptable for a local service. One `next` with limit 32 takes about 14 ms
  of interpreter time.
- **Clock.** The clock is an injected callable, `time.monotonic` by default,
  so tests can make expiry deterministic.

| Operation | Behavior |
| --- | --- |
| `open(size)` | Sweep. If 64 entries already exist, return error `-32021`. Otherwise create an entry whose cursor is `adapter.open_stream(size)` (unforced), with `expires_at = now + TTL`. Return the new ID. |
| `next(id, limit)` | Sweep. If the ID is missing, return `-32020`. If the stream is exhausted, return `{"events": [], "done": true}` and refresh the deadline. Otherwise `take(cursor, limit)`, store the returned tail, and refresh the deadline. When `done` is delivered, set `cursor = None` and `exhausted = True`. |
| `close(id)` | Sweep. If the ID is missing, return `-32020`. Otherwise delete the entry and return `{"closed": true}`. |

- **Inactivity lifetime.** 300 seconds, configurable with `--stream-ttl`.
  Activity means a successful `open` or `next`, including an empty read after
  exhaustion. Each activity moves `expires_at` to `now + TTL`. This value is a
  design choice, not something the assignment specifies.
- **Sweep and reclamation.** Every table operation first removes entries
  whose `expires_at ≤ now`. An expired entry's memory is reclaimed at the
  first request after its deadline. There is no background thread, so an idle
  server keeps at most 64 entries until the next request.
- **Exhausted streams.** The response that delivers `done` drops the solver
  state: the cursor and, through it, every continuation. A small record
  `{size, exhausted, expires_at}` remains so that repeated `next` calls
  return `{"events": [], "done": true}` until the record is closed or expires.
- **Close.** Removes the entry at once. Afterwards the ID behaves like an
  unknown ID (`-32020`).
- **Internal failure while forcing.** The entry is removed, any events from
  the failed request are discarded, and the client gets `-32603` with an
  incident ID. The stream ID then reports `-32020`.

## 7. JSON-RPC contract and errors

### 7.1 HTTP transport

- `POST /rpc` requires `Content-Type: application/json`, with optional
  `charset=utf-8` in any letter case. Any other media type gets
  `415 text/plain`.
- A body larger than 64 KiB gets `413 text/plain`.
- A JSON-RPC response is sent with HTTP 200 and `application/json`. A
  notification gets HTTP 204 with an empty body and no `Content-Type`.
- Other HTTP methods on `/rpc` get 405. `GET /` serves `index.html`,
  `GET /static/<path>` serves client assets, and other paths get 404.
- The server binds `127.0.0.1:8000` by default.

### 7.2 Envelope rules

These rules are adapted from the Assign07 dispatcher:

- A request must be an object whose only members are `jsonrpc`, `method`,
  `params` and `id`. `jsonrpc` must be `"2.0"`, `method` a string, `params`
  (if present) an object or array, and `id` (if present) a string, a number
  or `null`. Booleans are not valid IDs.
- A missing `id` makes the request a **notification**. `"id": null` is a call
  and gets a response with `"id": null`. Valid IDs are echoed exactly,
  including `0`, `-1`, `"abc"` and `1.5`.
- Parse errors (`-32700`) and invalid requests (`-32600`) are answered with
  `"id": null`, because the request's ID cannot be trusted. An invalid request
  object without an `id` is still answered with HTTP 200, since it is not a
  valid notification.
- **Batches are not supported.** A JSON array body (empty or not) gets one
  `-32600` response with `data: {"reason": "batch_not_supported"}`. The client
  never needs batches, and this keeps each HTTP request to one atomic stream
  operation.
- A **valid notification** is executed. For example, `queens.next` advances
  the stream and `queens.close` closes it. The response is always 204 with an
  empty body, even if the method or its parameters fail.
- `NaN`, `Infinity` and integers too long to convert are parse errors.

### 7.3 Methods and parameters

`params` must be a JSON object; omitting it is allowed only for
`service.health`. Unknown keys are rejected. An integer parameter must be a
JSON integer: `true`, `false`, `8.0`, `1.5`, `"8"` and `null` are all
rejected. Validation finishes before the stream table is touched, so invalid
parameters never allocate state.

| Method | Parameters | Result |
| --- | --- | --- |
| `service.health` | none, or `{}` | `{"status": "ok", "version": "1.0"}` |
| `queens.open` | `{"size": n}`, required integer, 4 ≤ n ≤ 10 | `{"stream_id": "<uuid>", "size": n}` |
| `queens.next` | `{"stream_id": s, "limit": k}`, both required: `s` a string, `k` an integer 1 ≤ k ≤ 32 | `{"events": [ … at most k … ], "done": bool}` |
| `queens.close` | `{"stream_id": s}`, required string | `{"closed": true}` |

Invalid-parameter errors (`-32602`) carry `data` that names the problem, for
example `{"field": "size", "reason": "out_of_range", "minimum": 4,
"maximum": 10}`. The possible reasons are `not_an_object`, `missing`,
`unexpected` (with the offending `fields`), `not_an_integer`, `out_of_range`
and `not_a_string`.

### 7.4 Event schema

| `event` | Other fields | Board snapshot |
| --- | --- | --- |
| `try` | `column`, `row`, `board` | The parent board before the candidate is considered (`row` entries). |
| `place` | `column`, `row`, `board` | The board after adding the safe candidate (`row + 1` entries, the last one equal to `column`). |
| `reject` | `column`, `row`, `board` | The unchanged parent board. The candidate conflicts with at least one of its queens. |
| `backtrack` | `column`, `row`, `board` | The parent board restored after removing the queen at (`row`, `column`). |
| `solution` | `board` | A complete valid board (`n` entries). |
| `done` | none | Exactly once, as the last event. |

Coordinates are integers from `0` to `n-1`. Boards are arrays in row order.

### 7.5 Error codes

All errors below are sent with HTTP 200 (or 204 for a notification) and
never include tracebacks, file paths, interpreter values or closures.

| Code | Message | When |
| --- | --- | --- |
| `-32700` | Parse error | The body is not valid UTF-8 JSON. |
| `-32600` | Invalid Request | Envelope rules broken, or a batch. |
| `-32601` | Method not found | Any name other than the four methods. |
| `-32602` | Invalid params | See [section 7.3](#73-methods-and-parameters). |
| `-32603` | Internal error | Unexpected exception. `data` holds only `{"incident": "<hex>"}`, and the details are logged on the server. |
| `-32020` | Stream not found | The stream ID is unknown, closed or expired. Application error. |
| `-32021` | Too many open streams | 64 entries already exist. `data: {"limit": 64}`. Application error. |

### 7.6 Example exchanges

The events below are real output of `solver.lam` on the supplied interpreter.
The UUID is illustrative.

`service.health`:

```json
{"jsonrpc": "2.0", "method": "service.health", "params": {}, "id": 1}
```

```json
{"jsonrpc": "2.0", "result": {"status": "ok", "version": "1.0"}, "id": 1}
```

`queens.open`:

```json
{"jsonrpc": "2.0", "method": "queens.open", "params": {"size": 8}, "id": 2}
```

```json
{"jsonrpc": "2.0", "result": {"stream_id": "6f1c2c1e-6c0b-4a51-9c39-2a7c8f0e5d41", "size": 8}, "id": 2}
```

`queens.next`, the first three events of an 8×8 stream:

```json
{"jsonrpc": "2.0", "method": "queens.next", "params": {"stream_id": "6f1c2c1e-6c0b-4a51-9c39-2a7c8f0e5d41", "limit": 3}, "id": 3}
```

```json
{"jsonrpc": "2.0", "result": {"events": [{"event": "try", "column": 0, "row": 0, "board": []}, {"event": "place", "column": 0, "row": 0, "board": [0]}, {"event": "try", "column": 0, "row": 1, "board": [0]}], "done": false}, "id": 3}
```

`queens.next` around the first solution (events 1,857 to 1,859):

```json
{"jsonrpc": "2.0", "result": {"events": [{"event": "place", "column": 3, "row": 7, "board": [0, 4, 7, 5, 2, 6, 1, 3]}, {"event": "solution", "board": [0, 4, 7, 5, 2, 6, 1, 3]}, {"event": "backtrack", "column": 3, "row": 7, "board": [0, 4, 7, 5, 2, 6, 1]}], "done": false}, "id": 40}
```

`queens.next` at the end of the stream, and a later read of the exhausted ID:

```json
{"jsonrpc": "2.0", "result": {"events": [{"event": "reject", "column": 7, "row": 1, "board": [7]}, {"event": "backtrack", "column": 7, "row": 0, "board": []}, {"event": "done"}], "done": true}, "id": 1200}
```

```json
{"jsonrpc": "2.0", "result": {"events": [], "done": true}, "id": 1201}
```

`queens.close`:

```json
{"jsonrpc": "2.0", "method": "queens.close", "params": {"stream_id": "6f1c2c1e-6c0b-4a51-9c39-2a7c8f0e5d41"}, "id": 1202}
```

```json
{"jsonrpc": "2.0", "result": {"closed": true}, "id": 1202}
```

Errors: `queens.next` on the closed ID, then an out-of-range size:

```json
{"jsonrpc": "2.0", "error": {"code": -32020, "message": "Stream not found"}, "id": 1203}
```

```json
{"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params", "data": {"field": "size", "reason": "out_of_range", "minimum": 4, "maximum": 10}}, "id": 5}
```

A notification (no `id`) that advances a stream gets `HTTP 204` with an empty
body:

```json
{"jsonrpc": "2.0", "method": "queens.next", "params": {"stream_id": "6f1c2c1e-6c0b-4a51-9c39-2a7c8f0e5d41", "limit": 1}}
```

## 8. Browser client

### 8.1 Modules

These are ES modules served from `static/`, with no CDN, framework or build
step.

- `transport.js`: `createRpcClient(fetchFn, url)` returns
  `call(method, params)`. It resolves to the `result`, or throws an
  `RpcError(code, message)` for a JSON-RPC error, or a `TransportError` for a
  network failure, a non-200 status or a body that is not JSON.
- `player.js`: no DOM access. It holds playback state and the event reducer.
  The RPC client, the timer function and a change callback are injected, so
  Node tests can drive it.
- `render.js`: draws the board, status, counters and log from the player's
  view state.
- `main.js`: connects buttons, the speed slider and the size selector to the
  player.

### 8.2 Client state

| Field | Meaning |
| --- | --- |
| `run` | Generation number, incremented by Start and Reset. |
| `streamId` | The current server stream, or `null`. |
| `mode` | `idle`, `paused`, `playing`, `seeking` (Next solution), `done` or `error`. |
| `inFlight` | True while a `queens.open` or `queens.next` request is pending. At most one consuming request is allowed per stream. |
| `buffer` | Events fetched but not yet shown, at most 31. |
| view | Committed board, candidate square, highlight, last event, solution count, per-kind counts, and a log bounded to the last 200 entries. |

### 8.3 Controls

| Control | Behavior |
| --- | --- |
| **Start / Restart** | Resets any current stream, opens a fresh one at the selected size (default 8), and starts playing. |
| **Step** | Switches to paused and shows exactly one event, taken from the buffer or fetched with `limit: 1`. Opens a stream first if none exists. |
| **Play / Pause** | Toggles between playing and paused. While playing, one event is shown per tick and `limit: 1` is fetched whenever the buffer is empty. Pause stops scheduling. If a request is in flight when Pause is pressed, its event is buffered and shown on the next Step or Play, so no event is lost or skipped. |
| **Next solution** | Fetches batches of up to 32 events and applies them without per-event delay, stopping immediately after the next `solution` (or `done`). Unshown events from the last batch stay in the buffer. Without batching, reaching the first 8×8 solution would take 1,858 requests; with batches of 32 it takes about 59. |
| **Reset** | Increments `run`, cancels timers, sends `queens.close` for the old stream (errors ignored), clears the board, counters, log and buffer, and returns to `idle`. |
| **Speed** | A slider mapping to a delay of 1000 ms down to 10 ms per event. It applies from the next tick. |
| **Pause at solutions** | A checkbox, on by default. While playing, a `solution` event switches the mode to paused. |
| **Board size** | A selector for 4 to 10, default 8. Changing it during a search resets. |

**Stale responses.** Each asynchronous step records `run` when its request
starts. If `run` has changed by the time the response arrives, the response
is discarded and cannot touch the board, counters or log. If the stale
response came from `queens.open`, the client closes that orphaned stream.

**Errors.** A transport or RPC failure stops playback, sets `mode = error`,
and shows the message in an alert region. Stream-not-found (`-32020`) gets a
specific message about the stream expiring. In this state, Start (Restart)
and Reset stay enabled.

**Completion.** `done` sets `mode = done` and shows a status banner,
"Search complete: N solutions", styled differently from a solution banner.
Step, Play and Next solution are disabled, and Start is labeled Restart.

### 8.4 Visual states

Every state uses color, a symbol and text together, so none relies on color
alone.

| Event | Board | Status text |
| --- | --- | --- |
| `try` | A candidate queen with a dashed amber outline at (row, column). Committed queens come from the snapshot. | "Try row r, column c" |
| `place` | The queen becomes solid, with a green flash. | "Place queen at row r, column c" |
| `reject` | The candidate square turns red with a ✕. The attacking queen is outlined red and the squares between them are tinted. | "Reject row r, column c: same column as the queen in row i" or "… on a diagonal with the queen in row i" |
| `backtrack` | The removed queen's square shows a fading purple ↩ outline. The board shows the restored snapshot. | "Backtrack: remove the queen from row r, column c" |
| `solution` | All queens turn gold, the board border turns gold, and the counter increments. | "Solution k: [ … ]" |
| `done` | The final board stays visible, with a blue completion banner. | "Search complete: N solutions" |

The reject explanation is display logic in `player.js`. It finds the first
attacking queen in the same order as `queens_check_safe` (nearest row first)
and never affects the search. Every one of the 13,664 rejections in the 8×8
trace has an attacking queen on its board
(`EventTests.test_every_reject_has_an_attacking_queen`).

### 8.5 Accessibility and layout

- Controls are native `<button>`, `<input>` and `<select>` elements with
  labels, a visible `:focus-visible` outline, and clear disabled styling.
  Play/Pause uses `aria-pressed`.
- The status line is an `aria-live="polite"` region and also states the
  board as text. Errors use `role="alert"`.
- The board sits beside the controls on laptop widths and stacks above them
  below about 720 px. Square size scales with the viewport.

## 9. Security boundaries

- The browser cannot send LAMBDA source, file paths or function names. The
  method table is fixed at four names, and parameters are strictly typed.
- The server binds `127.0.0.1` by default.
- Resource limits: request bodies up to 64 KiB, at most 32 events per call,
  at most 64 open streams, and a 300-second inactivity lifetime.
- Error responses never contain tracebacks, paths, interpreter values or
  closures. Internal errors are logged on the server under an incident ID.

## 10. Reuse and attribution

- **Assign07 `MySolution/app.py`, `rpc.py` and `errors.py`** (this student's
  own earlier work) are copied into this directory and adapted, not
  imported. The parts kept are the strict JSON decoding, envelope checks,
  method dispatch, incident-ID internal errors, media-type check and 204
  handling. The `lambda.*` methods and per-call worker processes are removed,
  batch handling becomes `batch_not_supported`, the error codes change, and
  static file serving is added.
- **`LAMBDA3/mytest/eight_queens.lam`** (instructor example): the idea of
  walking a newest-first board with distance 1, 2, … to detect diagonal
  attacks. Its direct-style search and its one-queen-per-column board are
  not used.
- **`LAMBDA3/mytest/eight_queens_stream.lam`** is not reused. It is
  direct-style, and it uses stream append rather than continuations.
- **`LAMBDA3/mylib/strm.lam`**: the shape of the empty stream,
  `lazy_make(λ(). stcn_nil())`.

## 11. Known limitations

- The interpreter takes about 0.43 ms per event, so the full 8×8 trace of
  33,589 events takes about 14.5 s of interpreter time. Fetching it through HTTP is correspondingly slow. The animation is
  unaffected.
- All state is in process memory. A restart invalidates every stream ID.
- One global lock serves streams one request at a time, which is acceptable
  for local use.
- Expired entries are reclaimed at the next request, not at the exact moment
  they expire.
