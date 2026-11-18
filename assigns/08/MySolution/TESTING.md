# Assignment 08 testing

**Status: plan only (Stage 1).** No submission test has been run yet. Every row
below is marked **not run**. Test names are the planned names. Later stages
will update this file with the actual names, commands and observed results,
and will mark any gaps.

The only evidence so far comes from a throwaway prototype run before the
design was written. It lives outside the repository and is not a submission
test. Its results are quoted in [DESIGN.md §3.7](DESIGN.md#37-order-uniqueness-and-termination)
and [§4.3](DESIGN.md#43-bounded-work-and-bounded-stack).

## Planned commands

All commands run from `assigns/08/`.

| Suite | Command (planned) |
| --- | --- |
| Python: solver, adapter, stream table, RPC over HTTP | `MySolution/.venv/bin/python -B -m unittest discover -s MySolution/tests -t . -v` |
| Client logic (Node built-in test runner, no packages) | `node --test MySolution/tests/js/` |
| Browser behavior | The manual checklist in [section 3](#3-browser-checklist), plus browser automation if it is available. |

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
- Exhausting the 8×8 search takes about 13 s in the interpreter, so each
  suite that needs the full trace computes it once per class
  (`setUpClass`).

## 1. Requirement-to-test map

The **Assign08 #** column refers to the numbered "Required tests" list in
`Assign08.md`.

### R1. Safety checks (Assign08 #1)

| Planned test | File | What it shows | Status |
| --- | --- | --- | --- |
| `SafetyTests.test_attacks_same_row` | `tests/test_solver.py` | `queens_attacks` (run in LAMBDA3) detects two squares in one row. | not run |
| `SafetyTests.test_attacks_same_column` | `tests/test_solver.py` | Same column detected. | not run |
| `SafetyTests.test_attacks_down_right_diagonal` | `tests/test_solver.py` | Diagonal where `row − col` is equal. | not run |
| `SafetyTests.test_attacks_down_left_diagonal` | `tests/test_solver.py` | Anti-diagonal where `row + col` is equal. | not run |
| `SafetyTests.test_attacks_safe_pair` | `tests/test_solver.py` | A knight's-move pair and other safe pairs are not attacks. | not run |
| `SafetyTests.test_check_safe_calls_on_safe` | `tests/test_solver.py` | `queens_check_safe` at answer type `sint` takes the safe continuation for a safe candidate against a multi-queen board. | not run |
| `SafetyTests.test_check_safe_conflicts_column_and_both_diagonals` | `tests/test_solver.py` | Takes the conflict continuation for a column conflict and for each diagonal direction, including against a queen several rows back. | not run |
| `SafetyTests.test_check_safe_stops_at_first_conflict` | `tests/test_solver.py` | The call counter shows recursion stops at the nearest conflict. | not run |
| `EventTests.test_one_queen_per_row_invariant` | `tests/test_solver.py` | Every event board satisfies the partial-board invariant ([DESIGN.md §3.3](DESIGN.md#33-search-state-and-the-partial-board-invariant)). This covers the assignment's "same row" wording. | not run |

### R2. CPS success and failure paths (Assign08 #2)

| Planned test | File | What it shows | Status |
| --- | --- | --- | --- |
| `CpsTests.test_complete_board_calls_success_with_resume` | `tests/test_solver.py` | `queens_search` with `row = n` calls the success continuation with the board, and the `resume` it receives is the given failure continuation. | not run |
| `CpsTests.test_exhausted_row_calls_failure` | `tests/test_solver.py` | A dead-end state calls its failure continuation, observed through a marker event emitted by a test continuation. | not run |
| `CpsTests.test_reject_resumes_at_next_column` | `tests/test_solver.py` | In the trace, every `reject(c, r)` is followed by `try(c+1, r)` or by the row's failure continuation. | not run |
| `CpsTests.test_backtrack_resumes_at_next_column_in_parent_row` | `tests/test_solver.py` | Every `backtrack(c, r)` is followed by `try(c+1, r)`, by the parent's `backtrack`, or by `done`. | not run |
| `CpsTests.test_solution_resumes_with_backtrack_of_last_row` | `tests/test_solver.py` | After each `solution`, the next event is `backtrack(c, n-1)` with the restored board. | not run |
| Source review: no direct-style search | `DESIGN.md` §3.6, `solver.lam` | The continuations decide every next action, and the safety check returns no Boolean to the search. Recorded as a review item. | not run |

### R3. Exhaustive deterministic search (Assign08 #3)

| Planned test | File | What it shows | Status |
| --- | --- | --- | --- |
| `ExhaustiveSearchTests.test_size4_reference_trace` | `tests/test_solver.py` | Exact opening events and solutions `[1,3,0,2]`, `[2,0,3,1]` in that order. | not run |
| `ExhaustiveSearchTests.test_size8_has_92_valid_unique_solutions` | `tests/test_solver.py` | 92 solutions, each checked by an independent Python validator, with no duplicates. | not run |
| `ExhaustiveSearchTests.test_size8_lexicographic_dfs_order` | `tests/test_solver.py` | The order matches a test-only reference enumerator. | not run |
| `ExhaustiveSearchTests.test_size8_deterministic_across_fresh_streams` | `tests/test_solver.py` | Two independently opened streams give identical event sequences. | not run |
| `ExhaustiveSearchTests.test_small_size_solution_counts` | `tests/test_solver.py` | Sizes 4, 5 and 6 give 2, 10 and 4 solutions. | not run |

### R4. Event kinds, coordinates and snapshots (Assign08 #4)

| Planned test | File | What it shows | Status |
| --- | --- | --- | --- |
| `EventTests.test_all_event_kinds_present` | `tests/test_solver.py` | All six kinds occur in the 8×8 trace. | not run |
| `EventTests.test_snapshot_semantics` | `tests/test_solver.py` | `try`, `reject` and `backtrack` carry the parent board. `place` carries the parent board plus `column`. `solution` carries a complete board equal to the preceding `place`. | not run |
| `EventTests.test_every_reject_has_an_attacking_queen` | `tests/test_solver.py` | Each rejection is justified by the board. | not run |
| `EventTests.test_done_exactly_once_and_last` | `tests/test_solver.py` | Exactly one `done`, and it is the final event. | not run |
| `AdapterTests.test_event_json_fields_and_row_order` | `tests/test_adapter.py` | Each kind's JSON has exactly its documented keys, with no internal tag or `-1` sentinel, and boards in row order. | not run |

### R5. Lazy construction and bounded demand (Assign08 #5)

| Planned test | File | What it shows | Status |
| --- | --- | --- | --- |
| `LazinessTests.test_construction_applies_no_search` | `tests/test_laziness.py` | `queens_stream(8)` and `open_stream(8)` cause zero `search` and `check_safe` applications, and the root is unevaluated. | not run |
| `LazinessTests.test_forcing_one_cell_leaves_tail_unforced` | `tests/test_laziness.py` | One force gives `try(0,0,[])`, its tail is unevaluated, and the call counts are bounded. | not run |
| `LazinessTests.test_bounded_prefix_sizes_8_9_10` | `tests/test_laziness.py` | After taking `k` events (`k` = 1, 10, 50), the stored cursor is unevaluated and the call counts grow with `k`, not with the search tree. | not run |
| `LazinessTests.test_unread_failing_tail_is_never_run` | `tests/test_laziness.py` | `take` on a stream whose second cell raises returns the first event without error. | not run |
| `LazinessTests.test_take_stops_at_done_without_forcing_its_tail` | `tests/test_laziness.py` | Taking past `done` never forces the tail after `done`. | not run |
| `LazinessTests.test_delivered_cells_are_released` | `tests/test_laziness.py` | A weak reference to an already-delivered cell dies after the cursor advances. | not run |
| `LazinessTests.test_stack_depth_stays_bounded` | `tests/test_laziness.py` | A long prefix succeeds under a lowered recursion limit, so continuations do not pile up on the stack. | not run |
| `AdapterTests.test_imports_assignment_08_lambda3` | `tests/test_adapter.py` | `lambda3.__file__` is inside `assigns/08/LAMBDA3`. | not run |

### R6. Stream lifecycle (Assign08 #6)

| Planned test | File | What it shows | Status |
| --- | --- | --- | --- |
| `StreamTableTests.test_open_returns_uuid_and_does_not_force` | `tests/test_streams.py` | A UUID4 string, and the cursor is unevaluated. | not run |
| `StreamTableTests.test_streams_are_independent` | `tests/test_streams.py` | Interleaved reads of two streams match the separate sequences, with no shared cursor. | not run |
| `StreamTableTests.test_next_never_forces_beyond_limit` | `tests/test_streams.py` | After `next(limit=k)` the stored cursor is unevaluated. Covers exact boundary and terminal cases. | not run |
| `StreamTableTests.test_exhaustion_releases_solver_state` | `tests/test_streams.py` | After `done`, the cursor is `None` and a small exhausted record remains. | not run |
| `StreamTableTests.test_repeated_next_after_exhaustion` | `tests/test_streams.py` | `{"events": [], "done": true}` repeatedly. | not run |
| `StreamTableTests.test_close_then_next_is_stream_not_found` | `tests/test_streams.py` | `-32020` after close, and also when closing twice. | not run |
| `StreamTableTests.test_unknown_id_is_stream_not_found` | `tests/test_streams.py` | `-32020`. | not run |
| `StreamTableTests.test_active_stream_expires_after_ttl` | `tests/test_streams.py` | Fake clock: live at `TTL − ε`, `-32020` at `TTL`. | not run |
| `StreamTableTests.test_activity_refreshes_deadline` | `tests/test_streams.py` | A `next` moves `expires_at`. | not run |
| `StreamTableTests.test_exhausted_record_expires` | `tests/test_streams.py` | Repeated empty reads work until the TTL passes, then `-32020`. | not run |
| `StreamTableTests.test_sweep_reclaims_expired_entries` | `tests/test_streams.py` | Expired entries leave the table at the next operation. | not run |
| `StreamTableTests.test_open_limit` | `tests/test_streams.py` | The 65th open gets `-32021`, and nothing is allocated. | not run |
| `StreamTableTests.test_internal_failure_removes_stream` | `tests/test_streams.py` | An injected forcing failure gives `-32603`, and the ID then reports `-32020`. | not run |
| `StreamTableTests.test_concurrent_next_has_no_duplicates_or_gaps` | `tests/test_streams.py` | Threads reading one stream together reproduce the sequential sequence exactly. | not run |

### R7. JSON-RPC envelope, methods, params, notifications, errors (Assign08 #7)

All of these go through the Flask test client, so they exercise the real HTTP
layer.

| Planned test | File | What it shows | Status |
| --- | --- | --- | --- |
| `EnvelopeTests.test_ids_are_echoed` | `tests/test_rpc.py` | `0`, `-1`, `"abc"`, `""`, `1.5` and `null` are echoed exactly. | not run |
| `EnvelopeTests.test_invalid_envelopes` | `tests/test_rpc.py` | Bad `jsonrpc`, missing or non-string `method`, scalar `params`, boolean or object `id`, an extra member, or a non-object body: `-32600` with `id: null`, HTTP 200. | not run |
| `EnvelopeTests.test_invalid_request_without_id_still_answered` | `tests/test_rpc.py` | HTTP 200 with a `-32600` body, not 204. | not run |
| `EnvelopeTests.test_parse_errors` | `tests/test_rpc.py` | Malformed JSON, invalid UTF-8, `NaN`: `-32700`, `id: null`. | not run |
| `EnvelopeTests.test_batches_not_supported` | `tests/test_rpc.py` | Empty and non-empty arrays: `-32600` with `batch_not_supported`, and no stream state changes. | not run |
| `MethodTests.test_health` | `tests/test_rpc.py` | Exact result, with params omitted or `{}`. | not run |
| `MethodTests.test_unknown_methods` | `tests/test_rpc.py` | `queens.reset`, `lambda.interpret`, `__init__` and `""` all give `-32601`. | not run |
| `MethodTests.test_open_next_close_round_trip` | `tests/test_rpc.py` | Each method's result shape matches [DESIGN.md §7.3](DESIGN.md#73-methods-and-parameters). | not run |
| `NotificationTests.test_valid_notification_changes_state_and_returns_204` | `tests/test_rpc.py` | A notification `queens.next` advances the stream (the next call sees the following event), with 204, an empty body and no `Content-Type`. | not run |
| `NotificationTests.test_failing_notifications_return_204` | `tests/test_rpc.py` | An unknown method, invalid params or an unknown stream as a notification gives 204. | not run |
| `ErrorTests.test_stream_not_found_application_error` | `tests/test_rpc.py` | `-32020` for unknown, closed and expired IDs (expired via an injected clock). | not run |
| `ErrorTests.test_internal_error_is_sanitized` | `tests/test_rpc.py` | An injected exception gives `-32603` with only an incident ID: no traceback, path or Python type name. | not run |
| `TransportTests.test_media_type_and_method_checks` | `tests/test_rpc.py` | Wrong `Content-Type` gives 415, `GET /rpc` gives 405, and an oversized body gives 413, all as plain text. | not run |
| `TransportTests.test_static_client_is_served` | `tests/test_rpc.py` | `GET /` serves HTML and `GET /static/js/player.js` serves JavaScript. | not run |

### R8. Parameter boundaries and `limit` (Assign08 #8)

| Planned test | File | What it shows | Status |
| --- | --- | --- | --- |
| `ParamsTests.test_size_bounds` | `tests/test_rpc.py` | 4 and 10 accepted. 3, 11, `8.0`, `true`, `"8"`, `null` and a missing size give `-32602`. | not run |
| `ParamsTests.test_limit_bounds` | `tests/test_rpc.py` | 1 and 32 accepted. 0, 33, `1.5`, `true`, `"1"` and a missing limit give `-32602`. | not run |
| `ParamsTests.test_shape_errors` | `tests/test_rpc.py` | Array `params`, unknown keys, a non-string `stream_id`, and params omitted for `queens.*` give `-32602`. | not run |
| `ParamsTests.test_invalid_params_allocate_nothing` | `tests/test_rpc.py` | The table size is unchanged after each rejected `queens.open`. | not run |
| `ParamsTests.test_next_returns_at_most_limit` | `tests/test_rpc.py` | `limit` 1 returns 1 event and `limit` 32 returns 32 events mid-stream, and fewer at the end of the stream. | not run |
| `HttpLazinessTests.test_open_and_next_force_only_what_is_returned` | `tests/test_http_flow.py` | The interpreter call counter around real HTTP calls shows `open` forces nothing and `next(limit=k)` leaves event `k+1` unforced. | not run |

### R9. Full HTTP flow (Assign08 #9)

| Planned test | File | What it shows | Status |
| --- | --- | --- | --- |
| `FullFlowTests.test_size8_http_open_to_done` | `tests/test_http_flow.py` | `open`, then `next` with limit 32 until `done: true`: 33,589 events, 92 valid, distinct, ordered solutions, `done` once and last. | not run |
| `FullFlowTests.test_repeated_terminal_reads_then_close` | `tests/test_http_flow.py` | Empty `done: true` reads repeat, then `close` gives `{"closed": true}`, then `-32020`. | not run |

### R10. Browser client logic (Assign08 #10, automated part)

| Planned test | File | What it shows | Status |
| --- | --- | --- | --- |
| `applyEvent handles each kind` | `tests/js/player.test.mjs` | Committed board, candidate and highlight for `try`, `place`, `reject`, `backtrack`, `solution` and `done`. | not run |
| `explainReject finds column and both diagonals` | `tests/js/player.test.mjs` | Nearest-first attacker and reason text. | not run |
| `step shows one event with limit 1` | `tests/js/player.test.mjs` | One `queens.next` with `limit: 1` per step. | not run |
| `play schedules and pause stops consumption` | `tests/js/player.test.mjs` | Fake timer: no requests after Pause, and an in-flight event is buffered, not lost. | not run |
| `next solution stops at solution and buffers the rest` | `tests/js/player.test.mjs` | Batches of 32, stop right after `solution`, leftovers shown by a later Step. | not run |
| `done disables playback and enables restart` | `tests/js/player.test.mjs` | Mode `done`, and the solution count is kept. | not run |
| `reset closes the stream and ignores stale responses` | `tests/js/player.test.mjs` | A deferred `next` that resolves after Reset changes nothing. | not run |
| `stale open result is closed` | `tests/js/player.test.mjs` | An orphaned stream ID gets `queens.close`. | not run |
| `only one request in flight` | `tests/js/player.test.mjs` | Repeated Step while pending sends one request. | not run |
| `transport and RPC errors are visible and recoverable` | `tests/js/player.test.mjs` | Mode `error` with a message, then Start opens a fresh stream. | not run |
| `event log is bounded` | `tests/js/player.test.mjs` | The log never exceeds 200 entries. | not run |
| `rpc client maps errors` | `tests/js/transport.test.mjs` | A JSON-RPC error gives `RpcError`, and a network failure, non-200 status or non-JSON body gives `TransportError`. Request IDs increase. | not run |

### R11. Reproducibility and submission hygiene

| Planned check | What it shows | Status |
| --- | --- | --- |
| Clean-environment rerun | A fresh virtual environment outside the submission, set up from `requirements.txt`, runs the exact README commands. | not run |
| Required documents | `DESIGN.md`, `README.md`, `TESTING.md` and `AI-TRANSCRIPT.md` are present and consistent with the code. | not run |
| Scope audit | Changes are confined to `assigns/08/MySolution/`, with no virtual environment, caches or runtime state committed, and instructor files untouched. | not run |

## 2. Results

None yet. Each later stage will record the command it ran, the date, the
counts it observed, and any failures here.

## 3. Browser checklist

This checklist is run manually against the real server (or with browser
automation when available) at `http://127.0.0.1:8000/`. Results will be
recorded here. Every item is **not run**.

| # | Step | Expected | Status |
| --- | --- | --- | --- |
| B1 | Load the page. | An empty 8×8 board, every control labeled, mode idle, 0 solutions. | not run |
| B2 | Press Step three times. | `try(0,0)`, then `place(0,0)`, then `try(0,1)`. The candidate is distinct from committed queens, and the status text matches each event. | not run |
| B3 | Keep stepping to the first reject. | Red ✕ on the candidate, attacker outlined, and text naming same column or diagonal. | not run |
| B4 | Press Play, then Pause. | Animation advances at the slider speed and stops promptly. No further requests while paused (Network panel). | not run |
| B5 | Change the speed while playing. | The delay changes on the next tick. | not run |
| B6 | Press Next solution. | Stops on solution 1, `[0,4,7,5,2,6,1,3]`, with gold styling and counter 1. Step continues with `backtrack(3,7)`. | not run |
| B7 | Observe a backtrack. | Purple ↩ on the removed square, and the board restored. | not run |
| B8 | Press Reset mid-search. | Board, counters and log cleared. Network shows `queens.close`. No late repaint. | not run |
| B9 | Choose size 4 and press Start (pause at solutions off). | Runs to completion: 2 solutions, a distinct "Search complete" banner, Start labeled Restart. | not run |
| B10 | Stop the server, then press Step. | A visible error message. After restarting the server, Restart works. | not run |
| B11 | Keyboard only (Tab, Enter or Space). | Every control is reachable, with a visible focus ring and clearly disabled states. | not run |
| B12 | Narrow the window to about 400 px wide. | The board stays legible, controls stack, and there is no horizontal scroll. | not run |
