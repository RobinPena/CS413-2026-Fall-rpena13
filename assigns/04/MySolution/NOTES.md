# Assign04 — Work Notes

Short running log of progress. Details live in the code, docs, and `AI-TRANSCRIPT.md`.

## 2026-10-04 (Sun)

**Planning:**
- Read Assign04 spec
- Mapped it to prior work (Assign02 interpreter, Assign03 requirements)
- Drafted 18-task plan (30–60 min each), 6 phases: setup → backend → model → controller → view → tests/docs

**Decisions:**
- Flask + pytest
- Controller coordinates backend calls
- `lambda1.py` copied unchanged into `lambda_web/backend/`

**Ground rules:**
- No AI commits/pushes
- Every file change reviewed before writing

**Blockers:**
- ~~Machine has Python 3.9.6; spec requires 3.12+~~ Resolved: Homebrew Python 3.14.8 on PATH

**Created:**
- Project tree: `lambda_web/{backend,model,controller,view}`, `tests/`, `samples/`
- `.gitignore`, `.python-version`, `NOTES.md`
- Blank deliverables: `requirements.txt`, `README.md`, `ARCHITECTURE.md`, `TESTING.md`, `AI-TRANSCRIPT.md`

**Task 2 — setup:**
- venv on Python 3.14.8; pinned flask 3.1.3, pytest 9.1.1
- `lambda1.py` copied unchanged into `lambda_web/backend/`
- App factory `create_app()`; placeholder `/` route in controller blueprint
- `run.py` binds 127.0.0.1:5000 (AirPlay Receiver disabled; 127.0.0.1 and localhost both verified)
- Smoke tests pass

**Task 3 — reader:**
- `backend/reader.py`: `ast`-walked, whitelist of 13 `D0E*` constructors, per-argument kind checks
- Never eval/exec; rejects imports, attributes, keywords, wrong arity/types, deep nesting
- Operator names checked only as non-empty strings; unknown ops left to the interpreter
- Indented/pasted input accepted (source parenthesized before parsing)

**Task 4 — contract:**
- `backend/contract.py`: `Operation`, `Outcome` (ok / input / language / backend failure / not implemented), frozen `Result`, `Artifact`, `LanguageBackend` Protocol
- Results tagged with revision; failures returned as Results, not exceptions
- Timeout classified as backend failure; undeclared vars + runtime errors as language errors

**Task 5 — Lint + Interpret:**
- `backend/lambda_backend.py`: `LambdaBackend.lint` (fvset, sorted names, no evaluation) and `.interpret` (`d0exp_evaluate`, empty env)
- Errors: reader → input error; exceptions or `D0V000` (incl. inside pairs) → language error; recursion limit → backend failure

**Task 6 — placeholders + timeout:**
- Type-check / Compile / Execute return `NOT_IMPLEMENTED`; Compile never yields an artifact
- Interpret runs in a spawned child process, killed after 5 s → backend failure; retry starts fresh
- Lint stays in-process (single tree walk, parser bounds nesting)

**Backend tests (pulled forward from tasks 13–14):**
- Added reader, contract, lint, interpret, placeholder/timeout tests + shared `tests/programs.py`
- `TESTING.md` started with coverage table mapped to spec tests/F-IDs
- Result: 102 passed (~4 s); deliberate break of pair `D0V000` check caught by `error-inside-pair` test

**Task 7 — model state:**
- `model/session.py`: `Session` (load, open_manual, edit, apply, discard, record, snapshot), frozen `Source`/`Snapshot`, `StateError`
- Revisions only increase; new revision clears results + artifact; stale results ignored
- Draft blocks source replacement; one lock per session; model imports only stdlib + contract
- Tests: `tests/test_model.py` (119 passed total); deliberate breaks (load ignoring draft, model importing flask) each caught

**Task 8 — model rules:**
- Validation: empty/whitespace, 64 KiB (bytes), UTF-8 uploads (BOM dropped); rejected drafts kept for correction
- Busy: `begin` → `Job`, `finish(result, artifact)`, `fail(message)`; busy blocks all changes; replaces `record`
- Gating: per-action enabled + reason in `Snapshot`; Execute needs artifact for current revision
- Tests: `tests/test_model_rules.py` (146 passed total); break (edit ignoring busy) caught
- Found: simultaneous-click test couldn't detect a missing lock (0/200); fixed by widening the check→busy gap in the test, now catches it every time

**Task 9 — controller source routes:**
- `create_app(backend, session)` is the only place choosing the concrete backend; one shared `Session` per server
- JSON routes: state, upload, canned, manual, edit, apply (sends text), discard; errors → 409/422/400/413/404 with full state
- Unknown `/api/` paths (404/405) answer in the same JSON shape; found when a decoded `../` path got Flask's HTML 404
- `serialize.py` (Snapshot → plain dict), `examples.py` (catalog → `samples/*.txt`), samples factorial(10) / fibonacci(10)
- Port back to 5000 after AirPlay fix; live check on 127.0.0.1 and localhost
- Tests: `tests/test_controller_source.py` + `tests/fakes.py` (176 passed total); breaks (no 409 handler, controller importing backend) caught

**Task 10 — controller actions:**
- `POST /api/actions/<id>`: `begin` → `_dispatch` → `finish`; any exception (backend or `finish`) → `fail`, logged, page never stuck busy
- Execute gets the model's artifact for the current revision; never recompiles
- `FakeBackend` options: `crashes`, `gate`, `artifact`; controller tests swap backends with no view changes
- Tests: `tests/test_controller_actions.py` (192 passed total); breaks (no crash guard, swapped dispatch) caught; live check of all five actions

**Task 11 — view structure:**
- `view/templates/index.html`: Load source button group, editor + Apply/Discard, actions from `Operation` order with reason slots, status (`role=status`), error (`role=alert`), results list
- `view/static/style.css`: CSS variables for restyling; outcomes shown as text, color only as cue
- `/` renders the template; tests parse the page with `html.parser` (200 passed total); breaks (reordered actions, `|safe` escaping) caught
- Look will be revised by Robin; tests check structure only

**Task 12 — view script:**
- `app.js`: `render(state)` copies server state to the page (textContent only); `run()` gives every click the same busy → request → render cycle
- Draft sync: first keystroke immediate, then 400 ms debounce; actions wait for pending edit; editor never overwritten while typing
- Duplicate disabled-reasons shown once; reload while busy polls until idle; network/HTTP errors shown in alert
- 413 message reworded ("submitted source", not "upload") since it also covers edits
- No JS runtime on this machine → static tests in `tests/test_view_script.py` + browser smoke test (214 passed total); breaks (`innerHTML`, renamed id) caught
- Chrome extension not used → smoke test run manually by Robin; checklist in `TESTING.md`

**Browser smoke test:**
- 16-step checklist run manually in Chrome by Robin; all steps as expected, no defects

**Task 16 — samples:**
- Added error samples: undeclared variable, division by zero, malformed input, rejected code, HTML-like text, slow Fibonacci (timeout), invalid UTF-8
- `samples/README.md` table of expected outcomes; `tests/test_samples.py` checks each (224 passed total); break (wrong documented outcome) caught
- Measured: fib(25) ≈ 5 s, fib(27) ≈ 13 s → fib(30) ≈ 1 min, reliably times out

**Task 17 — ARCHITECTURE.md:**
- Component diagram, responsibility table, controller-coordinates-backend rationale, Load → Lint → Interpret sequence (+ undeclared variable), backend contract, 2 design decisions (child process; JSON snapshots), placeholder replacement path, view contract, enforced boundaries
- Final pass: grammar and consistency (sentences instead of dashes, serial commas, "would" for future features, IDs), accurate status-code mapping incl. 405, Why/Tradeoff labels throughout, descriptive title

**Test cleanup:**
- 224 → 177 tests: removed `test_smoke.py`, `test_contract.py`, `test_placeholders_timeout.py`; trimmed same-path parameter cases; dropped controller tests duplicating model rules
- Every spec Test 1–6 still covered; earlier breaks (pair `D0V000`, swapped dispatch) still caught
- Mistake caught: first removal script was too greedy in two controller test files; restored from last commit and redone with exact matches

**Task 18 — README + traceability:**
- README: requirements, setup/run/test commands, input format, limits (incl. recursion depth ~160 calls, kept as documented limitation), 5 demos, known limitations, layout; reflection left for Robin
- TESTING.md: F1–F10 traceability and assignment §4 required-tests tables
- Every README demo result re-verified against the code (3628800, 55, 42, ZeroDivisionError, 5 s timeout, fact(164)/fact(165))

## Next

**To do:**
- [x] Install Python 3.12+ (have 3.14.8)
- [x] Task 2: venv, `requirements.txt`, copy `lambda1.py`, minimal app on 127.0.0.1
- [x] Task 3: restricted constructor reader (`backend/reader.py`)
- [x] Task 4: result contract (`backend/contract.py`)
- [x] Task 5: real Lint + Interpret (`backend/lambda_backend.py`)
- [x] Task 6: placeholders (Type-check/Compile/Execute) + interpret timeout
- [x] Task 7: model — source state, revisions, apply/discard (`model/session.py`)
- [x] Task 8: model validation (empty/UTF-8/64 KiB) + busy state + action gating
- [x] Task 9: controller source routes (upload, manual, canned, edit, apply, discard)
- [x] Task 10: controller action routes, dispatch, crash guard, backend substitution tests
- [x] Task 11: view template (menu, editor, controls, status, results)
- [x] Task 12: view script `app.js` (render state, forward actions, busy, draft sync)
- [x] Browser smoke test (manual, Robin) — results in `TESTING.md`
- [x] Task 16: samples (error examples)
- [x] Task 17: ARCHITECTURE.md
- [ ] Task 18: README/TESTING/clean-checkout check
