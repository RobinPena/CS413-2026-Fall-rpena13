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
| Q1 |  |  |  |
| Q2 |  |  |  |
| Q3 |  |  |  |
| Q4 |  |  |  |
| Q5 |  |  |  |

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

USER: students in course (well-verse in tech?)
    -user interests:
        - writing LAMBDA programs
        - tinkering with compiler
        - to be used in lectures


Question/Clarification
-------
    - having examples: saved as files? tabs? commented functions? copy/paste list of examples?
    - modify an example without losing acess: history saved locally? cloud? user-account?
    - easy to get started: define "easy"
