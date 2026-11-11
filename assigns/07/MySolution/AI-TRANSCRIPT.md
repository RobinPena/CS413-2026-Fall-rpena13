# AI Transcript

## Tools used

Claude Code (Claude Opus 5.5)

## How we worked

The work was done in 7 stages:

   0. discovery
1. the contract (`RPC.md`, the JSON Schema and a test plan)
2. the HTTP transport and JSON-RPC dispatcher
3. the LAMBDA3 methods in a worker process
4. acceptance and failure testing
5. documentation
6. a final review

We did one stage per instruction and ended each with a review packet:
outcome, files, the checks actually run, open decisions, and the next stage.


## Suggestions


Some design decisions came from Claude's suggestions in the review packets, which I accepted or changed:

- **Every `lambda.*` call runs in a new spawned process with a 2-second
  deadline.** This includes type checking. Type inference can take
  exponential time: during discovery, a 379-byte program took more than
  8 seconds to type-check. When the deadline passes, the worker is
  terminated, killed if it is still alive half a second later, and then
  waited on, so nothing keeps running in the background.
- **Error codes.**
  - `-32010` for syntax errors.
  - `-32011` for type errors. An unbound variable counts as one, because
    LAMBDA3's type checker reports it.
  - `-32012` for a timeout.
  - `-32013` for runtime errors. This was Claude's suggestion, and I chose
    it.
- **Recursion limit.** Claude suggested raising Python's recursion limit
  inside the worker. I chose to leave it at the default. As a result,
  recursion deeper than about 140 LAMBDA calls gets `-32013`, and `RPC.md`
  documents this.
- **No Python details in error messages.** When Python's own limits are hit,
  the client gets a fixed sentence instead of Python's message. Such limits
  include nesting too deep, an integer too long to convert, and the
  recursion limit. Python's messages included advice such as calling
  `sys.set_int_max_str_digits()`, which means nothing to a LAMBDA user.
  Unexpected failures return only an incident ID, and the details go to the
  server log.
- **Tests that check the documentation.** The examples in `RPC.md` §7 are
  replayed as a test, and compiled code is compared with LAMBDA3's compilers
  called directly. Neither the docs nor the fixtures can drift from what the
  service does.

## How the result was reviewed and tested

- **Local suite:** 114 HTTP-level tests run through Flask's test client.
  Successful results always come from the real LAMBDA3 in a real worker
  process. Timeouts are tested with real programs that run too long. The
  crash and hang tests use three stand-in workers, which run inside the
  spawned process: one hangs and ignores SIGTERM, one exits without
  answering, and one has a compiler that raises.
- **Mutation checks:** to see whether the tests could catch real bugs,
  We planted bugs in a copy of the code, one at a time, and ran the
  suite. Stage 2 used 4 bugs, Stage 3 used 10 and Stage 4 used 6, and every
  one was caught. A deadline three times too long and a worker that is never
  killed are two examples. `TESTING.md` lists them all.
- **Instructor suite:** run unchanged against a live server, it passed 15 of
  15. My own first run failed every test with `Connection refused`, because
  the server wasn't running. `README.md` now explains the two-terminal setup.
- **Clean copy:** the committed files were unpacked into an empty directory
  and installed into a new virtual environment from `requirements.txt`.
  Then the documented commands were run. Every curl example in `README.md`
  was run as written against a live server and compared with the response
  shown under it.

Several of Claude's mistakes were caught by these checks: 
- An early test for discarding `print` output passed whether or not the
  output was discarded. It was rewritten to capture the worker's real
  standard output.
- The first mutation counts written into `TESTING.md` came from an older
  version of the suite. They were rerun and corrected.
- A bug planted on purpose (terminating a worker without killing it) hung
  the test run and left two worker processes behind. They were killed, and
  the mutation script now stops a hung run itself.