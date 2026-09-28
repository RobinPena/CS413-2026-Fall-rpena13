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

<!-- bullets -->

### 3.2 Out of scope (first version)

<!-- bullets -->

### 3.3 System boundary: testing environment vs. compiler

<!-- Explicitly separate what the UI/environment owns vs. what belongs to the compiler team. -->

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

## Appendix: Working Notes (raw, pre-draft)

costumer wants:
    - web based env to try out lambda comp:
    - work directly with language tools
    - looking for conveniency
    - should compile and stop or run

USER: students in course
    -user interests:
        - writing LAMBDA programs
        - tinkering with compiler
        - to be used in lectures


Question/Clarification
-------
    - having examples: saved as files? tabs? commented functions? copy/paste list of examples?
    - modify an example without losing acess: history saved locally? cloud? user-account?
    - easy to get started: define "easy"
