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
- `run.py` binds 127.0.0.1:5000 (AirPlay Receiver disabled; use 127.0.0.1, not localhost)
- Smoke tests pass

**Task 3 — reader:**
- `backend/reader.py`: `ast`-walked, whitelist of 13 `D0E*` constructors, per-argument kind checks
- Never eval/exec; rejects imports, attributes, keywords, wrong arity/types, deep nesting
- Operator names checked only as non-empty strings; unknown ops left to the interpreter
- Indented/pasted input accepted (source parenthesized before parsing)

## Next

**To do:**
- [x] Install Python 3.12+ (have 3.14.8)
- [x] Task 2: venv, `requirements.txt`, copy `lambda1.py`, minimal app on 127.0.0.1
- [x] Task 3: restricted constructor reader (`backend/reader.py`)
- [ ] Task 4: result contract (`backend/contract.py`)
