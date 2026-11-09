# Testing — LAMBDA3 JSON-RPC Service

This file maps each required behavior to the tests that check it, and records
observed results. The contract being tested is [`RPC.md`](RPC.md).

**Status:**
- **Passed** rows were run on 2026-11-09 with the commands below.
- **Planned** rows have no test yet. Their test names are the intended
  names.
- **Partly passed** rows have some of their checks written and passing,
  while the rest are still planned.

## Commands

All commands run from `assigns/07/` with Python 3.12 or later.

```sh
# Setup
python3 -m venv MySolution/.venv
MySolution/.venv/bin/python -m pip install -r MySolution/requirements.txt

# Local HTTP-level suite (Flask test client; real LAMBDA3 and real worker processes)
MySolution/.venv/bin/python -m unittest discover -s MySolution/tests -t . -v

# Start the service, then run the instructor's black-box suite from a second terminal
MySolution/.venv/bin/python -m MySolution --host 127.0.0.1 --port 8000
python3 -m unittest discover -s TEST -v
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

| # | Required behavior | Planned tests | Status |
| --- | --- | --- | --- |
| 1 | `service.health` returns status and API version and keeps the request id | `test_methods.HealthTests.test_health_result_and_id`, `test_envelope.IdTests.test_valid_ids_are_echoed_unchanged` | Passed |
| 2 | Type-checking valid programs returns the formatted type | `test_methods.TypecheckTests.test_formatted_types` (`sint`, `sint -> sint`, a tuple, `List[sint]`, an unresolved `?t` variable) | Planned |
| 3 | Interpreting arithmetic, factorial, a tuple and a collection gives the right value and type | `test_methods.InterpretTests.test_arithmetic`, `.test_factorial_720`, `.test_tuple`, `.test_list`, `.test_array_and_option`, `.test_library_list_length` (source built from `mylib/list.lam`) | Planned |
| 4 | Python and JavaScript compilation return nonempty source and the right `target` | `test_methods.CompileTests.test_python_matches_compiler`, `.test_javascript_matches_compiler` (both equal the direct compiler output), `.test_fixtures_match_service`, `.test_compile_does_not_evaluate` (`1 / 0` compiles) | Planned |
| 5 | Syntax errors and type errors have distinct documented codes | `test_language_errors.LanguageErrorTests.test_syntax_error_code_and_position`, `.test_type_error_code`, `.test_codes_are_distinct` | Planned |
| 6 | Malformed JSON, invalid envelopes, unknown methods, absent or wrongly typed params, blank source and oversized source | `test_envelope.ParseErrorTests.*`, `test_envelope.InvalidRequestTests.*`, `test_envelope.MethodNotFoundTests.*`, `test_params.ParamsTests.*`, `test_params.SourceLimitTests.*` | Partly passed: parse errors, invalid envelopes, unknown methods, and absent, positional or scalar params pass. The `source` rules are planned. |
| 7 | A function result is formatted without closure internals | `test_methods.InterpretTests.test_lam_value_formatted`, `.test_fix_value_formatted` | Planned |
| 8 | An injected backend failure or timeout returns the documented error, keeps the id, and shows no traceback | `test_failures.FailureTests.test_worker_exception_is_internal_error`, `.test_worker_crash_is_internal_error`, `.test_blocking_worker_times_out_and_is_stopped`, `.test_slow_program_times_out`, `.test_service_recovers_after_timeout` | Planned |
| 9 | LAMBDA3 type checking rejects an unbound variable | `test_language_errors.LanguageErrorTests.test_unbound_variable_rejected` | Planned |
| 10 | Batches keep IDs and omit notifications; invalid members get `id: null`; a notification-only batch and a single notification get 204 with an empty body; an empty batch gets one Invalid Request object | `test_batches.BatchTests.*`, `test_batches.BatchProcessingTests.*`, `test_envelope.NotificationTests.test_single_notification_is_204_empty`, `test_transport.TransportTests.test_notification_is_204_with_zero_byte_body` | Passed |

### Contract details (`RPC.md`)

| Behavior | `RPC.md` | Planned tests | Status |
| --- | --- | --- | --- |
| 404 / 405 (with `Allow: POST`) / 415 / 413 in that order; text bodies on transport errors; JSON media type on 200; zero-byte 204 with no `Content-Type` | §1 | `test_transport.TransportTests.*` | Passed |
| Parse errors: truncated JSON, invalid UTF-8, BOM, `NaN`/`Infinity`, `1e400`, a 4,301-digit integer, deeply nested arrays, empty body | §1, §4 | `test_envelope.ParseErrorTests.*` | Passed |
| Each `-32600` reason, including a usable id that is not echoed and a top-level scalar | §2, §4 | `test_envelope.InvalidRequestTests.*` | Passed |
| IDs `""`, `0`, negative, fractional, large integer (up to 4,300 digits) and explicit `null` are echoed with the same JSON type; boolean, object and array IDs are rejected | §2 | `test_envelope.IdTests.*` | Passed |
| Notifications are processed; with an unknown method, bad params, a documented error or an internal error they still produce no response | §2 | `test_envelope.NotificationTests.*` | Passed |
| Dispatcher boundary: params passed through as sent; a documented error from a method keeps the id and data | §2, §4 | `test_envelope.DispatchBoundaryTests.*` (test double for the method table) | Passed |
| Params: missing, positional and scalar `params`; unexpected keys; `service.health` with members; `target` missing, wrong type or wrong case | §3 | `test_params.ParamsTests.*`, `test_envelope.InvalidRequestTests.test_bad_params` | Partly passed: the `service.health` and envelope cases pass. The `target` rules are planned. |
| Source limit boundaries: 65,536 vs 65,537 ASCII bytes; a 2-byte character pushing past the limit; unpaired surrogate; whitespace only | §3, §5 | `test_params.SourceLimitTests.*` | Planned |
| Runtime errors get `-32013` (division by zero, empty-list head, array index) | §4 | `test_language_errors.LanguageErrorTests.test_runtime_errors` | Planned |
| Too-deep nesting gives `-32010`; too-deep recursion gives `-32013`; neither is reported as a timeout | §4 | `test_language_errors.LanguageErrorTests.test_deep_nesting_is_syntax_error`, `.test_deep_recursion_is_runtime_error` | Planned |
| Diagnostics are capped at 1,000 characters | §4 | `test_language_errors.LanguageErrorTests.test_long_diagnostic_is_truncated` | Planned |
| Internal errors log details under the `incident` value and keep them out of the response | §4 | `test_envelope.DispatchBoundaryTests.test_unexpected_exception_is_logged_not_returned` (dispatcher), `test_failures.FailureTests.test_internal_error_is_logged_not_returned` (worker) | Partly passed: the dispatcher case passes. The worker case is planned. |
| Output from `print` is discarded; only the value is returned | §3 | `test_methods.InterpretTests.test_print_output_discarded` | Planned |
| Batch edge cases: 20 members accepted; 21 rejected with nothing run; duplicate IDs both answered; nested-array and scalar members; members run in order; one member's failure doesn't affect the others | §6 | `test_batches.BatchTests.*`, `test_batches.BatchProcessingTests.*` | Passed |
| The schema is valid; the fixtures and every `RPC.md` response validate; the invalid `RPC.md` requests are rejected; result+error is rejected | §8 | `test_schema.SchemaTests.*` | Passed |
| Every `RPC.md` §7 exchange gives the documented status and body | §7 | `test_examples.RpcMdExampleTests.test_documented_exchanges` | Planned |

### Instructor black-box suite (`../TEST/test_rpc_api.py`, unchanged, against a live server)

| Test | Status (2026-11-09) |
| --- | --- |
| `test_health` | Passed |
| `test_typecheck_arithmetic` | Failed: calls a `lambda.*` method, which the service did not yet serve (`-32601`) |
| `test_interpret_arithmetic` | Failed: calls a `lambda.*` method, which the service did not yet serve (`-32601`) |
| `test_interpret_tuple` | Failed: calls a `lambda.*` method, which the service did not yet serve (`-32601`) |
| `test_interpret_list` | Failed: calls a `lambda.*` method, which the service did not yet serve (`-32601`) |
| `test_interpret_function_formats_closure` | Failed: calls a `lambda.*` method, which the service did not yet serve (`-32601`) |
| `test_compile_python_and_javascript` | Failed: calls a `lambda.*` method, which the service did not yet serve (`-32601`) |
| `test_language_syntax_and_type_errors_are_distinct` | Failed: calls a `lambda.*` method, which the service did not yet serve (`-32601`) |
| `test_invalid_params_and_unknown_method` | Failed: calls a `lambda.*` method, which the service did not yet serve (`-32601`) |
| `test_malformed_json_returns_parse_error` | Passed |
| `test_batch_matches_by_id_and_omits_notification` | Failed: calls a `lambda.*` method, which the service did not yet serve (`-32601`) |
| `test_notification_only_batch_has_no_response` | Passed |
| `test_notification_has_no_response` | Passed |
| `test_invalid_request_and_empty_batch` | Passed |
| `test_malformed_batch_member_gets_null_id_error` | Passed |

## Observed results

Environment: macOS, Python 3.14.10, Flask 3.1.3, Werkzeug 3.1.9,
jsonschema 4.26.0.

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

- `../LAMBDA3/mylib/TEST/test_list_library.py` and `test_optn_library.py`
  import `lambda2`, which this assignment does not supply. The other library
  tests import `lambda3`.
- For some programs, LAMBDA3's type-error text names the two types in swapped
  roles. `1 + true` gives `+: expected bool, got sint`, and
  `if 1 then 2 else 3` gives `if condition: expected sint, got bool`. The
  service passes LAMBDA3 diagnostics through unchanged, so `RPC.md` uses
  examples whose wording reads correctly.
