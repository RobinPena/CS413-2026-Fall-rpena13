# LAMBDA Web Testing Environment — Requirements Specification

**Dev:** Robin Pena, with Claude (Sonnet, Opus) — see `AI-TRANSCRIPT.md`

**Course:** CS413 · **Assignment:** #3 · **Due:** 2026-09-29

**At a glance:** 19 functional requirements (16 Must, 3 Should) · 7 quality requirements (5 Must,
2 Should) · 9 acceptance criteria (4 of them failure scenarios) · 9 clarification questions
(6 answered by the stakeholder, 3 resolved by explicit assumption).

| Section | Contents |
| --- | --- |
| §1–§3 | Purpose, stakeholders, and what is in and out of scope |
| §4 | Clarification questions, stakeholder answers, and assumptions |
| §5–§6 | Functional and quality requirements |
| §7–§8 | External interfaces, dependencies, and priority rationale |
| §9–§11 | Acceptance criteria, traceability, and review notes |

---

## 1. Purpose

The LAMBDA Web Testing Environment is a locally run, browser-based tool that lets students write,
compile, and run LAMBDA programs, inspect what the compiler produced, and save programs as named,
repeatable tests.

It exists to replace the current workflow of exercising the LAMBDA compiler directly through the
language tools, making it faster and less error-prone to try programs, understand results, and check
the compiler for regressions as it continues to evolve.

---

## 2. Stakeholders

| Stakeholder | Role / Interest |
| --- | --- |
| **Course instructor** | • Commissions the tool<br>• Uses it live during lectures<br>• Primary decision-maker on scope |
| **Students (program authors)** | • Write and run LAMBDA programs<br>• Want convenience over the raw language tools |
| **Students (compiler developers)** | • Modify the compiler<br>• Use the tool to check that it still works |
| **Compiler team** | • Provides the compiler interface the environment depends on<br>• Owns the source notation, which is still being decided |

---

## 3. Scope

### 3.1 In scope (first version)

**Authoring**

- Write, paste, and edit LAMBDA programs in the browser
- An example library containing both built-in "canned" examples (e.g. factorial) and programs the
  student has saved — editing a canned example never alters the stored original
- Loading a program from a local file, so existing work does not have to be retyped

**Running and results**

- "Compile only" and "run" as distinct, separately invocable actions
- Display of the computed answer or the reported error
- Optional inspection of compiler diagnostics (AST or generated code) as plain text, hidden by
  default so it does not clutter a simple run
- Explicitly stopping a compilation or a run that is in progress

**Errors and failures**

- Compile-time errors presented differently from runtime failures, in both visuals and wording
- Mapping a compiler-reported error location back to the corresponding place in the source
- Environment and connection failures presented distinctly from program errors, with the user's work
  preserved and the request retryable
- Identifying which program version produced a displayed result when the program was edited mid-run

**Tests**

- Named tests, each pairing a program with an expected outcome: a value, or "should fail to compile"
- Named collections of those tests, runnable in a single action
- A pass/fail summary, with enough detail to investigate any test that did not match expectations

**Persistence and platform**

- Explicitly saving programs and test collections locally, with no automatic background saving
- Running locally on a student's or instructor's machine, with no server deployment
- Keyboard-operable main tasks and status messages that do not depend on color alone
- Building against mock/sample compiler responses now, with the real compiler pluggable in later
  without a redesign

### 3.2 Out of scope (first version)

- Public hosting or a deployed website
- User accounts or authentication
- Multi-user real-time collaborative editing
- Sharing test collections across the class — the instructor stated they "could live without that in
  the first version"
- The compiler itself — its implementation is a separate project
- Advanced visual polish or features found in a full development environment

### 3.3 System boundary: testing environment vs. compiler

**The environment owns:**

- The editor UI and the example library
- Invoking compile and run, and displaying results and errors
- Test and test-collection management
- Local persistence and execution control (stop)
- A swappable compiler interface — mock now, real later

**The compiler owns:**

- Parsing, compiling, and executing LAMBDA source
- Producing the AST, generated code, results, and error information
- Defining the source notation, which is still unsettled at time of writing

The compiler is treated as an external, evolving dependency that the environment integrates against
rather than embeds.

---

## 4. Clarification Questions & Assumptions

Each question records why it matters and how it was resolved: either a recorded stakeholder answer, or
an explicit assumption where no answer was sought.

| # | Question | Why it matters | Resolution |
| --- | --- | --- | --- |
| **Q1** | Is the example library a small fixed built-in set, or can students add and save their own entries? | Determines the data model — examples, personal saved programs, and tests may or may not be the same thing | **Answered 2026-09-28:** *"The example library should have 'canned' examples as well as some loaded by the students."* The library holds both. |
| **Q2** | With no user accounts, is browser local storage acceptable for "don't lose my work," or is explicit file export/import required? | Local storage can be cleared by the browser, affecting the reliability requirement and whether export is a Must | **Answered 2026-09-28:** *"Yes, there should be a way for the user to export/save code into the local storage. No auto-saves, though."* Saving is an explicit user action. |
| **Q3** | Is there an expected file extension or format for LAMBDA source files? | Needed to specify the file-load requirement and check compiler interface expectations | **Assumption:** source files are plain text. The environment accepts any plain-text file, with no extension restriction, since the compiler team has not established a convention. |
| **Q4** | In what form does the compiler return AST and generated code, and should it get special rendering? | Avoids over-scoping the UI and keeps the requirement testable | **Answered 2026-09-28:** *"Returning text is fine."* Diagnostics are returned and displayed as plain text; no tree rendering required. |
| **Q5** | Is there a fixed "taking too long" threshold, or is a manual stop sufficient? | "Long time" is not verifiable as written; a testable stop behavior is needed | **Answered 2026-09-28:** *"There should be a way to explicitly stop compilation and/or execution."* No timeout; manual stop covering both phases. |
| **Q6** | For a test expecting a compile error, does passing require an exact message match, a category match, or any failure? | Determines what "worked as expected" means for negative tests | **Assumption:** a negative test passes if the compiler reports any compilation error. The brief only distinguishes "compiles" from "the compiler reject[ing] the program." |
| **Q7** | How should mock responses be marked so they are never mistaken for real results? | An explicit stakeholder concern that needs concrete UI behavior | **Answered 2026-09-28:** *"Any reasonable form of marking should be fine at this stage."* No specific format mandated. |
| **Q8** | What counts as "a browser students normally use"? | Needed to make the compatibility requirement testable | **Assumption:** the current stable release of at least one evergreen browser (e.g. Chrome or Firefox). Legacy support is out of scope for v1. |
| **Q9** | Is there a concrete target behind "easy to get started" — for example, a new student reaching a first successful run within a set number of minutes unaided — or is it meant qualitatively? | "Easy" is unverifiable as written. The answer decides whether onboarding needs its own measurable acceptance check or stays a qualitative design goal | **Answered 2026-09-29:** *"Just need to identify that this is a non-functional requirement."* No numeric target is wanted. Captured as **QR-7**. |

---

## 5. Functional Requirements

Ordered by priority: Must first, then Should. See §8 for the rationale behind each Should.

| ID | Requirement | Priority |
| --- | --- | --- |
| **FR-1** | The system shall let the user write a new LAMBDA program or paste one into an editor within the page. | Must |
| **FR-2** | The system shall provide a library of example programs containing both built-in "canned" examples and programs the student has saved. Loading a canned example into the editor and modifying it shall not alter the stored original. | Must |
| **FR-3** | The system shall let the user request compilation of the current program without executing it, and report whether compilation succeeded or failed. | Must |
| **FR-4** | The system shall let the user request that the current program be compiled and run, and report the resulting value or an error. | Must |
| **FR-5** | The system shall visibly distinguish whether a displayed result came from a compile-only check or from a run. | Must |
| **FR-6** | The system shall visibly distinguish a compilation error from a runtime failure, using different presentation and wording for each. | Must |
| **FR-7** | When the compiler reports a source location for an error, the system shall let the user locate the corresponding position in the program source, for example by highlighting or navigating to it. | Must |
| **FR-8** | The system shall distinguish a failure to reach or complete a request to the compiler from an error in the user's program, and shall not present the former as if the program were at fault. | Must |
| **FR-9** | If the system cannot reach the compiler, it shall preserve the user's current program and let the user retry the request once the problem is resolved. | Must |
| **FR-10** | The system shall let the user explicitly stop a compilation or a run that is in progress, before the compiler returns a result. | Must |
| **FR-11** | The system shall let the user explicitly save the current program or test collection to local storage. The system shall not save editor content automatically without such an explicit action. | Must |
| **FR-12** | The system shall let the user define a named test consisting of a program and an expected outcome, where the expected outcome is either a specific value, such as an integer or Boolean, or an expectation that compilation fails. | Must |
| **FR-13** | The system shall let the user organize named tests into a named collection and run all tests in that collection in one action. | Must |
| **FR-14** | After running a test collection, the system shall display a summary of how many tests matched their expected outcome, and shall let the user inspect the detail of any test that did not. | Must |
| **FR-15** | The system shall obtain compilation and execution results through a defined interface that can be backed by either mock/sample responses or a real compiler, without requiring changes to the rest of the system when switched. | Must |
| **FR-16** | When a result was produced by a mock/sample response rather than a real compiler, the system shall visibly indicate this so it is not mistaken for an actual compilation or run result. | Must |
| **FR-17** | The system shall let the user optionally view compiler-produced diagnostics, such as an abstract syntax tree or generated code, displayed as plain text, when the compiler makes them available. This information shall not be shown by default. | Should |
| **FR-18** | If the user edits and re-submits a program while a previous request for that program is still in progress, the system shall indicate which program version a displayed result corresponds to. | Should |
| **FR-19** | The system shall let the user load a LAMBDA program from a local file into the editor. | Should |

---

## 6. Quality Requirements (Non-Functional)

Each quality requirement states one property and how that property would be checked, so that no
requirement rests on an unmeasurable term such as "fast" or "easy." Each states a property that can
pass or fail independently of the others.

| ID | Requirement | How satisfaction is assessed | Priority |
| --- | --- | --- | --- |
| **QR-1** | The system shall respond to ordinary user actions — opening the page, switching examples, editing text, starting a compile, run, or stop — without waiting on the compiler. *Proposed target: visible feedback within 1 second under normal local operation, independent of compiler latency.* | Time the interval between each listed action and visible UI feedback, such as a busy indicator or an updated state. | Must |
| **QR-2** | While a compile or run request is in progress, the system shall keep the editor and main controls usable rather than freezing. | With a request in flight, attempt to edit the program and to trigger stop; confirm both are accepted rather than blocked. | Must |
| **QR-3** | The system's primary tasks — writing, compiling, running, saving, loading, and managing tests — shall be fully operable using only the keyboard. | Perform each primary task end to end without using a pointing device. | Must |
| **QR-4** | Status and error messages shall remain distinguishable without relying on color alone. | Render the interface without color, for example in grayscale, and confirm success, error, and in-progress states are still tellable apart. | Must |
| **QR-5** | A single failing or erroring test within a collection shall not prevent the remaining tests in that collection from running and reporting a result. | Build a collection containing one deliberately broken test among several valid ones, run it, and confirm the others still execute and report. | Should |
| **QR-6** | Saved programs and test collections shall survive a page reload and a full browser restart without data loss, under normal operation with no manual clearing of browser storage. | Save a program and a collection, reload the page, then fully restart the browser; confirm the content is intact after each. | Should |
| **QR-7** | A newcomer who has not used the LAMBDA compiler before shall be able to reach a first successful run using only the built-in examples and the controls visible on the page, without editing configuration or consulting compiler documentation. *The stakeholder confirmed this is a non-functional requirement and declined to set a numeric onboarding target (Q9), so none is proposed here.* | Observe a first-time user, given no verbal guidance, open the page, load a built-in example, and run it; record whether they succeed using on-screen affordances alone and where they get stuck. | Must |

---

## 7. External Interfaces & Dependencies

**Compiler interface.** The environment communicates with a LAMBDA compiler through a defined
request/response interface rather than embedding compiler logic.

- A **request** carries the program source and the requested action: compile-only, or run.
- A **response** carries either a success result — a value, or confirmation that compilation
  succeeded — or an error, including a source location when the compiler provides one.
- A response may also carry diagnostics such as an AST or generated code, returned as plain text
  (FR-17, per the Q4 answer).
- Because the source notation is still being decided, the interface treats program text as an opaque
  string rather than assuming a specific syntax.
- The interface is initially backed by mock/sample responses and is intended to be backed by the real
  compiler later with no redesign of the rest of the system (FR-15), with mock output labeled as such
  (FR-16).
- **Open dependency:** the exact interface contract must be agreed with the compiler team before
  implementation. This specification does not resolve it.

**Local persistence.** Saved programs and named test collections are stored locally on the user's own
machine, for example in browser storage, rather than on a server or shared database — consistent with
there being no user accounts in the first version (FR-11, QR-6).

**Local file system.** Loading a program (FR-19) reads a local file the user selects. No requirement is
placed on writing back to that file or on a specific extension (see Q3).

**Browser.** The environment runs inside a standard web browser on the user's own machine, with no
extensions or plugins and no hosted deployment (§3.2). Per Q8, it targets a current evergreen browser.

**Local setup.** The environment and its compiler backend, mock or real, run locally. Installation is
expected to be simple enough that another person can follow written setup instructions, per the
instructor's stated goal.

---

## 8. Priorities & Rationale

**Must** requirements form the loop the brief treats as essential: edit → compile or run → understand
the result → keep it as a repeatable test. They also cover the failure-handling and mock/real compiler
concerns the instructor raised directly (FR-8, FR-9, FR-16). Dropping any of them would leave the tool
unable to replace the current direct-tool-use workflow, which is its stated purpose. QR-7 is also a
Must: a tool the instructor cannot hand to a newcomer mid-lecture fails one of the brief's opening
goals, however well the rest of it works.

**Should** requirements are valuable but not load-bearing for that loop:

- **FR-17 — AST and generated-code inspection.** The brief frames this conditionally, "when that
  information is available," and warns it should not get in the way of simple use. It can follow once
  the compiler exposes the data.
- **FR-18 — identifying which version produced a result.** Only applies when a user edits and
  resubmits before a prior request finishes: a real case, but narrower than the main flow.
- **FR-19 — loading from a local file.** Pasting into the editor (FR-1) already meets the core need;
  file loading removes friction rather than enabling the task.
- **QR-5 and QR-6 — fault isolation and durable persistence.** These harden behavior that matters for
  trust in the tool over time, but the system remains usable within a single session without them.

**Deferred entirely** beyond the first version (§3.2): sharing collections across the class, user
accounts, multi-user collaboration, and public hosting — all explicitly de-scoped by the instructor.

---

## 9. Acceptance Criteria

Nine checks covering eleven requirements. Four are failure or exceptional scenarios: AC-3, AC-5, AC-6,
and AC-7.

### AC-1 — compile-only (FR-3)

- **Given:** the editor contains a syntactically valid LAMBDA program.
- **When:** the user requests compilation without running.
- **Then:** the system reports that compilation succeeded and displays no run result or value.

### AC-2 — run (FR-4)

- **Given:** the editor contains the built-in factorial example, unmodified.
- **When:** the user requests that the program be compiled and run.
- **Then:** the system displays the correct computed value for that example.

### AC-3 — failure scenario: compile-time vs. runtime error (FR-6)

- **Given:** the editor contains a program with a syntax error.
- **When:** the user requests a run.
- **Then:** the system reports a compilation error, using presentation and wording distinct from a
  runtime failure. It does not claim the program ran and failed.

### AC-4 — error location mapping (FR-7)

- **Given:** the editor contains a program with an error the compiler reports at a specific position.
- **When:** the user requests compilation and the error is returned.
- **Then:** the user can navigate to, or see highlighted, the corresponding position in the source.

### AC-5 — failure scenario: compiler unreachable (FR-8, FR-9)

- **Given:** the editor contains a valid program and the compiler backend is unreachable.
- **When:** the user requests a run.
- **Then:** the system reports an environment or connection failure distinct from a program error,
  keeps the program text intact, and lets the user retry the same request once the backend is
  reachable — at which point the retry succeeds.

### AC-6 — failure scenario: non-terminating program (FR-10)

- **Given:** the editor contains a recursive program that does not terminate.
- **When:** the user starts a run, then explicitly invokes stop before any result is returned.
- **Then:** the run halts, no result is presented as though it had completed, and the editor and
  controls remain usable immediately afterward. The same stop control behaves equivalently when
  invoked during compilation rather than execution.

### AC-7 — exceptional scenario: one failing test in a collection (FR-14, QR-5)

- **Given:** a named collection of three tests, one deliberately written to fail, for example with a
  wrong expected value.
- **When:** the user runs the collection.
- **Then:** the summary reports 2 passed and 1 failed, the failing test's detail is available for
  inspection, and the two passing tests report normally — the failure neither blocks nor hides them.

### AC-8 — mock response labeling (FR-16)

- **Given:** the environment is configured to use mock/sample responses, with no real compiler
  connected.
- **When:** the user runs any program.
- **Then:** the displayed result is visibly labeled as coming from a mock response, distinguishable at
  a glance from a real compiler result.

### AC-9 — persistence across reload (FR-11, QR-6)

- **Given:** the user has explicitly saved a program under a name.
- **When:** the page is reloaded, and separately, the browser is closed and reopened.
- **Then:** the saved program is still present in both cases and can be reopened with its content
  intact.

---

## 10. Traceability

Every requirement traces to a passage of the stakeholder brief, a recorded answer from §4, or an
explicit assumption.

| ID | Source |
| --- | --- |
| **FR-1** | Brief, *Trying a program*: "I imagine opening the page, typing or pasting a short program…" |
| **FR-2** | Brief, *Trying a program*: "Having a few examples to start from would help… Students should be able to modify an example without losing access to the original." Extended by the **Q1 answer**. |
| **FR-3** | Brief, *Trying a program*: "Sometimes I only want to check whether a program compiles." |
| **FR-4** | Brief, *Trying a program*: "At other times, I want to run it and see the answer." |
| **FR-5** | **Assumption**, derived from FR-3 and FR-4: two distinct actions imply their results must be told apart to avoid confusing one for the other. |
| **FR-6** | Brief, *Understanding what happened*: "A compilation error and a failure while running the program should not look like the same thing." |
| **FR-7** | Brief, *Understanding what happened*: "the environment should help the student find that place in the source." |
| **FR-8** | Brief, *Understanding what happened*: "If it cannot reach the compiler, I do not want students to think their program is wrong." |
| **FR-9** | Brief, *Understanding what happened*: "They should be able to keep their work and try again when the problem is resolved." |
| **FR-10** | Brief, *Understanding what happened*: "There should be a way to stop it and move on." Extended to compilation by the **Q5 answer**. |
| **FR-11** | Brief, *Keeping examples as tests*: "I would be frustrated if refreshing the page meant losing the examples I had prepared." Explicit-save and no-auto-save behavior per the **Q2 answer**. |
| **FR-12** | Brief, *Keeping examples as tests*: "Each test would contain a program and some record of what should happen… Some tests would expect an answer… Others would intentionally contain an error…" |
| **FR-13** | Brief, *Keeping examples as tests*: "a student could run the collection again to check whether anything has broken." |
| **FR-14** | Brief, *Keeping examples as tests*: "a quick summary of which tests worked as expected, with enough detail to investigate the ones that did not." |
| **FR-15** | Brief, *The compiler is still evolving*: "we should be able to connect the real compiler without starting the interface over again." |
| **FR-16** | Brief, *The compiler is still evolving*: "as long as nobody mistakes them for actual compilation results." Marking format left open by the **Q7 answer**. |
| **FR-17** | Brief, *Trying a program*: "inspect information the compiler produces, such as an abstract syntax tree or generated code… I do not want all of that detail to get in the way." Plain text per the **Q4 answer**. |
| **FR-18** | Brief, *Understanding what happened*: "I need to know which version produced the result I am seeing." |
| **FR-19** | Brief, *Trying a program*: "Students may already have programs saved in files, and they should not have to retype them." |
| **QR-1** | Brief, *Keeping the project manageable*: "The environment should respond promptly to ordinary actions, even when the compiler takes longer to finish." The 1-second figure is a **proposal**, not stated in the brief. |
| **QR-2** | Brief, *Understanding what happened*: "The page should remain usable while work is in progress." |
| **QR-3** | Brief, *Keeping the project manageable*: "Students should be able to perform the main tasks with a keyboard." |
| **QR-4** | Brief, *Keeping the project manageable*: "messages should make sense without depending only on colors." |
| **QR-5** | Brief, *Keeping examples as tests*: "One troublesome test should not make the rest of the collection useless." |
| **QR-6** | Brief, *Keeping examples as tests*: refresh and return-later concerns, stated as a durability standard. Reinforced by the **Q2 answer**. |
| **QR-7** | Brief, opening section: "It should be easy to get started, including for someone who has not used the compiler before." Classified as non-functional, with no numeric target, per the **Q9 answer**. |

---

## 11. Review Notes

Issues found while reviewing this specification, and how each was resolved.

**1. Duplicate persistence requirements.** An early draft carried two functional requirements both
covering "save locally and survive reload" — one traced to keeping a program, one to keeping examples
as tests. *Resolved by* merging them into FR-11, covering both programs and test collections.

**2. A quality attribute written as a functional requirement.** "The page should remain usable while
work is in progress" was first written as a functional requirement, but it describes how well the
system behaves rather than a discrete action a user invokes. *Resolved by* moving it to QR-2,
alongside the related responsiveness requirement QR-1.

**3. Uniform "Must" priority carried no signal.** The first complete pass marked nearly every
requirement Must, which does not separate essential needs from optional ones. *Resolved by* re-reading
each requirement against the brief's own emphasis — conditional phrasing such as "when that
information is available," or conveniences with a working alternative — and reassigning FR-17, FR-18,
FR-19, QR-5, and QR-6 to Should, with the reasoning recorded in §8.

**4. "Easy to get started" was captured nowhere.** The brief's "easy to get started, including for
someone who has not used the compiler before" is exactly the kind of unmeasurable phrase this
specification avoids, and an earlier draft left it covered only indirectly by the example library
(FR-2), responsiveness (QR-1), and setup notes (§7). Rather than invent an onboarding metric the brief
did not support, the gap was raised with the stakeholder as **Q9**. *Resolved by* their answer — "just
need to identify that this is a non-functional requirement" — which is now recorded as **QR-7**, with
an observational check and an explicit note that no numeric target was wanted.

**5. The same guarantee stated in two places.** Fault isolation appeared in both FR-14 and the
test-run quality requirement, and durable persistence in both FR-11 and the persistence quality
requirement — the same defect as note 1, in a different form. *Resolved by* a consistent split: the
functional requirement states the behavior the system performs, and the quality requirement states the
standard it must hold to. FR-14 now covers the summary and detail view, with isolation owned by QR-5;
FR-11 covers explicit saving, with durability owned by QR-6.

**6. A compound quality requirement was not individually testable.** Keyboard operability and
color-independent messaging were stated as a single requirement joined by "and," so one could pass
while the other failed with no way to record that. *Resolved by* splitting them into QR-3 and QR-4,
each with its own assessment method.
