# AI transcript: Assignment 08

AI was used for this assignment. This file records which tools were used, the
meaningful prompts, what the AI suggested or produced, and how the work was
checked. It is kept up to date stage by stage. Sections marked *student* must
be written by the student; the AI does not fill them in on the student's
behalf.

## Tools

- **Claude Code**, Anthropic's command-line coding agent, using the model
  Claude Opus 5.5 (`claude-opus-5-5`). It ran in the student's local terminal
  with permission to read files, run shell commands, and edit files inside
  `assigns/08/MySolution/`.
- **A staged master prompt**, `assign08-master-prompt.md`, which the student
  supplied and keeps outside this repository. It splits the work into stages
  0 to 6 and requires a stop for review after each one.
  *Student: state how that prompt was produced.*

## Session log

### 2026-11-17: Stage 0, read-only discovery

**Prompt (verbatim):** "Let's work on our latest development assignment, take
a look into assign08-master-prompt.md, and then lets get to work on the latest
assignemnt for CS413"

**What the AI did:**

- Read `Assign08.md`, the supplied interpreter (`lambda3.py`, `basics0.py`),
  the queens and lazy-stream examples, `mylib/strm.lam`, and the student's
  Assign07 transport, dispatcher and tests. No repository files were changed.
- Wrote a throwaway CPS solver prototype in a temporary directory outside the
  repository and ran it with `python3 -B` against `assigns/08/LAMBDA3`. It
  type-checked, made no search calls when a stream was opened, produced the
  two size-4 solutions in the expected order, and produced 92 valid, distinct,
  lexicographically ordered size-8 solutions in 33,589 events. The full run
  completed with Python's recursion limit lowered to 80.

**Suggestions made**, all accepted by the student when they said "lets do
Stage 1 first":

- Merge `search` and `try_column` into one recursive function, because
  LAMBDA3's `fix` supports only self-recursion.
- Encode events as tagged tuples, store boards newest row first, and reverse
  them once in the adapter.
- Reuse the Assign07 Flask transport and dispatcher, adapted and credited.
- Do not support JSON-RPC batches.
- Use a 300-second stream inactivity lifetime and keep a small record for
  exhausted streams.
- Use plain ES modules for the client, tested with `node --test`.

### 2026-11-17: Stage 1, design and test plan

**Prompt (verbatim):** "I want to do a commit and self test + overview after
each stage, so lets do Stage 1 first."

**What the AI did:**

- Checked that a polymorphic CPS safety checker (`queens_check_safe[A]`)
  type-checks in LAMBDA3 and runs at both `sint` and stream answer types,
  again in a temporary directory outside the repository.
- Collected exact event sequences from the prototype for the examples in
  the design.
- Wrote `DESIGN.md` (architecture, invariant, continuation types,
  pseudocode, laziness argument, stream lifecycle, RPC contract, client
  design), `TESTING.md` (a plan in which every test is marked "not run"),
  and this file.
- Ran a self-test of the documents, created the branch `assign08`, and
  committed only these three files.

**Notable design suggestions:**

- Make `solver.lam` a declaration file, so tests can call each helper
  through LAMBDA3.
- Make the safety checker polymorphic in its answer type.
- Have "Next solution" fetch batches of 32 events, buffering any events after
  the solution. The prototype showed that the first 8×8 solution is event
  1,858, which would take 1,858 requests with `limit: 1`.

## Review and testing by the student

*Student: describe how you reviewed the design and code, which tests you ran
yourself, and anything you changed or rejected.*
