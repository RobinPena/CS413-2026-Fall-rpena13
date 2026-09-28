# LAMBDA Web Testing Environment — Requirements Specification

Status: **DRAFT — work in progress**

---

## 1. Purpose

The LAMBDA Web Testing Environment is a locally run, browser-based tool that lets students write,
compile, and run LAMBDA programs. It lets them inspect what the compiler produced, and save programs as named,
repeatable tests. It exists to replace the current workflow of exercising the LAMBDA compiler directly
through the language tools, making it faster and less error-prone for students and the instructor to
try programs, understand results, and check the compiler for regressions as it continues to evolve.

## 2. Stakeholders

| Stakeholder | Role / Interest |
| --- | --- |
| Course instructor | Commissions the tool; uses it in lectures; primary decision-maker on scope |
| Students (program authors) | Write and run LAMBDA programs; want convenience over the raw tools |
| Students (compiler developers) | Modify the compiler; use the tool to check it still works |
| Compiler team | Provides the compiler interface the environment depends on |

## 3. Scope

### 3.1 In scope (first version)

- Write/paste and edit LAMBDA programs in-browser
- Built-in starter examples (e.g. factorial) that can be modified without altering the original
- "Compile only" and "run" as distinct, separately invocable actions
- Display of results: computed answer, or error
- Optional inspection of AST / generated code, hidden by default so it does not clutter simple runs
- Distinguishing compile-time errors from runtime failures, visually and in wording
- Mapping a compiler-reported error location back to the source (e.g. highlight/jump to line)
- Distinguishing an environment/connection failure from a problem in the student's program; work is preserved and retry is possible
- Stopping a long-running or non-terminating program; the page remains responsive meanwhile
- Tracking which program version produced a given displayed result, if the program is edited mid-run
- Loading a program from a local file (no retyping)
- Saving a program locally and resuming it in a later session, surviving a page refresh
- Named test collections: a program paired with an expected outcome (a value, or "should fail to compile")
- Running a whole test collection; a pass/fail summary; one failing test does not block the rest
- Keyboard-operable main tasks; status/error messages that do not rely on color alone
- Running locally on a student's or instructor's machine; no server deployment required
- Building the interface against mock/sample compiler responses now, with the real compiler pluggable in later without redesign

### 3.2 Out of scope (first version)

- Public hosting / a deployed website
- User accounts or authentication
- Multi-user real-time collaborative editing
- Sharing test collections across the class (stakeholder: "could live without that in the first version")
- The compiler itself — its implementation is a separate project; the environment only consumes its interface
- Advanced visual polish or features found in a full development environment

### 3.3 System boundary: testing environment vs. compiler

- **Environment owns:** editor UI, example library, compile/run invocation, result and error display, test collection management, local persistence, execution control (stop), and a swappable compiler interface (mock now, real later).
- **Compiler owns:** parsing, compiling, and executing LAMBDA source; producing the AST, generated code, results, and error information; defining the source notation (still unsettled at time of writing). Treated as an external, evolving dependency the environment integrates against rather than embeds.

---

## 4. Clarification Questions & Assumptions

For each open point: the question, why it matters, and either a recorded stakeholder answer, an explicit assumption, or "unresolved."

| # | Question | Why it matters | Answer / Assumption / Unresolved |
| --- | --- | --- | --- |
| Q1 | Is the example library a small fixed built-in set, or can students add/save their own entries to it? | Determines data model: examples vs. personal saved programs vs. tests may or may not be the same thing | Sent to instructor 2026-09-28 — awaiting reply |
| Q2 | Given no user accounts, is browser local storage acceptable for "don't lose my work on refresh / return later," or is explicit file export/import required? | Local storage can be cleared by the browser; affects reliability requirement and whether export is a Must | Sent to instructor 2026-09-28 — awaiting reply |
| Q3 | Is there an expected file extension/format for LAMBDA source files students load? | Needed to specify the file-load requirement and validate compiler interface expectations | Assumption: source files are plain text; the environment accepts any plain-text file for loading (no extension restriction), since no file-format convention has been established by the compiler team as of this writing |
| Q4 | In what form will the compiler return AST/generated code (structured JSON vs. plain text)? Should it get special rendering or just be shown as text? | Avoids over-scoping the UI; keeps the requirement testable | Sent to instructor 2026-09-28 — awaiting reply |
| Q5 | Is there a fixed time threshold before a run is flagged as "taking too long," or is a manual stop button (anytime) sufficient? | "Long time" is vague; need a testable stop behavior | Sent to instructor 2026-09-28 — awaiting reply |
| Q6 | For a test expecting a compile error, does "pass" require an exact error message match, an error category match, or just any failure? | Directly determines what "worked as expected" means for negative tests | Assumption: a negative test passes if the compiler reports any compilation error for that program; the specific message or error category is not required to match, since the brief only distinguishes "compiles" from "the compiler reject[ing] the program" |
| Q7 | How should mock/sample compiler responses be visibly marked so they're never mistaken for real results? | Explicit stakeholder concern in the brief; needs a concrete UI behavior | Sent to instructor 2026-09-28 — awaiting reply |
| Q8 | What counts as "a browser students normally use" — a specific minimum set (e.g., current Chrome/Firefox) or broad compatibility? | Needed to make the compatibility quality requirement testable | Assumption: the environment targets the current stable release of at least one evergreen browser (e.g. Chrome or Firefox); broad legacy-browser support is out of scope for the first version, consistent with the brief's emphasis on a small, manageable first version |

---

## 5. Functional Requirements

<!-- FR-<n>, one behavior per requirement, testable, "the system shall ..." -->

Ordered by priority (Must, then Should); see §8 for rationale on the Should items.

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-1 | The system shall let the user write a new LAMBDA program or paste one into an editor within the page. | Must |
| FR-2 | The system shall provide a set of built-in starter example programs (e.g. a factorial example) that the user can load into the editor and modify without altering the original stored example. | Must |
| FR-3 | The system shall let the user request compilation of the current program without executing it, and report whether compilation succeeded or failed. | Must |
| FR-4 | The system shall let the user request that the current program be compiled and run, and report the resulting value or an error. | Must |
| FR-5 | The system shall visibly distinguish, in the displayed result, whether it came from a compile-only check or from a run. | Must |
| FR-6 | The system shall visibly distinguish a compilation error from a runtime failure, using different presentation and wording for each. | Must |
| FR-7 | When the compiler reports a source location for an error, the system shall let the user locate the corresponding position in the program source (e.g. by highlighting or navigating to it). | Must |
| FR-8 | The system shall distinguish a failure to reach or complete a request to the compiler from an error in the user's program, and shall not present the former as if the program were at fault. | Must |
| FR-9 | If the system cannot reach the compiler, it shall preserve the user's current program and let the user retry the request once the problem is resolved. | Must |
| FR-10 | The system shall let the user stop a program that is running, before the compiler returns a result. | Must |
| FR-11 | The system shall persist saved programs and named test collections locally such that they remain available after the page is reloaded or the browser is closed and reopened. | Must |
| FR-12 | The system shall let the user define a named test consisting of a program and an expected outcome, where the expected outcome is either a specific value (e.g. an integer or Boolean) or an expectation that compilation fails. | Must |
| FR-13 | The system shall let the user organize named tests into a named collection and run all tests in a collection in one action. | Must |
| FR-14 | After running a test collection, the system shall display a summary of how many tests matched their expected outcome, and shall let the user inspect the detail of any test that did not, without a failing test preventing the rest of the collection from running. | Must |
| FR-15 | The system shall obtain compilation and execution results through a defined interface that can be backed by either mock/sample responses or a real compiler, without requiring changes to the rest of the system when switched. | Must |
| FR-16 | When a result was produced by a mock/sample compiler response rather than a real compiler, the system shall visibly indicate this so it is not mistaken for an actual compilation or run result. | Must |
| FR-17 | The system shall let the user optionally view compiler-produced diagnostic information (such as an abstract syntax tree or generated code) when the compiler makes it available, without showing this information by default. | Should |
| FR-18 | If the user edits and re-submits a program while a previous request for that program is still in progress, the system shall indicate which program version a displayed result corresponds to. | Should |
| FR-19 | The system shall let the user load a LAMBDA program from a local file into the editor. | Should |

---

## 6. Quality Requirements

<!-- QR-<n>: usability, reliability, responsiveness, etc. Define how satisfaction is assessed. -->

Ordered by priority (Must, then Should).

| ID | Requirement | How satisfaction is assessed | Priority |
| --- | --- | --- | --- |
| QR-1 | The system shall respond to ordinary user actions (opening the page, switching examples, editing text, starting a compile/run/stop) without waiting on the compiler. *Proposal: visible feedback within 1 second under normal local operation, independent of compiler latency.* | Time the interval between the user action and visible UI feedback (e.g. a busy indicator or updated state) across the listed actions. | Must |
| QR-2 | While a compile or run request is in progress, the system shall keep the editor and other main controls usable (editing, starting a new action, requesting stop) rather than freezing. | With a request in flight, attempt to edit the program and to trigger stop; confirm both are accepted rather than blocked. | Must |
| QR-3 | The system's primary tasks (writing, compiling, running, saving/loading, and managing tests) shall be operable using only the keyboard, and status/error messages shall be distinguishable without relying on color alone. | Perform each primary task using only the keyboard; render the interface without color (e.g. grayscale) and confirm success/error states remain distinguishable. | Must |
| QR-4 | A single failing or erroring test within a collection shall not prevent the remaining tests in that collection from running and reporting a result. | Build a collection containing one deliberately broken test among several valid ones; run the collection; confirm the others still execute and report. | Should |
| QR-5 | Saved programs and test collections shall survive a page reload and a full browser restart without data loss, under normal operation (no manual clearing of browser storage). | Save a program/collection, reload the page, then fully restart the browser; confirm the content is intact both times. | Should |

---

## 7. External Interfaces & Dependencies

- **Compiler interface.** The environment communicates with a LAMBDA compiler through a defined
  request/response interface, not by embedding compiler logic itself. A request carries the program
  source and the requested action (compile-only or run); a response carries either a success result
  (a value, or confirmation of successful compilation) or an error (with a source location when the
  compiler provides one), and may optionally include diagnostic data such as an AST or generated code
  (FR-17). The source notation the compiler expects is still being decided by the compiler team at time
  of writing, so the interface treats program text as an opaque string rather than assuming a specific
  syntax. This interface is initially backed by mock/sample responses and is intended to be backed by the
  real compiler later without requiring the rest of the system to be redesigned (FR-15), with mock output
  visibly labeled as such (FR-16). Coordinating the exact interface contract with the compiler team is
  necessary before implementation and is called out as an open dependency, not resolved by this
  specification.
- **Local persistence.** Saved programs and named test collections are stored locally on the user's own
  machine (e.g. browser storage) rather than on a server or shared database, consistent with there being
  no user accounts in the first version (FR-11).
- **Local file system.** Loading a program from a file (FR-19) reads a local file the user selects; no
  requirement is placed on writing back to that same file or on a specific file extension (§4, Q3 —
  assumption: plain text, any extension).
- **Browser.** The environment runs inside a standard web browser on the user's own machine, without
  browser extensions or plugins, and without a hosted/public deployment (§3.2). Per §4 Q8, it targets a
  current evergreen browser (e.g. Chrome or Firefox) rather than broad legacy support.
- **Local setup.** The environment and its (mock or real) compiler backend run locally on a student's or
  instructor's computer; installation is expected to be simple enough for someone else to follow written
  setup instructions, per the instructor's stated goal of a straightforward setup.

---

## 8. Priorities & Rationale

**Must** requirements form the essential loop the brief describes as non-negotiable: edit → compile/run →
understand the result → save it as a repeatable test, plus the failure-handling and mock/real compiler
concerns the instructor raised explicitly (FR-8, FR-9, FR-16). Dropping any of these would leave the
tool unable to replace the current direct-tool-use workflow, which is its stated purpose.

**Should** requirements are valuable but not load-bearing for that core loop:

- **FR-17** (AST/generated-code inspection) — the brief frames this as conditional ("when that information
  is available") and explicitly says it should not get in the way of simple use. It can be added once the
  compiler exposes this data without blocking the first version.
- **FR-18** (tracking which program version produced a displayed result) — only matters when a user edits
  and resubmits before a prior request finishes; a real but narrower edge case than the main flow.
- **FR-19** (loading a program from a local file) — pasting into the editor (FR-1) already satisfies the
  core need; file loading removes retyping friction but is not required to use the system.

**Quality requirements QR-4 and QR-5** are marked Should for a similar reason: they harden behavior
(fault isolation in a test run, persistence surviving a full browser restart) that matters for trust in
the tool over time, but the system is still usable for a single session without them.

Deferred beyond the first version entirely (see §3.2): sharing test collections across the class, user
accounts, multi-user collaboration, and public hosting — all explicitly de-scoped by the instructor.

---

## 9. Acceptance Criteria

<!-- At least 6 requirements, at least 2 failure/exceptional scenarios. -->

### AC-1 (for FR-3 — compile-only)

- **Given:** the editor contains a syntactically valid LAMBDA program.
- **When:** the user requests compilation without running.
- **Then:** the system reports that compilation succeeded, and does not display a run result or value.

### AC-2 (for FR-4 — run)

- **Given:** the editor contains the built-in factorial example, unmodified.
- **When:** the user requests that the program be compiled and run.
- **Then:** the system displays the correct computed value for that example.

### AC-3 (for FR-6 — failure scenario: compile-time vs. runtime error)

- **Given:** the editor contains a program with a syntax error.
- **When:** the user requests a run.
- **Then:** the system reports a compilation error, using presentation and wording distinct from a
  runtime failure — it does not claim the program ran and failed.

### AC-4 (for FR-7 — error location mapping)

- **Given:** the editor contains a program with an error the compiler reports at a specific line/position.
- **When:** the user requests compilation and the error is returned.
- **Then:** the user can navigate to or see highlighted the corresponding position in the source editor.

### AC-5 (for FR-8, FR-9 — failure scenario: compiler unreachable)

- **Given:** the editor contains a valid program, and the compiler backend is unreachable (e.g. not
  running).
- **When:** the user requests a run.
- **Then:** the system reports an environment/connection failure distinct from a program error, keeps
  the program text intact, and lets the user retry the same request once the backend becomes reachable,
  at which point the retry succeeds.

### AC-6 (for FR-10 — failure/exceptional scenario: non-terminating program)

- **Given:** the editor contains a recursive program that does not terminate.
- **When:** the user starts a run, then invokes stop before any result is returned.
- **Then:** the run halts, no result is presented as if it had completed, and the editor and controls
  remain usable immediately afterward.

### AC-7 (for FR-13, FR-14 — exceptional scenario: one failing test in a collection)

- **Given:** a named test collection containing three tests, one of which is deliberately written to
  fail (e.g. wrong expected value).
- **When:** the user runs the collection.
- **Then:** the summary reports 2 passed / 1 failed, the failing test's detail is available for
  inspection, and the two passing tests show their results normally (the failing test does not block or
  hide them).

### AC-8 (for FR-16 — mock response labeling)

- **Given:** the environment is configured to use mock/sample compiler responses (no real compiler
  connected).
- **When:** the user runs any program.
- **Then:** the displayed result is visibly labeled as coming from a mock/sample response, distinguishable
  at a glance from a real compiler result.

### AC-9 (for FR-11 — persistence across reload)

- **Given:** the user has saved a program under a name.
- **When:** the page is reloaded (or the browser is closed and reopened).
- **Then:** the saved program is still present and can be reopened with its content intact.

---

## 10. Traceability

| Requirement ID | Source (brief passage / answer / assumption) |
| --- | --- |
| FR-1 |  |

---

## 11. Review Notes

<!-- At least 3 issues found in the draft and how they were addressed. -->

1.
2.
3.

---
