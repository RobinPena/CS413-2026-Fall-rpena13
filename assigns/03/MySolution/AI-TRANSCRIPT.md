# AI Transcript

## Tool used

Claude Code (Anthropic), model Sonnet 5, used interactively in the terminal against this repository
throughout the drafting of `REQUIREMENTS.md`.

## Workflow

We agreed on an approach before drafting anything: read and skim the informal brief and note what
stood out, then combine notes to work out scope/requirements/open questions, and only then write the
final specification. The AI was instructed explicitly not to run any
version control actions, those were left to the user to perform manually.

The document was built section by section, roughly in this order: document skeleton
(matching the assignment's 11 required elements) → Scope → Clarification Questions → locked-in
assumptions for unanswered questions → Purpose → Functional Requirements → priority pass + Quality
Requirements → External Interfaces & Dependencies → Acceptance Criteria → recording real stakeholder
answers and propagating them into affected requirements → Traceability → Review Notes.

## Significant AI-generated suggestions

- The initial `REQUIREMENTS.md` skeleton (Purpose, Stakeholders, Scope, Clarification Questions,
  Functional/Quality Requirements, External Interfaces, Priorities, Acceptance Criteria, Traceability,
  Review Notes), matching the assignment's evaluation criteria section by section.
- Draft Acceptance Criteria (9 total, 4 of them failure/exceptional scenarios), Traceability entries
  tying every requirement back to a brief passage, a recorded answer, or an explicit assumption, and
  Review Notes identifying issues found in the draft (see `REQUIREMENTS.md` §11).
- Grammar checks and "eye-candy" edits.

## Significant user corrections and decisions

- The user chose which 5 of the 8 drafted clarification questions were actually worth sending to the
  instructor (Q1, Q2, Q4, Q5, Q7), and supplied the instructor's real answers, which were recorded
  verbatim rather than paraphrased or invented.
- For the 3 questions not sent (Q3, Q6, Q8), the user directed that assumptions be locked in rather than
  left unresolved, and reviewed the specific assumption wording proposed for each.
- A reorganization pass that merged two functional requirements that turned out to describe the same
  save/persist behavior, moved one requirement ("the page stays usable while work is in progress") out
  of Functional Requirements and into Quality Requirements because it describes a quality attribute
  rather than a discrete action, and re-assigned priorities (Must vs. Should) based on how conditionally
  or firmly the brief stated each need — bringing the functional requirement count from 21 down to 19,
  inside the assignment's suggested 12–20 range.
- The user edited the working notes directly at points (grammar fixes, removing scratch content) rather
  than delegating every edit to the AI.
- The user directed a review of priority assignments after noticing the first draft marked nearly every
  requirement "Must," which was corrected into a Must/Should split with recorded rationale (§8).
- The user is treating this document as still in draft status pending a final read-through before
  submission, and has not authorized any commit or push of these files.

## How the output was reviewed

Each section was produced in conversation and left visible for the user to read before the next section
was started, rather than generating the whole document unattended. Concrete stakeholder answers
(obtained by the user, outside this tool) were used to correct AI-proposed assumptions where they existed, and the AI was asked to point out where those answers required propagating changes
into already-drafted requirements, which
was then checked against the updated table. A dedicated pass was requested specifically to catch
redundant or misclassified requirements and priority-labeling problems. A full final read-through of the assembled document, plus the
decision on the outstanding follow-up question, was done by the user before final submission.
