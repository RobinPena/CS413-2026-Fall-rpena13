# AI Transcript

## Tool used

Claude Code (Anthropic), model Claude Opus 5.5, used interactively in the
terminal against this repository from October 4 to October 6, 2026. The
effort setting was raised to "xhigh" on October 5. The Claude in Chrome
browser extension was tried for the browser smoke test but could not connect,
so it was not used.

## Workflow

Before any code was written, I set the ground rules: Claude never commits or
pushes, any file change or code addition is proposed as a draft and approved before it is
written, and work is split into short tasks. Claude first summarized
how the assignment builds on Assign02 (the interpreter) and Assign03 (the
requirements), then proposed an 18-task plan in six phases: setup, backend,
model, controller, view, and tests and documentation.

Each phase started with a plan covering goals, approach and reasons, which I
reviewed before any code. Each task then followed the same cycle: Claude
showed a draft, I approved or changed it, Claude wrote the files and ran the
full test suite, and the results were recorded in `NOTES.md` and
`TESTING.md`. I made every commit myself. Several times I paused the work to
test what had been built so far.

## Significant AI-generated suggestions

- Safety: a restricted reader that parses input and walks the syntax tree
  instead of running it. Interpret runs in a separate process that is killed
  after 5 seconds.
- Testing approach: tests that enforce boundaries (what the model and
  controller import, and a static safety check on the script), a fake backend
  that can crash, block or produce generated code, and a deliberately planted
  bug in each task to prove the tests catch it.
- The diagrams of `ARCHITECTURE.md`, `TESTING.md`,
  `samples/README.md` and `README.md`.

## AI mistakes caught and fixed

- Claude twice ran check scripts in a way the spawned interpreter process
  could not handle, which produced false "process exited unexpectedly"
  results. The checks were re-run correctly from a file.
- Claude once staged file deletions in Git, against the ground rules. It
  noticed and undid this immediately.
- A script meant to remove a few redundant tests deleted many more. The two
  affected files were restored from my last commit and edited again with
  exact matches.
- A test meant to catch two simultaneous clicks could not detect a missing
  lock (0 failures in 200 runs). It was fixed so that it fails every time the
  lock is removed.
- Testing exposed three smaller problems that were fixed: indented input was
  rejected, unknown API paths returned HTML instead of JSON, and an error
  message said "upload" even for edits.

## How the output was reviewed and tested

- I reviewed every draft before it was written.
- After every task, the full automated suite was run, and the real pass
  counts were recorded in `NOTES.md`.
- In each phase, Claude deliberately broke the code (for example, removing a
  safety check or swapping two operations) to confirm the tests failed, then
  restored the files and confirmed they matched byte for byte.
- The running server was checked with real requests after the controller and
  view were built.
- I ran the 16-step browser smoke test in Chrome 154, and every step passed.
- Every result quoted in the README was re-checked against the code.
- A fresh clone of the committed repository was set up exactly as the README
  describes: all 177 tests passed and the server worked.
