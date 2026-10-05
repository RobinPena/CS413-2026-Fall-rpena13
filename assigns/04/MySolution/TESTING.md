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
| `tests/test_view_script.py` | `app.js` served; never uses `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write`/`eval`/`new Function`; only calls `/api/`; no language logic; every element id it uses exists on the page | F9, MVC boundary (view) |

**Not yet covered:** browser smoke test (below).

## Browser smoke test

Manual run against `.venv/bin/python run.py`, opened at `http://127.0.0.1:5000`.

- **Date:**
- **Browser and version:**
- **Run by:**

| # | Steps | Expected | Spec | Observed |
| --- | --- | --- | --- | --- |
| 1 | Open `http://127.0.0.1:5000` | "Load a source to begin."; all actions disabled with one reason line | F4 | |
| 2 | Factorial (canned) | "Factorial (canned) · revision 1"; text in editor; Lint–Compile enabled; Execute disabled with explanation | F1, F4, F7 | |
| 3 | Lint, then Interpret | "No free variables found."; "Interpret is running…" then `D0Vint(arg1=3628800)` | F5, F6, F10 | |
| 4 | Fibonacci (canned), Interpret | Revision 2, old results cleared; `D0Vint(arg1=55)` | F1, F8 | |
| 5 | Type-check, Compile | Both "not implemented"; Execute still disabled | F7 | |
| 6 | Manual input; type `D0Evar("x")` | Blank editor; actions and load buttons disabled ("Apply or discard…") | F1, F2 | |
| 7 | Apply; Lint | "Manual input (manual) · revision 3"; language error "Undeclared variable(s): x" | F2, F5 | |
| 8 | Edit to `D0Elam("x", D0Evar("x"))`; Apply; Lint | Revision 4; Lint ok | F2, F5 | |
| 9 | Type something; Discard changes | Editor restored; revision unchanged | F2 | |
| 10 | Clear the editor to spaces; Apply | Error "Source is empty."; spaces kept in editor; revision unchanged | F3 | |
| 11 | Apply `D0Eop2("/", D0Eint(1), D0Eint(0))`; Lint; Interpret | Lint ok; Interpret language error with ZeroDivisionError | F5, F6 | |
| 12 | Choose File… with a UTF-8 `.txt` | Loaded as upload, new revision | F1 | |
| 13 | Choose File… with a non-UTF-8 file | Error naming UTF-8; previous source kept | F3 | |
| 14 | Apply `# <b>hi</b> <script>alert(1)</script>` + newline + `D0Evar("<i>x</i>")`; Lint | Tags shown as text in editor and result; no alert; no bold | F9 | |
| 15 | Edit Fibonacci's argument to 30; Apply; Interpret | "Interpret is running…" for about 5 s, then backend failure "Timed out after 5 s"; then set 10, Apply, Interpret gives 55 | F10 | |
| 16 | Use only Tab, Enter and Space for steps 2–3 | Every control is reachable and works from the keyboard | Accessibility | |
