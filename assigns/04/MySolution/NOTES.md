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
- Machine has Python 3.9.6; spec requires 3.12+

**Created:**
- Project tree: `lambda_web/{backend,model,controller,view}`, `tests/`, `samples/`
- `.gitignore`, `.python-version`, `NOTES.md`
- Blank deliverables: `requirements.txt`, `README.md`, `ARCHITECTURE.md`, `TESTING.md`, `AI-TRANSCRIPT.md`

## Next

**To do:**
- [ ] Install Python 3.12
- [ ] Task 2: venv, `requirements.txt`, copy `lambda1.py`, minimal app on 127.0.0.1
