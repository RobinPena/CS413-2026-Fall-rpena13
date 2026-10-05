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
| `tests/test_model_rules.py` | Empty/whitespace, size (bytes, 64 KiB), invalid UTF-8/BOM rejected with state preserved and rejected drafts kept; busy blocks conflicting changes, finish/fail restore controls, retry, simultaneous clicks; per-action enable/reason, Execute gating, artifact invalidation | F2, F3, F4, F7, F8, F10; Test 6 (model) |
| `tests/test_controller_source.py` | State/source routes over HTTP with a fake backend: canned examples (valid programs), upload, manual input without upload, edit/apply/discard, replacement, 409/422/413/400 with state preserved, unknown API paths answer in JSON, HTML-like text passed through, controller imports no backend implementation | Test 4, F1, F2, F3, F8 |
| `tests/test_controller_actions.py` | Each action dispatches to the substituted backend; Execute consumes the compiled artifact, unavailable otherwise; refusals call no backend; results accumulate/clear; real Lint/Interpret/placeholders via HTTP; busy blocks other requests; crash and wrong result recorded, retry succeeds; real timeout via HTTP | Tests 5–6, F4, F5, F6, F7, F10 |
| `tests/test_view_page.py` | Page at `/`: Load source menu options, action buttons in F4 order (initially disabled, each with a reason slot), editor label, Apply/Discard, status/alert roles, every control labelled, unique ids, only local resources, template escapes text | F1, F2, F4, F9, F10 (structure) |

**Not yet covered:** view script behavior (`app.js`), browser smoke test.
