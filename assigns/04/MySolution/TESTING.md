# Testing

## Automated tests

Run from `MySolution/`: `.venv/bin/pytest -v` (177 tests, about 5 s; no browser or server needed).

| File | Covers | Spec |
| --- | --- | --- |
| `tests/test_reader.py` | Every constructor; comments/multiline/indentation; rejects injection and never executes input; line numbers | Restricted reader |
| `tests/test_lint.py` | `d0exp_fvset` per constructor, duplicates, nested/shadowed bindings, `fix`, `let` initializer scope, `frozenset`; Lint pass/fail, sorted names, no evaluation | Tests 1–2, F5 |
| `tests/test_interpret.py` | Arithmetic, factorial/Fibonacci incl. base cases; input vs runtime errors; `D0V000` in pairs; recursion limit | Test 3, F6 |
| `tests/test_model.py` | Load/replace, manual input, typing without upload, edit/apply/discard, draft blocks replacement, revisions clear results, stale results ignored, read-only snapshot, model imports no web/backend code | Test 4, F1, F2, F8 |
| `tests/test_model_rules.py` | Empty/whitespace, size (bytes, 64 KiB), invalid UTF-8/BOM rejected with state preserved and rejected drafts kept; busy blocks conflicting changes, finish/fail restore controls, retry, simultaneous clicks; per-action enable/reason, Execute gating, artifact invalidation | F2, F3, F4, F7, F8, F10; Test 6 (model) |
| `tests/test_controller_source.py` | State/source routes over HTTP with a fake backend: canned examples, upload, manual input without upload, 409/422/413/400 with state preserved, unknown API paths answer in JSON, HTML-like text passed through, controller imports no backend implementation | Test 4, F1, F2, F3, F8 |
| `tests/test_controller_actions.py` | Each action dispatches to the substituted backend; Execute consumes the compiled artifact, unavailable otherwise; refusals call no backend; results accumulate/clear; real Lint/Interpret via HTTP; Type-check/Compile report not implemented and produce no artifact; busy blocks other requests; crash and wrong result recorded, retry succeeds | Tests 5–6, F4, F5, F6, F7, F10 |
| `tests/test_view_page.py` | Page at `/`: Load source menu options, action buttons in F4 order (initially disabled, each with a reason slot), editor label, Apply/Discard, status/alert roles, every control labelled, unique ids, only local resources, template escapes text | F1, F2, F4, F9, F10 (structure) |
| `tests/test_view_script.py` | `app.js` served; never uses `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write`/`eval`/`new Function`; only calls `/api/`; no language logic; every element id it uses exists on the page | F9, MVC boundary (view) |
| `tests/test_samples.py` | Every file in `samples/` gives the Lint and Interpret outcomes documented in `samples/README.md` (incl. Lint-pass/Interpret-fail and timeout); invalid UTF-8 sample rejected on upload; no undocumented samples | F1, F3, F5, F6, F9, F10 (sample inputs) |


## Traceability: requirements F1–F10

| Req. | Requirement | Automated tests | Smoke steps |
| --- | --- | --- | --- |
| F1 | Load source menu, source name and revision | `test_view_page.py` (menu options), `test_controller_source.py` (canned, upload, manual input), `test_model.py` (load, manual input) | 2, 4, 6, 12 |
| F2 | Typing without upload, editing, Apply/Discard, edits block actions and replacement | `test_model.py` (editing, discard, typing without upload, draft blocks replacement), `test_model_rules.py` (unapplied edits disable actions), `test_controller_source.py` (409) | 6, 7, 8, 9 |
| F3 | Reject empty, invalid UTF-8 and oversized input, keeping the applied source and the rejected edit | `test_model_rules.py` (validation), `test_controller_source.py` (rejected uploads, 422 apply), `test_samples.py` (invalid UTF-8) | 10, 13 |
| F4 | Buttons in order, applied source required, Execute disabled | `test_view_page.py` (order), `test_model_rules.py` (gating), `test_controller_actions.py` (refusals) | 1, 2 |
| F5 | Lint reports undeclared names or none | `test_lint.py`, `test_controller_actions.py` (real Lint), `test_samples.py` | 3, 7, 8 |
| F6 | Interpret shows value or diagnostic, input vs runtime errors | `test_interpret.py`, `test_controller_actions.py` (real Interpret), `test_samples.py` | 3, 4, 11 |
| F7 | Type-check/Compile not implemented, Execute explained | `test_controller_actions.py` (placeholders, Execute unavailable), `test_model_rules.py` (Execute reason) | 2, 5 |
| F8 | New revision clears results and artifacts, rejected changes preserve state | `test_model.py` (results cleared, stale ignored), `test_model_rules.py` (artifact invalidation), `test_controller_actions.py` (results cleared) | 4 |
| F9 | Results show action, revision and outcome, text shown literally | `test_view_page.py` (escaping), `test_view_script.py` (no markup insertion), `test_controller_source.py` (HTML-like text), `test_samples.py` | 14 |
| F10 | Busy status, conflicts prevented, recovery, retry, time limit | `test_model_rules.py` (busy, fail, retry, simultaneous clicks), `test_controller_actions.py` (busy, crash, retry), `test_samples.py` (timeout) | 3, 15 |

## Required automated tests (assignment, section 4)

| # | Required coverage | Where |
| --- | --- | --- |
| 1 | Free variables for every constructor, duplicates, nested bindings, recursive functions, `let` initializer scope, `frozenset` result | `test_lint.py` |
| 2 | Lint success and listed names; Lint does not evaluate | `test_lint.py` |
| 3 | Arithmetic, factorial and Fibonacci with base cases; malformed input; runtime failures | `test_interpret.py`, `test_samples.py` |
| 4 | Manual input without upload, replacement, editing, rejected changes keep the applied source | `test_model.py`, `test_model_rules.py`, `test_controller_source.py` |
| 5 | Backend dispatch; placeholders never succeed; Execute unavailable | `test_controller_actions.py` |
| 6 | Busy state, backend failure, successful retry | `test_controller_actions.py`, `test_model_rules.py` |
| — | A model test runs without a browser or server | `test_model.py`, `test_model_rules.py` |
| — | A controller test substitutes a test backend without view changes | `test_controller_actions.py` (`FakeBackend`) |

## Browser smoke test

Manual run against `.venv/bin/python run.py`, opened at `http://127.0.0.1:5000`.

- **Date:** 2026-10-04
- **Browser and version:** Google Chrome 154.0.8037.98 (macOS)
- **Run by:** Robin Pena (manual)

| # | Steps | Expected | Spec | Observed |
| --- | --- | --- | --- | --- |
| 1 | Open `http://127.0.0.1:5000` | "Load a source to begin."; all actions disabled with one reason line | F4 | As expected (confirmed by Robin). |
| 2 | Factorial (canned) | "Factorial (canned) · revision 1"; text in editor; Lint–Compile enabled; Execute disabled with explanation | F1, F4, F7 | As expected (confirmed by Robin). |
| 3 | Lint, then Interpret | "No free variables found."; "Interpret is running…" then `D0Vint(arg1=3628800)` | F5, F6, F10 | As expected (confirmed by Robin). |
| 4 | Fibonacci (canned), Interpret | Revision 2, old results cleared; `D0Vint(arg1=55)` | F1, F8 | As expected (confirmed by Robin). |
| 5 | Type-check, Compile | Both "not implemented"; Execute still disabled | F7 | As expected (confirmed by Robin). |
| 6 | Manual input; type `D0Evar("x")` | Blank editor; actions and load buttons disabled ("Apply or discard…") | F1, F2 | As expected (confirmed by Robin). |
| 7 | Apply; Lint | "Manual input (manual) · revision 3"; language error "Undeclared variable(s): x" | F2, F5 | As expected (confirmed by Robin). |
| 8 | Edit to `D0Elam("x", D0Evar("x"))`; Apply; Lint | Revision 4; Lint ok | F2, F5 | As expected (confirmed by Robin). |
| 9 | Type something; Discard changes | Editor restored; revision unchanged | F2 | As expected (confirmed by Robin). |
| 10 | Clear the editor to spaces; Apply | Error "Source is empty."; spaces kept in editor; revision unchanged | F3 | As expected (confirmed by Robin). |
| 11 | Apply `D0Eop2("/", D0Eint(1), D0Eint(0))`; Lint; Interpret | Lint ok; Interpret language error with ZeroDivisionError | F5, F6 | As expected (confirmed by Robin). |
| 12 | Choose File… with a UTF-8 `.txt` | Loaded as upload, new revision | F1 | As expected (confirmed by Robin). |
| 13 | Choose File… with a non-UTF-8 file | Error naming UTF-8; previous source kept | F3 | As expected (confirmed by Robin). |
| 14 | Apply `# <b>hi</b> <script>alert(1)</script>` + newline + `D0Evar("<i>x</i>")`; Lint | Tags shown as text in editor and result; no alert; no bold | F9 | As expected (confirmed by Robin). |
| 15 | Edit Fibonacci's argument to 30; Apply; Interpret | "Interpret is running…" for about 5 s, then backend failure "Timed out after 5 s"; then set 10, Apply, Interpret gives 55 | F10 | As expected (confirmed by Robin). |
| 16 | Use only Tab, Enter and Space for steps 2–3 | Every control is reachable and works from the keyboard | Accessibility | As expected (confirmed by Robin). |

All 16 steps behaved as expected; no defects found.
