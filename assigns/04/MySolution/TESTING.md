# Testing

## Automated tests

Run from `MySolution/`: `.venv/bin/pytest -v`

| File | Covers | Spec |
| --- | --- | --- |
| `tests/test_smoke.py` | App factory serves `/`; `lambda1` imports | Setup |
| `tests/test_reader.py` | Every constructor; comments/multiline/indentation; rejects injection and never executes input; line numbers | Restricted reader |
| `tests/test_contract.py` | Immutable `Result`; only `OK` is success; button order | §2, F4 |
| `tests/test_lint.py` | `d0exp_fvset` per constructor, duplicates, nested/shadowed bindings, `fix`, `let` initializer scope, `frozenset`; Lint pass/fail, sorted names, no evaluation | Tests 1–2, F5 |
| `tests/test_interpret.py` | Arithmetic, factorial/Fibonacci incl. base cases; input vs runtime errors; `D0V000` in pairs; recursion limit; Lint-pass/Interpret-fail | Test 3, F6 |
| `tests/test_placeholders_timeout.py` | Type-check/Compile/Execute not implemented, no artifact; timeout then successful retry | Tests 5–6 (backend), F7, F10 |
| `tests/test_model.py` | Load/replace, manual input, typing without upload, edit/apply/discard, draft blocks replacement, revisions clear results, stale results ignored, read-only snapshot, model imports no web/backend code | Test 4, F1, F2, F8 |

**Not yet covered:** model validation and busy state (F3, F10), controller dispatch and busy state (Tests 5–6), browser smoke test.
