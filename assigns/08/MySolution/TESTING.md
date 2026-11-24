# Assignment 08 testing

This file maps each requirement of the assignment to the tests that check it.

## Commands

All commands run from `assigns/08/`.

| Suite | Command |
| --- | --- |
| Python: solver, adapter, stream table, RPC over HTTP | `MySolution/.venv/bin/python -B -m unittest discover -s MySolution/tests -t . -v` |
| Client logic (Node built-in test runner, no packages) | `node --test MySolution/tests/js/` |
| Browser checklist in headless Chrome (needs Google Chrome; set `PYTHON` or `CHROME` to override paths) | `node MySolution/tests/browser/checklist.mjs` |

## Ground rules

- Successful solver, stream and HTTP-flow tests use the supplied LAMBDA3
  interpreter in `assigns/08/LAMBDA3`. One test checks that this is the copy
  actually imported.
- Test doubles are allowed only for the clock, injected transport failures,
  and forced internal failures. They never stand in for a successful
  end-to-end result.
- Laziness is never judged from a printed `<lazy>` value. It is shown with an
  interpreter call counter, a tail that raises if forced, unevaluated-cursor
  checks, and a weak reference ([DESIGN.md §4.5](DESIGN.md#45-how-laziness-is-tested)).
- Exhausting the 8×8 search takes about 14.5 s in the interpreter, so the
  tests share one cached trace per board size (`trace` in
  `tests/support.py`). The determinism test opens a second, fresh 8×8 stream
  and compares it against that trace.

## 1. Requirement-to-test map

The **Assign08 #** column refers to the numbered "Required tests" list in
`Assign08.md`.

### R1. Safety checks (Assign08 #1)

| Test | File | What it shows |
| --- | --- | --- |
| `SafetyTests.test_attacks_same_row` | `tests/test_solver.py` | `queens_attacks` (run in LAMBDA3) detects two squares in one row. |
| `SafetyTests.test_attacks_same_column` | `tests/test_solver.py` | Same column detected. |
| `SafetyTests.test_attacks_down_right_diagonal` | `tests/test_solver.py` | Diagonal where `row − col` is equal. |
| `SafetyTests.test_attacks_down_left_diagonal` | `tests/test_solver.py` | Anti-diagonal where `row + col` is equal. |
| `SafetyTests.test_attacks_safe_pair` | `tests/test_solver.py` | A knight's-move pair and other safe pairs are not attacks. |
| `SafetyTests.test_check_safe_calls_on_safe` | `tests/test_solver.py` | `queens_check_safe` at answer type `sint` takes the safe continuation for a safe candidate against a multi-queen board. |
| `SafetyTests.test_check_safe_conflicts_column_and_both_diagonals` | `tests/test_solver.py` | Takes the conflict continuation for a column conflict and for each diagonal direction, including against a queen several rows back. |
| `SafetyTests.test_check_safe_stops_at_first_conflict` | `tests/test_solver.py` | The call counter shows recursion stops at the nearest conflict. |
| `EventTests.test_one_queen_per_row_invariant` | `tests/test_solver.py` | Every event board satisfies the partial-board invariant ([DESIGN.md §3.3](DESIGN.md#33-search-state-and-the-partial-board-invariant)). This covers the assignment's "same row" wording. |

### R2. CPS success and failure paths (Assign08 #2)

| Test | File | What it shows |
| --- | --- | --- |
| `CpsTests.test_complete_board_calls_success_with_resume` | `tests/test_solver.py` | `queens_search` with `row = n` calls the success continuation with the board, and the `resume` it receives is the given failure continuation. |
| `CpsTests.test_success_then_resume_at_next_candidate` | `tests/test_solver.py` | From row 3 of `[1,3,0]` (size 4): rejects, the place, the success marker, then the resume continuation's `backtrack` and the next column, then failure. |
| `CpsTests.test_exhausted_row_calls_failure` | `tests/test_solver.py` | A dead-end state calls its failure continuation, observed through a marker event emitted by a test continuation. |
| `CpsTests.test_reject_resumes_at_next_column` | `tests/test_solver.py` | In the trace, every `reject(c, r)` is followed by `try(c+1, r)` or by the row's failure continuation. |
| `CpsTests.test_backtrack_resumes_at_next_column_in_parent_row` | `tests/test_solver.py` | Every `backtrack(c, r)` is followed by `try(c+1, r)`, by the parent's `backtrack`, or by `done`. |
| `CpsTests.test_solution_resumes_with_backtrack_of_last_row` | `tests/test_solver.py` | After each `solution`, the next event is `backtrack(c, n-1)` with the restored board. |
| Source review: no direct-style search | `DESIGN.md` §3.6, `solver.lam` | The continuations decide every next action, and the safety check returns no Boolean to the search. Recorded as a review item. |

### R3. Exhaustive deterministic search (Assign08 #3)

| Test | File | What it shows |
| --- | --- | --- |
| `ExhaustiveSearchTests.test_size4_reference_trace` | `tests/test_solver.py` | Exact opening events and solutions `[1,3,0,2]`, `[2,0,3,1]` in that order. |
| `ExhaustiveSearchTests.test_size8_has_92_valid_unique_solutions` | `tests/test_solver.py` | 92 solutions, each checked by an independent Python validator, with no duplicates. |
| `ExhaustiveSearchTests.test_size8_lexicographic_dfs_order` | `tests/test_solver.py` | The order matches a test-only reference enumerator. |
| `ExhaustiveSearchTests.test_size8_deterministic_across_fresh_streams` | `tests/test_solver.py` | Two independently opened streams give identical event sequences. |
| `ExhaustiveSearchTests.test_small_size_solution_counts` | `tests/test_solver.py` | Sizes 4, 5 and 6 give 2, 10 and 4 solutions. |

### R4. Event kinds, coordinates and snapshots (Assign08 #4)

| Test | File | What it shows |
| --- | --- | --- |
| `EventTests.test_all_event_kinds_present` | `tests/test_solver.py` | All six kinds occur in the 8×8 trace. |
| `EventTests.test_snapshot_semantics` | `tests/test_solver.py` | `try`, `reject` and `backtrack` carry the parent board. `place` carries the parent board plus `column`. `solution` carries a complete board equal to the preceding `place`. |
| `EventTests.test_every_reject_has_an_attacking_queen` | `tests/test_solver.py` | Each rejection is justified by the board. |
| `EventTests.test_done_exactly_once_and_last` | `tests/test_solver.py` | Exactly one `done`, and it is the final event. |
| `AdapterTests.test_event_json_fields_and_row_order` | `tests/test_adapter.py` | Each kind's JSON has exactly its documented keys, with no internal tag or `-1` sentinel, and boards in row order. |
| `AdapterTests.test_solver_type` | `tests/test_adapter.py` | `queens_stream` type-checks as `sint -> Lazy[Stcn[(sint, sint, sint, List[sint])]]`. |
| `AdapterTests.test_unknown_event_tag_is_an_error` | `tests/test_adapter.py` | A tag outside 0–5 raises `SolverError` instead of reaching JSON. |

### R5. Lazy construction and bounded demand (Assign08 #5)

| Test | File | What it shows |
| --- | --- | --- |
| `LazinessTests.test_construction_applies_no_search` | `tests/test_laziness.py` | `queens_stream(8)` and `open_stream(8)` cause zero `search` and `check_safe` applications, and the root is unevaluated. |
| `LazinessTests.test_counter_sees_search_work` | `tests/test_laziness.py` | Control for the counter: consuming a size-4 stream registers search and safety-check calls. |
| `LazinessTests.test_forcing_one_cell_leaves_tail_unforced` | `tests/test_laziness.py` | One force gives `try(0,0,[])`, its tail is unevaluated, and the call counts are bounded. |
| `LazinessTests.test_bounded_prefix_sizes_8_9_10` | `tests/test_laziness.py` | After taking `k` events (`k` = 1, 10, 50), the stored cursor is unevaluated and the call counts grow with `k`, not with the search tree. |
| `LazinessTests.test_unread_failing_tail_is_never_run` | `tests/test_laziness.py` | `take` on a stream whose second cell raises returns the first event without error. |
| `LazinessTests.test_take_stops_at_done_without_forcing_its_tail` | `tests/test_laziness.py` | Taking past `done` never forces the tail after `done`. |
| `LazinessTests.test_delivered_cells_are_released` | `tests/test_laziness.py` | A weak reference to an already-delivered cell dies after the cursor advances. |
| `LazinessTests.test_stack_depth_stays_bounded` | `tests/test_laziness.py` | A long prefix succeeds under a lowered recursion limit, so continuations do not pile up on the stack. |
| `AdapterTests.test_imports_assignment_08_lambda3` | `tests/test_adapter.py` | `lambda3.__file__` is inside `assigns/08/LAMBDA3`. |
| `AdapterTests.test_take_continues_without_repeats_or_gaps` | `tests/test_adapter.py` | Two takes from a returned cursor equal one long take. |
| `AdapterTests.test_take_returns_fewer_events_at_end_of_stream` | `tests/test_adapter.py` | Fewer events at the end, `done` with no cursor, and the exact boundary where the limit lands just before `done` leaves the cursor unforced. |
| `AdapterTests.test_stream_without_done_is_an_error` | `tests/test_adapter.py` | A stream that ends without `done` raises `SolverError` instead of inventing one. |
| `AdapterTests.test_open_stream_rejects_bad_sizes` | `tests/test_adapter.py` | Sizes 3, 11, `True`, `8.0`, `"8"` and `None` are refused before LAMBDA3 is called; 4 and 10 open unforced. |

### R6. Stream lifecycle (Assign08 #6)

| Test | File | What it shows |
| --- | --- | --- |
| `StreamTableTests.test_open_returns_uuid_and_does_not_force` | `tests/test_streams.py` | A UUID4 string, and the cursor is unevaluated. |
| `StreamTableTests.test_streams_are_independent` | `tests/test_streams.py` | Interleaved reads of two streams match the separate sequences, with no shared cursor. |
| `StreamTableTests.test_next_never_forces_beyond_limit` | `tests/test_streams.py` | After `next(limit=k)` the stored cursor is unevaluated. Covers exact boundary and terminal cases. |
| `StreamTableTests.test_exhaustion_releases_solver_state` | `tests/test_streams.py` | After `done`, the cursor is `None` and a small exhausted record remains. |
| `StreamTableTests.test_repeated_next_after_exhaustion` | `tests/test_streams.py` | `{"events": [], "done": true}` repeatedly. |
| `StreamTableTests.test_close_then_next_is_stream_not_found` | `tests/test_streams.py` | `-32020` after close, and also when closing twice. |
| `StreamTableTests.test_unknown_id_is_stream_not_found` | `tests/test_streams.py` | `-32020`. |
| `StreamTableTests.test_active_stream_expires_after_ttl` | `tests/test_streams.py` | Fake clock: live at `TTL − ε`, `-32020` at `TTL`. |
| `StreamTableTests.test_activity_refreshes_deadline` | `tests/test_streams.py` | A `next` moves `expires_at`. |
| `StreamTableTests.test_exhausted_record_expires` | `tests/test_streams.py` | Repeated empty reads work until the TTL passes, then `-32020`. |
| `StreamTableTests.test_sweep_reclaims_expired_entries` | `tests/test_streams.py` | Expired entries leave the table at the next operation. |
| `StreamTableTests.test_open_limit` | `tests/test_streams.py` | The 65th open gets `-32021`, and nothing is allocated. |
| `StreamTableTests.test_internal_failure_removes_stream` | `tests/test_streams.py` | An injected forcing failure gives `-32603`, and the ID then reports `-32020`. |
| `StreamTableTests.test_concurrent_next_has_no_duplicates_or_gaps` | `tests/test_streams.py` | Threads reading one stream together reproduce the sequential sequence exactly. |

### R7. JSON-RPC envelope, methods, params, notifications, errors (Assign08 #7)

All of these go through the Flask test client, so they exercise the real HTTP
layer.

| Test | File | What it shows |
| --- | --- | --- |
| `EnvelopeTests.test_ids_are_echoed` | `tests/test_rpc.py` | `0`, `-1`, `"abc"`, `""`, `1.5` and `null` are echoed exactly. |
| `EnvelopeTests.test_invalid_envelopes` | `tests/test_rpc.py` | Bad `jsonrpc`, missing or non-string `method`, scalar `params`, boolean or object `id`, an extra member, or a non-object body: `-32600` with `id: null`, HTTP 200. |
| `EnvelopeTests.test_invalid_request_without_id_still_answered` | `tests/test_rpc.py` | HTTP 200 with a `-32600` body, not 204. |
| `EnvelopeTests.test_parse_errors` | `tests/test_rpc.py` | Malformed JSON, invalid UTF-8, `NaN`: `-32700`, `id: null`. |
| `EnvelopeTests.test_batches_not_supported` | `tests/test_rpc.py` | Empty and non-empty arrays: `-32600` with `batch_not_supported`, and no stream state changes. |
| `MethodTests.test_health` | `tests/test_rpc.py` | Exact result, with params omitted or `{}`. |
| `MethodTests.test_unknown_methods` | `tests/test_rpc.py` | `queens.reset`, `lambda.interpret`, `__init__` and `""` all give `-32601`. |
| `MethodTests.test_open_next_close_round_trip` | `tests/test_rpc.py` | Each method's result shape matches [DESIGN.md §7.3](DESIGN.md#73-methods-and-parameters). |
| `NotificationTests.test_valid_notification_changes_state_and_returns_204` | `tests/test_rpc.py` | A notification `queens.next` advances the stream (the next call sees the following event), with 204, an empty body and no `Content-Type`. |
| `NotificationTests.test_failing_notifications_return_204` | `tests/test_rpc.py` | An unknown method, invalid params or an unknown stream as a notification gives 204. |
| `ErrorTests.test_stream_not_found_application_error` | `tests/test_rpc.py` | `-32020` for unknown, closed and expired IDs (expired via an injected clock). |
| `ErrorTests.test_internal_error_is_sanitized` | `tests/test_rpc.py` | An injected exception gives `-32603` with only an incident ID: no traceback, path or Python type name. |
| `ErrorTests.test_too_many_streams_application_error` | `tests/test_rpc.py` | The 65th open gets `-32021` with `data: {"limit": 64}`. |
| `TransportTests.test_media_type_and_method_checks` | `tests/test_rpc.py` | A missing or wrong `Content-Type` gives 415, `GET`/`PUT`/`DELETE /rpc` give 405 with `Allow: POST`, and an unknown path gives 404, all as plain text. JSON in any letter case, with or without `charset=utf-8`, is accepted. |
| `TransportTests.test_body_size_limit` | `tests/test_rpc.py` | A body of exactly 64 KiB is accepted; one byte more gives 413 as plain text. |

### R8. Parameter boundaries and `limit` (Assign08 #8)

| Test | File | What it shows |
| --- | --- | --- |
| `ParamsTests.test_size_bounds` | `tests/test_rpc.py` | 4 and 10 accepted. 3, 11, `8.0`, `true`, `"8"`, `null` and a missing size give `-32602`. |
| `ParamsTests.test_limit_bounds` | `tests/test_rpc.py` | 1 and 32 accepted. 0, 33, `1.5`, `true`, `"1"` and a missing limit give `-32602`. |
| `ParamsTests.test_shape_errors` | `tests/test_rpc.py` | Array `params`, unknown keys, a non-string `stream_id`, and params omitted for `queens.*` give `-32602`. |
| `ParamsTests.test_invalid_params_allocate_nothing` | `tests/test_rpc.py` | The table size is unchanged after each rejected `queens.open`. |
| `ParamsTests.test_next_returns_at_most_limit` | `tests/test_rpc.py` | `limit` 1 returns 1 event and `limit` 32 returns 32 events mid-stream, and fewer at the end of the stream. |
| `HttpLazinessTests.test_open_and_next_force_only_what_is_returned` | `tests/test_http_flow.py` | The interpreter call counter around real HTTP calls shows `open` forces nothing and `next(limit=k)` leaves event `k+1` unforced. |

### R9. Full HTTP flow (Assign08 #9)

| Test | File | What it shows |
| --- | --- | --- |
| `FullFlowTests.test_size8_http_open_to_done` | `tests/test_http_flow.py` | On a real local socket server: `open`, then `next` with limit 32 until `done: true`. 33,589 events in 1,050 requests, only the last one short; 92 valid, distinct solutions in reference order; `done` once and last; and the events equal the solver's own trace exactly. |
| `FullFlowTests.test_repeated_terminal_reads_then_close` | `tests/test_http_flow.py` | Empty `done: true` reads repeat, then `close` gives `{"closed": true}`, then `-32020`. |

### R10. Browser client (Assign08 #10)

The playback tests replay the solver's real 4×4 trace from
`tests/js/fixtures/size4-trace.json` through a fake server that can hold
responses back, so each test decides exactly when a request completes.

| Test | File | What it shows |
| --- | --- | --- |
| `applyEvent handles each kind` | `tests/js/player.test.mjs` | For `try`, `place`, `reject`, `backtrack`, `solution` and `done`: the committed board comes from the snapshot, the candidate is kept apart, and the status sentences are exact. |
| `explainReject finds column and both diagonals` | `tests/js/player.test.mjs` | Nearest attacker first, the reason, and the squares between; every rejection in the real trace is explained. |
| `step shows one event with limit 1` | `tests/js/player.test.mjs` | Step opens a stream once, then sends one `queens.next` with `limit: 1` per press. |
| `play schedules and pause stops consumption` | `tests/js/player.test.mjs` | Fake timers: one event per tick, a new speed applies from the next tick, and nothing is requested after Pause. |
| `pause while a request is in flight buffers the event instead of losing it` | `tests/js/player.test.mjs` | The late event is buffered and shown by the next Step without a new request. |
| `play pressed during a pending step keeps playing` | `tests/js/player.test.mjs` | Playback starts once the pending Step finishes. |
| `next solution stops at solution and buffers the rest` | `tests/js/player.test.mjs` | Batches of 32, a stop right after the `solution`, leftovers shown by later Steps. |
| `pause at solutions stops playback on a solution` | `tests/js/player.test.mjs` | With the option on, Play pauses at the first solution. |
| `done disables playback and enables restart` | `tests/js/player.test.mjs` | All 139 events, 2 solutions, the finished stream closed, Step/Play/Next solution inert, and Restart opening a fresh stream. |
| `reset closes the stream and ignores stale responses` | `tests/js/player.test.mjs` | Reset sends `queens.close`, and a `next` answered after Reset changes nothing. |
| `stale open result is closed` | `tests/js/player.test.mjs` | A stream opened for a search that was reset gets `queens.close`. |
| `only one request in flight` | `tests/js/player.test.mjs` | Repeated Step and Next solution presses while a request is pending send nothing. |
| `transport and RPC errors are visible and recoverable` | `tests/js/player.test.mjs` | Network failure, expired stream and internal error each give mode `error` with a message saying what to do; Restart then works. |
| `event log is bounded` | `tests/js/player.test.mjs` | The log keeps the latest 200 entries. |
| `speed slider maps to delays from 1000 ms to 10 ms` | `tests/js/player.test.mjs` | The slider's range, and faster never means slower. |
| `rpc client sends JSON-RPC 2.0 requests with increasing ids` | `tests/js/transport.test.mjs` | Exact request bodies, `POST`, `Content-Type: application/json`. |
| `rpc client maps errors` | `tests/js/transport.test.mjs` | A JSON-RPC error gives `RpcError`; a network failure, non-200 status, non-JSON or `null` body, or mismatched `id` gives `TransportError`. |
| `AdapterTests.test_client_fixture_matches_solver` | `tests/test_adapter.py` | The fixture the client tests replay is exactly the solver's 4×4 trace. |
| `TransportTests.test_static_client_is_served` | `tests/test_rpc.py` | `GET /` serves the page; it and every module it imports are served locally with the right media type, and no file references a remote URL. |
| Browser checklist B1–B12 | `tests/browser/checklist.mjs` | The [checklist](#2-browser-checklist) run in headless Chrome against the real server, by clicking the page's controls: 27 checks, plus no JavaScript errors. |

### R11. Reproducibility and submission hygiene

| Check | What it shows |
| --- | --- |
| Clean-environment rerun | A fresh virtual environment outside the submission, set up from `requirements.txt`, runs the exact README commands. |
| Required documents | `DESIGN.md`, `README.md`, `TESTING.md` and `AI-TRANSCRIPT.md` are present and consistent with the code. |
| Scope audit | Changes are confined to `assigns/08/MySolution/`, with no virtual environment, caches or runtime state committed, and instructor files untouched. |

## 2. Browser checklist

`tests/browser/checklist.mjs` runs every step below in headless Chrome
against the real server. Each step can also be done by hand at
`http://127.0.0.1:8000/`.

| # | Step | Expected |
| --- | --- | --- |
| B1 | Load the page. | An empty 8×8 board, every control labeled, mode idle, 0 solutions. |
| B2 | Press Step three times. | `try(0,0)`, then `place(0,0)`, then `try(0,1)`. The candidate is distinct from committed queens, and the status text matches each event. |
| B3 | Keep stepping to the first reject. | Red ✕ on the candidate, attacker outlined, and text naming same column or diagonal. |
| B4 | Press Play, then Pause. | Animation advances at the slider speed and stops promptly. No further requests while paused (Network panel). |
| B5 | Change the speed while playing. | The delay changes on the next tick. |
| B6 | Press Next solution. | Stops on solution 1, `[0,4,7,5,2,6,1,3]`, with gold styling and counter 1. Step continues with `backtrack(3,7)`. |
| B7 | Observe a backtrack. | Purple ↩ on the removed square, and the board restored. |
| B8 | Press Reset mid-search. | Board, counters and log cleared. Network shows `queens.close`. No late repaint. |
| B9 | Choose size 4 and press Start (pause at solutions off). | Runs to completion: 2 solutions, a distinct "Search complete" banner, Start labeled Restart. |
| B10 | Stop the server, then press Step. | A visible error message. After restarting the server, Restart works. |
| B11 | Keyboard only (Tab, Enter or Space). | Every control is reachable, with a visible focus ring and clearly disabled states. |
| B12 | Narrow the window to about 400 px wide. | The board stays legible, controls stack, and there is no horizontal scroll. |

## 3. Results

Observed on 2026-11-19 on macOS 27.0.1 (arm64) with Python 3.14.10,
Flask 3.1.3, Node 26.13.1 and Chrome 158.0.8127.37. The commands were run
exactly as written in [README.md](README.md), from a fresh copy of
`assigns/08/` with a newly created virtual environment.

| Command | Observed |
| --- | --- |
| `MySolution/.venv/bin/python -B -m unittest discover -s MySolution/tests -t . -v` | `Ran 79 tests in 49.657s`, `OK` |
| `node --test MySolution/tests/js/` | 17 tests, 17 passed, 0 failed |
| `node MySolution/tests/browser/checklist.mjs` | `27/27 browser checks passed` in about 14 s, with no JavaScript errors in the page |
| The `curl` examples in README.md, against `python -m MySolution` | Every answer was exactly as documented (`queens.open` apart from its new UUID) |

Values the tests assert, as observed:

- **4×4:** 139 events; solutions `[1,3,0,2]` then `[2,0,3,1]`.
- **8×8:** 33,589 events: 15,720 `try`, 13,664 `reject`, 2,056 `place`,
  2,056 `backtrack`, 92 `solution` and 1 `done` (last). The 92 solutions are
  valid, distinct and in lexicographic order, and two fresh streams give
  identical traces. The first solution, `[0,4,7,5,2,6,1,3]`, is event 1,858.
  Over HTTP the whole stream took 1,050 requests with `limit: 32`, and the
  events equal the solver's own trace.
- **Laziness:** opening a stream makes exactly one interpreter application
  (`queens_stream` itself) and no `search` call; forcing the first event
  makes one `search` call and no `check_safe` call; after `k` events the next
  cell is still unevaluated for sizes 8, 9 and 10; delivered cells are freed;
  5,000 events of a 10×10 stream run under a lowered recursion limit.

Gaps:

- Only macOS was tested. Linux and Windows were not run.
- The browser checklist was run by automation in headless Chrome, not
  repeated by hand. Its screenshots were reviewed for appearance at laptop
  width and at 400 px.
- `StreamTableTests.test_concurrent_next_has_no_duplicates_or_gaps` slows
  each read to make races likely; like any concurrency test, it can show a
  race but cannot prove there is none.
