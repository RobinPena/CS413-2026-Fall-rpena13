# AI Transcript

## Tools used

Claude Code (Claude Opus 5.5)

## How we worked

The work was done in 7 stages, one stage per instruction. Each stage ended
with something tangible that could be run or read, a check of it, and a short
overview. I read the overview, then asked for the next stage. Claude made no
commits; the git work was mine.

| Stage | What was built | Check after the stage |
| --- | --- | --- |
| 1. Discovery | `DESIGN.md`: 59 requirements with IDs, the architecture, the decisions, the file layout | Every ID traced to a file and a test; the real Assign07 service probed for its answers |
| 2. Contract | `API.md` (14 routes, rules, worked examples) and `api.schema.json` | The schema is valid, the route table matches Assign09.md, and all 30 example responses validate |
| 3. Data model and store | Records, validation, business rules, the in-memory store, list snapshots | 76 unit tests; 15 planted bugs, all caught |
| 4. HTTP API | Flask routes, the error envelope, CORS, `python -m MySolution` | 191 tests through the HTTP test client; 37 planted bugs; `curl` against the running service |
| 5. Studio | The studio host, storage adapter, LAMBDA3 client, run logic, and page | 204 Python tests, 25 Node tests, and 18 headless-Chrome checks against the real services; 16 planted bugs |
| 6. Docs and demo | `README.md` with the architecture diagram, and the completed `TESTING.md` | README followed in a fresh copy; examples and the studio tour matched; a restart emptied the database |
| 7. Final review | A small cleanup of `DESIGN.md` | Each rubric category checked; every cited test exists; nothing extra in the submission |

## Suggestions

Claude proposed these in the stage overviews, and I kept them:

- **A small studio host.** Assign07 refuses the browser's cross-origin check,
  and Assign07 must not be changed. A small host therefore serves the page
  and passes `POST /lambda/rpc` to Assign07 unchanged. The database service
  never touches LAMBDA source.
- **A new, small studio.** Assign03 had only requirements, and Assign08's
  client is the N-Queens animator. The studio is plain HTML and JavaScript
  with no build step, and all REST details stay in `storage.js`.
- **Immutable records and one lock per operation.** Every check and change
  happens under one lock, so racing or stale updates can't slip through.
  List snapshots keep references to the old records rather than copies.
- **Strict `If-Match`.** Only a single quoted revision such as `"3"` is
  accepted. `*` is refused because it would allow a silent overwrite.
- **Matching limits.** Source is capped at 65,536 bytes, which is LAMBDA3's
  own limit, so any stored case can be sent to LAMBDA3 unchanged.
- **Runs use frozen cases.** A run reads the saved collection and freezes
  each case before starting, so an edit made during the run can't change a
  result. Only LAMBDA3's syntax error (`-32010`) and type error (`-32011`)
  can match an expected error.

## How the result was reviewed and tested

- **Tests:**
  - 204 Python tests (unit tests, plus HTTP tests through Flask's test
    client), in about 5 seconds;
  - 25 Node tests for the studio modules;
  - 18 headless-Chrome checks against the real database service and the
    real Assign07 service.

  Every HTTP response is also checked against the JSON Schema.
- **Planted bugs:** to see whether the tests catch real bugs, we planted bugs
  in a copy of the code, one at a time:
  - 15 in the business rules;
  - 37 in the HTTP layer;
  - 18 in the studio.

  All were caught in the end. `TESTING.md` lists them.
- **Fresh copy:** Assign07 and Assign09 were copied into an empty folder
  without their virtual environments, then set up exactly as `README.md`
  says, and all three test suites passed. Then:
  - The services were started with the documented commands, on separate
    ports, because my own copies were running.
  - Every `curl` example matched the README.
  - The studio tour gave the results the README describes.
  - Restarting the database emptied it.
- **Final review:** each rubric category was checked against the evidence.
  Assign07 and Assign08 were not changed, and there are no caches or virtual
  environments in the submission.

Several of Claude's mistakes were caught by these checks:

- Two race tests had their expected results swapped. They were corrected.
- One planted bug survived: no test sent a query parameter to
  `DELETE /programs/{id}`. The tests now cover all 12 routes that take none.
- `TESTING.md` claimed a full planted-bug rerun before it had been done. Both
  reruns were then done, so the claim is true.
- Claude published `TESTING.md` as a private web page without being asked.
  It was deleted at my request.
- One planted studio bug went undetected: a run that used the page's own copy
  of the cases instead of the saved ones. Browser check F4b was added and now
  catches it.
- The README said a new collection had to be clicked to open; it opens on its
  own. The README was fixed after the studio tour.
- The browser test crashed while cleaning up, after every check had passed:
  it deleted Chrome's profile before Chrome had exited. It now waits.
