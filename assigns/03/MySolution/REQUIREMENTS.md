# LAMBDA Web Testing Environment — Requirements Specification

Status: **DRAFT — work in progress**

---

## 1. Purpose

<!-- 1-2 sentences: what is this system, why does it exist. -->

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
| Q3 | Is there an expected file extension/format for LAMBDA source files students load? | Needed to specify the file-load requirement and validate compiler interface expectations | Unresolved (not sent — see below) |
| Q4 | In what form will the compiler return AST/generated code (structured JSON vs. plain text)? Should it get special rendering or just be shown as text? | Avoids over-scoping the UI; keeps the requirement testable | Sent to instructor 2026-09-28 — awaiting reply |
| Q5 | Is there a fixed time threshold before a run is flagged as "taking too long," or is a manual stop button (anytime) sufficient? | "Long time" is vague; need a testable stop behavior | Sent to instructor 2026-09-28 — awaiting reply |
| Q6 | For a test expecting a compile error, does "pass" require an exact error message match, an error category match, or just any failure? | Directly determines what "worked as expected" means for negative tests | Unresolved (not sent — see below) |
| Q7 | How should mock/sample compiler responses be visibly marked so they're never mistaken for real results? | Explicit stakeholder concern in the brief; needs a concrete UI behavior | Sent to instructor 2026-09-28 — awaiting reply |
| Q8 | What counts as "a browser students normally use" — a specific minimum set (e.g., current Chrome/Firefox) or broad compatibility? | Needed to make the compatibility quality requirement testable | Unresolved (not sent — see below) |

---

## 5. Functional Requirements

<!-- FR-<n>, one behavior per requirement, testable, "the system shall ..." -->

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-1 |  | Must |

---

## 6. Quality Requirements

<!-- QR-<n>: usability, reliability, responsiveness, etc. Define how satisfaction is assessed. -->

| ID | Requirement | Priority |
| --- | --- | --- |
| QR-1 |  | Must |

---

## 7. External Interfaces & Dependencies

<!-- Compiler interface, file system/local storage, browser, sample/mock responses during compiler development. -->

---

## 8. Priorities & Rationale

<!-- Must / Should / Could, and why. What waits until later versions. -->

---

## 9. Acceptance Criteria

<!-- At least 6 requirements, at least 2 failure/exceptional scenarios. -->

### AC-1 (for FR-?)

- **Given:**
- **When:**
- **Then:**

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
