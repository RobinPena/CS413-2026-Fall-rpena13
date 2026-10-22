# AI Transcript

## Tools used

Claude Code (Claude Opus 5.5)

## How we worked

Every file
change is shown to me as a draft or diff before it is written. Staggered claude drafts, review, repeat. Each code
change comes with tests in both suites.

The work followed an eight-step plan: setup, the pretty printer, the name
collector and fresh-name supply, the substitution visitor, extra edge-case
tests, the README and a final check from a clean copy.

## Important prompts and suggestions

- The fresh-name policy (the first unused `name_k`, avoiding every name in
  both inputs) and building the whole
  substitution visitor in one step, because the abstract methods require it.
- For the edge-case tests, Claude worked out the expected outputs by hand,
  then we ran four deliberately broken versions of substitution against the
  cases. Three of them passed all 40 existing cases. The 13 new cases catch
  all four.


## Reflection

Working this way, I spent less time writing code and more time on quality
assurance and quality control. QA was setting the rules, requirements, needs up front, QC was
checking what came back: reading diffs, asking whether a passing test proves
anything and confirming the instructions work on a clean machine. The test
suite was the clearest example. Forty passing cases looked complete, yet
three broken versions of the code passed all of them. Tests written by the
same tool that wrote the code are not evidence on their own. They need an
independent check. Is our role is shifting
from developers toward reviewers and product managers? As the days pass and AI gets better, I am more and more amazed, consequently, the more I want to go back to work projects from books like the old days. I might go ahead and do that.