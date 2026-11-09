# Testing — LAMBDA3 JSON-RPC Service

This file maps each required behavior to the tests that check it, and records
observed results. The contract being tested is [`RPC.md`](RPC.md).

**Status:** every row is **Planned**. No service tests have been run yet.
Test names are the intended names, and this file is updated as tests are
written and run.

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
| 1 | `service.health` returns status and API version and keeps the request id | `test_methods.HealthTests.test_health_result_and_id` | Planned |
| 2 | Type-checking valid programs returns the formatted type | `test_methods.TypecheckTests.test_formatted_types` (`sint`, `sint -> sint`, a tuple, `List[sint]`, an unresolved `?t` variable) | Planned |
| 3 | Interpreting arithmetic, factorial, a tuple and a collection gives the right value and type | `test_methods.InterpretTests.test_arithmetic`, `.test_factorial_720`, `.test_tuple`, `.test_list`, `.test_array_and_option`, `.test_library_list_length` (source built from `mylib/list.lam`) | Planned |
| 4 | Python and JavaScript compilation return nonempty source and the right `target` | `test_methods.CompileTests.test_python_matches_compiler`, `.test_javascript_matches_compiler` (both equal the direct compiler output), `.test_fixtures_match_service`, `.test_compile_does_not_evaluate` (`1 / 0` compiles) | Planned |
| 5 | Syntax errors and type errors have distinct documented codes | `test_language_errors.LanguageErrorTests.test_syntax_error_code_and_position`, `.test_type_error_code`, `.test_codes_are_distinct` | Planned |
| 6 | Malformed JSON, invalid envelopes, unknown methods, absent or wrongly typed params, blank source and oversized source | `test_envelope.ParseErrorTests.*`, `test_envelope.InvalidRequestTests.*`, `test_envelope.MethodNotFoundTests.*`, `test_params.ParamsTests.*` | Planned |
| 7 | A function result is formatted without closure internals | `test_methods.InterpretTests.test_lam_value_formatted`, `.test_fix_value_formatted` | Planned |
| 8 | An injected backend failure or timeout returns the documented error, keeps the id, and shows no traceback | `test_failures.FailureTests.test_worker_exception_is_internal_error`, `.test_worker_crash_is_internal_error`, `.test_blocking_worker_times_out_and_is_stopped`, `.test_slow_program_times_out`, `.test_service_recovers_after_timeout` | Planned |
| 9 | LAMBDA3 type checking rejects an unbound variable | `test_language_errors.LanguageErrorTests.test_unbound_variable_rejected` | Planned |
| 10 | Batches keep IDs and omit notifications; invalid members get `id: null`; a notification-only batch and a single notification get 204 with an empty body; an empty batch gets one Invalid Request object | `test_batches.BatchTests.*`, `test_envelope.NotificationTests.test_single_notification_is_204_empty` | Planned |

### Contract details (`RPC.md`)

| Behavior | `RPC.md` | Planned tests | Status |
| --- | --- | --- | --- |
| 404 / 405 (with `Allow: POST`) / 415 / 413; text bodies on transport errors; JSON media type on 200; zero-byte 204 | §1 | `test_transport.TransportTests.*` | Planned |
| Parse errors: truncated JSON, invalid UTF-8, BOM, `NaN`/`Infinity`, `1e400`, empty body | §1, §4 | `test_envelope.ParseErrorTests.*` | Planned |
| Each `-32600` reason, including a usable id that is not echoed and a top-level scalar | §2, §4 | `test_envelope.InvalidRequestTests.*` | Planned |
| IDs `""`, `0`, negative, fractional, large integer and explicit `null` are echoed; boolean, object and array IDs are rejected | §2 | `test_envelope.IdTests.*` | Planned |
| Notifications with an unknown method, bad params or a LAMBDA error produce no response | §2 | `test_envelope.NotificationTests.*` | Planned |
| Params: missing, positional and scalar `params`; unexpected keys; `service.health` with members; `target` missing, wrong type or wrong case | §3 | `test_params.ParamsTests.*` | Planned |
| Source limit boundaries: 65,536 vs 65,537 ASCII bytes; a 2-byte character pushing past the limit; unpaired surrogate; whitespace only | §3, §5 | `test_params.SourceLimitTests.*` | Planned |
| Runtime errors get `-32013` (division by zero, empty-list head, array index) | §4 | `test_language_errors.LanguageErrorTests.test_runtime_errors` | Planned |
| Too-deep nesting gives `-32010`; too-deep recursion gives `-32013`; neither is reported as a timeout | §4 | `test_language_errors.LanguageErrorTests.test_deep_nesting_is_syntax_error`, `.test_deep_recursion_is_runtime_error` | Planned |
| Diagnostics are capped at 1,000 characters | §4 | `test_language_errors.LanguageErrorTests.test_long_diagnostic_is_truncated` | Planned |
| Internal errors log details under the `incident` value and keep them out of the response | §4 | `test_failures.FailureTests.test_internal_error_is_logged_not_returned` | Planned |
| Output from `print` is discarded; only the value is returned | §3 | `test_methods.InterpretTests.test_print_output_discarded` | Planned |
| Batch edge cases: more than 20 members; duplicate IDs both answered; nested-array member; scalar members | §6 | `test_batches.BatchTests.*` | Planned |
| The schema is valid; the fixtures and every `RPC.md` response validate; result+error is rejected | §8 | `test_schema.SchemaTests.*` | Planned |
| Every `RPC.md` §7 exchange gives the documented status and body | §7 | `test_examples.RpcMdExampleTests.test_documented_exchanges` | Planned |

### Instructor black-box suite (`../TEST/test_rpc_api.py`, unchanged, against a live server)

| Test | Status |
| --- | --- |
| `test_health` | Planned |
| `test_typecheck_arithmetic` | Planned |
| `test_interpret_arithmetic` | Planned |
| `test_interpret_tuple` | Planned |
| `test_interpret_list` | Planned |
| `test_interpret_function_formats_closure` | Planned |
| `test_compile_python_and_javascript` | Planned |
| `test_language_syntax_and_type_errors_are_distinct` | Planned |
| `test_invalid_params_and_unknown_method` | Planned |
| `test_malformed_json_returns_parse_error` | Planned |
| `test_batch_matches_by_id_and_omits_notification` | Planned |
| `test_notification_only_batch_has_no_response` | Planned |
| `test_notification_has_no_response` | Planned |
| `test_invalid_request_and_empty_batch` | Planned |
| `test_malformed_batch_member_gets_null_id_error` | Planned |

## Observed results

None yet.

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
