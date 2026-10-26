# AI Transcript

## Tools used

- Claude Code (command line), model Claude Opus 5.5 (`claude-opus-5-5`).
- For the slides (stage 09): headless Google Chrome to print the HTML deck
  to PDF, and Poppler's `pdftoppm` to render the pages for checking. The
  finished recording was checked with short Swift scripts using Apple's
  AVFoundation. None of these scripts is part of the submission.

## Stage log

| Stage | Work | Tests after |
| --- | --- | --- |
| 01 | Package skeleton, supplied-AST loader, result types | 14 |
| 02 | Target terms, exact printer, names, capture-avoiding substitution | 39 |
| 03 | Single evaluator with exact budgets; source validation; examples | 78 |
| 04 | Closed Church encodings and bounded observers | 114 |
| 05 | Compositional visitor compiler | 136 |
| 06 | Lambda Arcade command-line demo and saved terms | 163 |
| 07 | Adversarial test audit | 171 |
| 08 | `README.md`, `DESIGN.md`, this transcript | 171 |
| 09 | Slide deck, speaker notes and recording checklist; slides and video added under `presentation/` | 171 |

## Presentation

Claude drafted the slide deck, timed speaker notes and a recording
checklist outside this repository. I recorded and narrated the video
myself; Claude did not generate any audio, video or images of me.

## Suggestions accepted

Claude proposed these and I kept them:

- One explicit-stack machine with a small adapter per language, so the
  variable, lambda and application cases are shared and steps are counted
  in one place. Execution is restricted to closed programs (documented);
  compilation handles open ones.
- Target nodes cache their free variables, and every target operation
  avoids Python recursion.
- Observers: a `STEP`/`BASE` spine for naturals, three-parameter `YES`/`NO`
  markers so a boolean result cannot be confused with a numeral, and one
  observation budget shared across pair components.
- Thunk parameters `u_k`/`v_k`, chosen to avoid every source name and every
  library binder, so no source name is reserved.
- The demo saves each full pure term under `MySolution/demo_terms/`, with
  default budgets set from measured needs.
- The slide deck: an HTML source printed to a 12-page PDF, prediction
  questions before results, real demo output on the slides, and the
  bottom-right corner of every slide left empty for the webcam.

## Mistakes found and fixed

- Environment: the tests failed under Python 3.9.6 (a `SyntaxError` on
  `match`), and also when a test file was run directly or discovery was
  started from inside `MySolution`. After the `PATH` fix, the documented
  commands run as modules from `assigns/06/`.
- Stage 02: one expected value that Claude wrote for a substitution test was
  wrong; the code was right. The expected result was corrected to
  `(lam y_2. ((lam y_1. y) y_2))`.
- Stage 03: a static test that searched the evaluator for the word
  "compile" matched "compiler" in a docstring. It now looks for
  `compile_expr`.
- Stage 04: one planted bug survived because a check in the spine reader was
  redundant. The check was removed, a comment explains why it is not
  needed, and two malformed-spine tests were added.
- Stage 06: one planted bug (comparing observed data with `==`) survived. With
  the real observers it cannot change a result, but a direct test now makes
  the `1` versus `true` rule explicit.
- Stage 07: one new test built a program that doubled in size at each level
  and hung. Claude stopped the run and fixed the test. A test that pinned a
  large step count was relaxed, as the pack advises.
- Stage 08: the first `DESIGN.md` draft had about 1,700 prose words; it was
  cut to under 1,500.
- Stage 09: the first rendering of the slides broke code lines in the
  middle of terms, turned `lam` into `LAM` in table headers, and used `H` on
  one slide before defining it. All three were fixed before recording.
- Final review: one sentence in `DESIGN.md` said "no beta reduction" where
  "no eta reduction" was meant; it was corrected.

## Testing actually done

- We ran the full suite at the end of every stage, with the counts in
  the stage log, all passing. The final run was 171 tests in about 2
  seconds on Python 3.14.9.
- Planted-bug checks: bugs were planted in a scratch copy outside the
  repository, the suite was run against it, and the copy was deleted.
  - Stage 03: 5 bugs, all caught.
  - Stage 04: 5 bugs; 4 caught, 1 survived, leading to the fix above.
  - Stage 05: 6 bugs, all caught.
  - Stage 06: 8 bugs; 7 caught, and the last one after the new test.
  - Stage 07: 7 bugs, all caught.
- `python3 -m MySolution.demo` passed all 14 examples with exit status 0,
  and the four-example short route passed 4 of 4.
- Presentation: every page of `slides.pdf` was checked as a rendered image.
  The final video was decoded from start to end: 28 minutes 25 seconds,
  1280×720, with audio throughout. Sampled frames show the webcam inset and
  readable slide and terminal text, including the live factorial run.
