# Testing — LAMBDA3 JSON-RPC Service

This file maps each required behavior to the tests that check it, and records
observed results. The contract being tested is [`RPC.md`](RPC.md).

**Status:** every row below was last run on 2026-11-10 with the commands
below, and every row passed.

## Commands

All commands run from `assigns/07/` with Python 3.12 or later.

```sh
# Setup
python3 -m venv MySolution/.venv
MySolution/.venv/bin/python -m pip install -r MySolution/requirements.txt

# Local HTTP-level suite (Flask test client; real LAMBDA3 and real worker processes)
MySolution/.venv/bin/python -m unittest discover -s MySolution/tests -t . -v

# Start the service, then run the instructor's black-box suite from a second terminal
# (options: --deadline SECONDS, default 2.0; --max-source-bytes N, default 65536)
MySolution/.venv/bin/python -m MySolution --host 127.0.0.1 --port 8000
python3 -m unittest discover -s TEST -v

# The same suite against a server on another port
LAMBDA_RPC_URL=http://127.0.0.1:9000/rpc python3 -m unittest discover -s TEST -v
```

The two suites complement each other. The instructor suite (`../TEST/`) checks
the shared contract against a live server. It does not cover deadlines or the
limits each implementation chooses. The local suite covers those, along with
injected failures, transport statuses and the edge cases in `RPC.md`.

## Architecture

```text
HTTP client ──POST /rpc──▶ Transport (Flask app)
                             │  404/405/415/413; strict UTF-8 JSON decode
                             ▼
                           JSON-RPC dispatcher
                             │  envelope, IDs, notifications, batches,
                             │  method table, response objects, HTTP 200/204
                             ▼
                           Service adapter
                             │  params rules, source limit, error-code mapping
                             │  (service.health answered here)
             ═══════ process boundary: spawned worker, deadline, terminate → kill → join ═══════
                             ▼
                           Worker process ──▶ LAMBDA3 (../LAMBDA3/lambda3.py + basics0.py)
                              parse + type-check, then format_type /
                              evaluate + d0val_format / compile (Python or JS)
```

Test doubles are used only at the process boundary, to inject failures: a
worker that raises, one that crashes, and one that blocks. Every successful
type check, interpretation and compilation in the suite runs the real
LAMBDA3 code in a real worker process.

Every HTTP 200 body the local suite receives is also validated against
`rpc.schema.json#/$defs/ResponseBody`.

## Acceptance matrix

Test names are `module.Class.method` under `MySolution/tests/`.

### Required behaviors (Assign07, Task 3)

| # | Required behavior | Tests | Status |
| --- | --- | --- | --- |
| 1 | `service.health` returns status and API version and keeps the request id | `test_methods.HealthTests.test_health_result_and_id`, `test_envelope.IdTests.test_valid_ids_are_echoed_unchanged` | Passed |
| 2 | Type-checking valid programs returns the formatted type | `test_methods.TypecheckTests.test_formatted_types` (`sint`, `bool`, a tuple, `List[sint]`, `sint -> sint`, an unresolved `?t0 -> ?t0`, the factorial program), `.test_typecheck_does_not_evaluate` | Passed |
| 3 | Interpreting arithmetic, factorial, a tuple and a collection gives the right value and type | `test_methods.InterpretTests.test_arithmetic`, `.test_factorial` (720), `.test_tuple`, `.test_list`, `.test_array_and_option`, `.test_supplied_list_library` (source built from `mylib/list.lam`) | Passed |
| 4 | Python and JavaScript compilation return nonempty source and the right `target` | `test_methods.CompileTests.test_code_is_the_unchanged_compiler_output` (four programs, both targets, each equal to the output of LAMBDA3's compiler called directly in a separate Python process), `.test_both_targets_return_nonempty_programs`, `.test_compile_does_not_evaluate` (`1 / 0` and `fib(26)` compile), `.test_output_larger_than_a_pipe_buffer` | Passed |
| 5 | Syntax errors and type errors have distinct documented codes | `test_language_errors.LanguageErrorTests.test_syntax_error_has_diagnostic_and_location`, `.test_type_error`, `.test_syntax_and_type_errors_have_distinct_codes` | Passed |
| 6 | Malformed JSON, invalid envelopes, unknown methods, absent or wrongly typed params, blank source and oversized source | `test_envelope.ParseErrorTests.*`, `test_envelope.InvalidRequestTests.*`, `test_envelope.MethodNotFoundTests.*`, `test_params.ParamsTests.*`, `test_params.SourceParamsTests.*`, `test_params.TargetParamsTests.*`, `test_params.SourceLimitTests.*` | Passed |
| 7 | A function result is formatted without closure internals | `test_methods.InterpretTests.test_function_values_are_formatted_without_internals` (`<lam>`, `<fix>`) | Passed |
| 8 | An injected backend failure or timeout returns the documented error, keeps the id, and shows no traceback | `test_failures.BackendExceptionTests.test_unexpected_backend_exception_in_the_worker`, `test_failures.CrashedWorkerTests.test_worker_that_exits_without_an_outcome` (both: `-32603` with the id, and the response has no `Traceback`, no injected exception name or message, no `.py` file name and no `/Users` path), `test_failures.HungWorkerTests.test_hung_worker_is_killed_and_the_call_times_out`, `test_failures.TimeoutTests.test_slow_interpretation_times_out`, `.test_service_answers_after_a_timeout` | Passed |
| 9 | LAMBDA3 type checking rejects an unbound variable | `test_language_errors.LanguageErrorTests.test_unbound_variable_is_a_type_error` | Passed |
| 10 | Batches keep IDs and omit notifications; invalid members get `id: null`; a notification-only batch and a single notification get 204 with an empty body; an empty batch gets one Invalid Request object | `test_batches.BatchTests.*`, `test_batches.BatchProcessingTests.*`, `test_envelope.NotificationTests.test_single_notification_is_204_empty`, `test_transport.TransportTests.test_notification_is_204_with_zero_byte_body` | Passed |

### Contract details (`RPC.md`)

| Behavior | `RPC.md` | Tests | Status |
| --- | --- | --- | --- |
| 404 / 405 (with `Allow: POST`) / 415 / 413 in that order; text bodies on transport errors; JSON media type on 200; zero-byte 204 with no `Content-Type` | §1 | `test_transport.TransportTests.*` | Passed |
| Parse errors: truncated JSON, invalid UTF-8, BOM, `NaN`/`Infinity`, `1e400`, a 4,301-digit integer, deeply nested arrays, empty body | §1, §4 | `test_envelope.ParseErrorTests.*` | Passed |
| Each `-32600` reason, including a usable id that is not echoed and a top-level scalar | §2, §4 | `test_envelope.InvalidRequestTests.*` | Passed |
| IDs `""`, `0`, negative, fractional, large integer (up to 4,300 digits) and explicit `null` are echoed with the same JSON type; boolean, object and array IDs are rejected | §2 | `test_envelope.IdTests.*` | Passed |
| Notifications are processed; with an unknown method, bad params, a documented error or an internal error they still produce no response | §2 | `test_envelope.NotificationTests.*` | Passed |
| Dispatcher boundary: params passed through as sent; a documented error from a method keeps the id and data | §2, §4 | `test_envelope.DispatchBoundaryTests.*` (test double for the method table) | Passed |
| Params: missing, positional and scalar `params`; unexpected keys for every method; `source` missing, wrong type, unpaired surrogate or blank; `source` checked before `target`; `target` missing, wrong type or wrong case | §3 | `test_params.ParamsTests.*`, `test_params.SourceParamsTests.*`, `test_params.TargetParamsTests.*`, `test_envelope.InvalidRequestTests.test_bad_params` | Passed |
| Source limit: 65,536 bytes accepted and 65,537 rejected; 2-byte characters counted as bytes, at and past the limit; size checked before blankness; the limit taken from the app config | §3, §5 | `test_params.SourceLimitTests.*`, `test_params.ConfiguredSourceLimitTests.*` | Passed |
| A source reaches LAMBDA3 unchanged: no trimming, so syntax-error positions count the original text | §3 | `test_methods.InterpretTests.test_source_is_used_unchanged`, `test_language_errors.LanguageErrorTests.test_syntax_error_location_counts_the_unchanged_source` | Passed |
| Runtime errors get `-32013`: division by zero, empty-list head, empty option, array index, negative array size, an integer too long to format | §4 | `test_language_errors.LanguageErrorTests.test_runtime_errors`, `.test_integer_too_long_to_format_is_a_runtime_error` | Passed |
| Python's limits get fixed diagnostics: nesting too deep for the parser (`-32010`) or the type checker (`-32011`), an overlong integer literal (`-32010`), recursion too deep at run time (`-32013`); none is reported as a timeout | §4 | `test_language_errors.LanguageErrorTests.test_too_deeply_nested_source_is_a_syntax_error`, `.test_too_deeply_nested_for_the_type_checker_is_a_type_error`, `.test_overlong_integer_literal_is_a_syntax_error`, `.test_recursion_limit_is_a_runtime_error` | Passed |
| Diagnostics are capped at 1,000 characters | §4 | `test_language_errors.LanguageErrorTests.test_long_diagnostic_is_cut_to_1000_characters` | Passed |
| Internal errors log details under the `incident` value and keep them out of the response | §4 | `test_envelope.DispatchBoundaryTests.test_unexpected_exception_is_logged_not_returned` (dispatcher), `test_failures.CrashedWorkerTests.*` and `test_failures.BackendExceptionTests.*` (worker; the failure is injected inside the spawned process) | Passed |
| Deadline: a slow program and an exponential type check both get `-32012` after the deadline; a worker that ignores SIGTERM is killed and reaped; the deadline is taken from the app config; a notification runs under the same deadline; the service answers normally after a timeout | §5 | `test_failures.TimeoutTests.*`, `test_failures.ConfiguredDeadlineTests.*`, `test_failures.HungWorkerTests.*` | Passed |
| Output from `print` is discarded (the worker's inherited standard output is captured and checked); only the value is returned | §3 | `test_methods.InterpretTests.test_print_output_is_discarded` | Passed |
| Batch edge cases: 20 members accepted; 21 rejected with nothing run; duplicate IDs both answered; nested-array and scalar members; members run in order; one member's failure doesn't affect the others | §6 | `test_batches.BatchTests.*`, `test_batches.BatchProcessingTests.*` | Passed |
| The schema is valid; the fixtures and every `RPC.md` response validate; the invalid `RPC.md` requests are rejected; result+error is rejected | §8 | `test_schema.SchemaTests.*` | Passed |
| Every `RPC.md` §7 exchange gives the documented status and body: all 19 examples are read from `RPC.md` itself and replayed. Bodies are compared with `1`, `1.0` and `true` kept distinct, batch entries are matched in any order, and the two abbreviated compile responses are compared with their `examples/` files and documented lengths | §7 | `test_examples.RpcMdExampleTests.test_documented_exchanges` | Passed |

### Instructor black-box suite (`../TEST/test_rpc_api.py`, unchanged, against a live server)

| Test | Status (2026-11-10) |
| --- | --- |
| `test_health` | Passed |
| `test_typecheck_arithmetic` | Passed |
| `test_interpret_arithmetic` | Passed |
| `test_interpret_tuple` | Passed |
| `test_interpret_list` | Passed |
| `test_interpret_function_formats_closure` | Passed |
| `test_compile_python_and_javascript` | Passed |
| `test_language_syntax_and_type_errors_are_distinct` | Passed |
| `test_invalid_params_and_unknown_method` | Passed |
| `test_malformed_json_returns_parse_error` | Passed |
| `test_batch_matches_by_id_and_omits_notification` | Passed |
| `test_notification_only_batch_has_no_response` | Passed |
| `test_notification_has_no_response` | Passed |
| `test_invalid_request_and_empty_batch` | Passed |
| `test_malformed_batch_member_gets_null_id_error` | Passed |

## Observed results

Environment: macOS, Python 3.14.10, Flask 3.1.3, Werkzeug 3.1.9,
jsonschema 4.26.0.

**2026-11-10: the documented workflow, from a clean copy**

- **Setup:** `git archive HEAD assigns/07` was unpacked into an empty
  directory, so nothing outside the committed files was used. The commands in
  `README.md` then created a new virtual environment and installed
  `requirements.txt`, which gave Flask 3.1.3, Werkzeug 3.1.9 and
  jsonschema 4.26.0.
- **Local suite:** the documented command ran 114 tests in 16.6 s, all OK.
- **Instructor suite:** a server was started from that copy with the default
  options, and the suite passed all 15 tests against it. The server log had
  no errors, and no worker process was left afterwards.
- **README examples:** after `README.md` was finished, a script ran each
  `bash` block in its Examples section, exactly as written, against a server
  with the default options. It compared each output with the block shown
  below the command. JSON was compared as data, generated code by its
  ending, and the notification by its status line and empty body.
  - All 13 examples matched.
  - The timeout example answered after 2.01 s.
  - The service code was the same as in the clean copy; only the
    documentation had changed.
- **Recursion depth**, measured through the real worker: `fact(141)`
  evaluates and `fact(142)` gets `-32013`. A plain counting recursion
  reaches depth 140. This agrees with the "roughly 140 nested LAMBDA calls"
  in `RPC.md` §4.
- **Overlapping calls:** 8 `fib(26)` interpretations were sent to a live
  server at the same time.
  - Each got `-32012` after 2.005 to 2.008 s.
  - No worker process was left afterwards.
  - A factorial call made next returned `720`.
- **The instructor's LAMBDA3 update of 2026-11-10** (upstream commit
  `8b4974c`) adds a `%` operator, fixes the `mylib` test imports, and adds to
  `a1sz.lam`. This solution's committed files were checked against that
  LAMBDA3 in a separate copy, with no code changes:
  - The local suite ran 114 tests, all OK, including the comparison with
    LAMBDA3's compilers.
  - The instructor suite passed all 15 against a live server.
  - All four `mylib` library tests passed.
  - Through the service, `7 % 3` gave `1` and `(0 - 7) % 3` gave `2`.
    `1 % 0` gave `-32013`, and `true % 2` gave `-32011`.

**2026-11-10: acceptance run, with the `RPC.md` examples replayed**

- **Local suite:** `MySolution/.venv/bin/python -m unittest discover -s
  MySolution/tests -t . -v` ran 114 tests in about 17 s, all OK. The new
  tests are the `RPC.md` §7 replay, which includes one real 2-second timeout,
  and the comparison of compiled code with LAMBDA3's compiler called directly.
- **Mutation check of the new tests:** each change below was made in a copy
  of `MySolution/`, and `test_examples` and `test_methods` were run against
  it. The unchanged copy passed, and every change was caught.
  - `RPC.md` documenting factorial as `721`: 1 failure.
  - `RPC.md` giving the Python code's length as 4,870 characters: 1.
  - `RPC.md` giving the syntax error's column as 5: 1.
  - The `### 7.19` heading losing its number: 1.
  - The timeout's `limit_seconds` sent as the integer `2` instead of `2.0`:
    1. Only the replay catches this, because it compares JSON text;
    `test_failures` compares with `==`, where `2 == 2.0`.
  - Whitespace stripped from the compiler output: 11, counting subtests.
- **Instructor suite, unchanged, against a live server:**
  - The server was started with `MySolution/.venv/bin/python -m MySolution
    --host 127.0.0.1 --port 8000`. A `service.health` call was polled until
    it answered, and then `python3 -m unittest discover -s TEST -v` passed
    all 15 tests in 0.89 s.
  - With that server stopped, a second server on port 9000 was tested with
    `LAMBDA_RPC_URL=http://127.0.0.1:9000/rpc python3 -m unittest discover
    -s TEST -v`. All 15 passed, so the suite really did use the URL from
    `LAMBDA_RPC_URL`.
  - Neither server logged an error. Both were stopped afterwards, and no
    server or worker process was left running. `../LAMBDA3/` has no
    `__pycache__`.

**2026-11-09: all four methods, with the real LAMBDA3 in worker processes**

- **Local suite:** `MySolution/.venv/bin/python -m unittest discover -s
  MySolution/tests -t . -v` ran 113 tests in about 13 s, all OK. Most of that
  time is spent waiting out deadlines: four real timeouts, and two forced
  kills of a worker that ignores SIGTERM.
- **Mutation check:** each deliberate bug below was written into a copy of
  `MySolution/` on disk, so the spawned workers ran it too, and the full
  suite was run against that copy. The unmodified copy passed, and every bug
  was caught. Each bullet gives the failure count unittest reported (failing
  subtests count separately).
  - Diagnostics not cut to 1,000 characters: 1.
  - A type-checker overflow reported as a syntax error: 1.
  - The parent keeping its copy of the pipe's write end open (a crashed
    worker then looks like a timeout): 1.
  - Terminating a worker without the kill that follows: the suite hung and
    was stopped after 90 s, because the worker that ignores SIGTERM stayed
    alive.
  - A deadline three times too long: 2.
  - Stripping whitespace from the compiler output: 3.
  - `ValueError` from the evaluator treated as an internal error: 4.
  - Counting the source limit in characters instead of bytes: 1.
  - Comparing `target` without regard to case: 2.
  - Not discarding `print` output: 1.
- **Live server:** `python -m MySolution --host 127.0.0.1 --port 8000`.
  - The factorial program returned `{"type": "sint", "value": "720"}` in
    0.08 s.
  - `missing_name + 1` returned `-32011` with
    `unbound variable 'missing_name'`.
  - `fib(26)` returned `-32012` after 2.00 s.
  - The JavaScript compile response for `1 + 2` equalled
    `examples/compile-javascript-response.json` exactly.
  - The server log had no errors.
  - `--deadline 0` and `--max-source-bytes nan` were rejected at startup.
- **Instructor suite** (`python -m unittest discover -s TEST -v`, against
  that server): all 15 passed. The server was stopped afterwards, and no
  `__pycache__` was left in `../LAMBDA3/`.

**2026-11-09: protocol and transport, with `service.health` as the only real
method**

- **Local suite:** `MySolution/.venv/bin/python -m unittest discover -s
  MySolution/tests -t . -v` ran 62 tests in 0.3 s, all OK.
- **Mutation check:** four deliberate bugs were patched into the service in
  memory, one at a time, and each was caught. Each bullet gives the number of
  failing tests.
  - Accepting booleans as IDs: 2.
  - Echoing the id of an invalid request: 22.
  - Accepting any media type: 9.
  - Allowing 21 batch members: 2.
- **Live server:** `MySolution/.venv/bin/python -m MySolution --host
  127.0.0.1 --port 8000` started. `curl` with a `service.health` call got
  `200 OK`, `Content-Type: application/json` and
  `{"jsonrpc": "2.0", "result": {"status": "ok", "version": "1.0"}, "id": 1}`.
- **Instructor suite** (`python3 -m unittest discover -s TEST`, against that
  server): 6 passed and 9 failed (10 failures, counting subtests). Every
  failing test calls a `lambda.*` method, and every passing test uses only
  `service.health` or protocol behavior. The server was stopped afterwards.

## Known issues in the supplied material

These are in instructor-provided files. They are recorded here and left
unchanged.

- In the LAMBDA3 this solution was developed against (as added on
  2026-11-04 in upstream commit `50584a4`),
  `../LAMBDA3/mylib/TEST/test_list_library.py` and
  `test_optn_library.py` import `lambda2`, which this assignment does not
  supply. The instructor's update of 2026-11-10 (upstream commit `8b4974c`)
  changes them to import `lambda3`, and all four library tests then pass.
- For some programs, LAMBDA3's type-error text names the two types in swapped
  roles. `1 + true` gives `+: expected bool, got sint`, and
  `if 1 then 2 else 3` gives `if condition: expected sint, got bool`. The
  service passes LAMBDA3 diagnostics through unchanged, so `RPC.md` uses
  examples whose wording reads correctly.
