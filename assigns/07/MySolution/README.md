# Assign07: LAMBDA3 as a JSON-RPC 2.0 Service

A local HTTP service that offers the supplied LAMBDA3 implementation
(`../LAMBDA3/lambda3.py`) as JSON-RPC 2.0 methods at a single endpoint,
`POST /rpc`:

| Method | What it does |
| --- | --- |
| `service.health` | Reports that the service is up, with its API version. |
| `lambda.typecheck` | Parses and type-checks a LAMBDA program and returns its type. |
| `lambda.interpret` | Type-checks the program, evaluates it, and returns its type and formatted value. |
| `lambda.compile` | Type-checks the program and returns LAMBDA3's Python or JavaScript translation as text. |

LAMBDA3 does all of the language work and is imported unchanged. Each
`lambda.*` call runs in a new worker process with a 2-second deadline.

The full contract is in [`RPC.md`](RPC.md): envelope rules, parameters, error
codes, limits, batches, and worked examples. The JSON Schema is
[`rpc.schema.json`](rpc.schema.json). [`TESTING.md`](TESTING.md) maps each
required behavior to its tests, shows the architecture, and records the
observed results.

## Requirements

- Python 3.12 or later, because `lambda3.py` uses `type` statements.
  Developed and tested with Python 3.14.10 on macOS.
- Flask 3.1.3 (with Werkzeug 3.1.9) for HTTP, and jsonschema 4.26.0 for the
  tests. These and their dependencies are pinned in `requirements.txt`.
- `curl`, for the examples below.

## Setup

From the repository root:

```bash
cd assigns/07
python3 -m venv MySolution/.venv
MySolution/.venv/bin/python -m pip install -r MySolution/requirements.txt
```

If `python3 --version` reports a version older than 3.12, create the virtual
environment with a newer interpreter instead, for example
`python3.14 -m venv MySolution/.venv`.

On Windows (not tested), use `py -3.14 -m venv MySolution\.venv`, then
`MySolution\.venv\Scripts\python` in place of `MySolution/.venv/bin/python`.

Run every command below from `assigns/07`.

## Running the tests

**Local suite** (114 tests, about 17 seconds):

```bash
MySolution/.venv/bin/python -m unittest discover -s MySolution/tests -t . -v
```

These tests send HTTP requests through Flask's test client, so they don't need
a running server. Every successful type check, interpretation and compilation
runs the real LAMBDA3 in a real worker process. Most of the time goes to
waiting out real 2-second deadlines.

**Instructor suite** (`TEST/`, 15 tests). It sends requests to a running
server, so it needs two terminals. In the first, start the server and leave it
running:

```bash
MySolution/.venv/bin/python -m MySolution --host 127.0.0.1 --port 8000
```

Wait until it prints `Running on http://127.0.0.1:8000`. Then, in the second
terminal:

```bash
python3 -m unittest discover -s TEST -v
```

If no server is running, every test fails with `Connection refused`. To test a
server on another port, set `LAMBDA_RPC_URL`:

```bash
LAMBDA_RPC_URL=http://127.0.0.1:9000/rpc python3 -m unittest discover -s TEST -v
```

Stop the server with Ctrl+C. Running the tests writes `__pycache__`
directories. Git ignores them, and `python3 -B` doesn't write them at all.

## Starting the service

```bash
MySolution/.venv/bin/python -m MySolution
```

The endpoint is `http://127.0.0.1:8000/rpc`. Every request is a `POST` with
`Content-Type: application/json`.

| Option | Default | Meaning |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Interface to listen on |
| `--port` | `8000` | TCP port |
| `--deadline` | `2.0` | Seconds allowed for each `lambda.*` call |
| `--max-source-bytes` | `65536` | Largest `source` parameter, in UTF-8 bytes |

`--deadline` and `--max-source-bytes` must be finite and greater than 0. This
is Flask's built-in development server, and it prints a warning saying so. It
is meant for local use only.

## Examples

These were run on 2026-11-10 against a server started with the default
options. Each response is shown below its command.

**Health:**

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "service.health", "params": {}, "id": 1}'
```

```json
{"jsonrpc": "2.0", "result": {"status": "ok", "version": "1.0"}, "id": 1}
```

**Type check:**

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "lam (x: sint) => x * 2"}, "id": 2}'
```

```json
{"jsonrpc": "2.0", "result": {"type": "sint -> sint"}, "id": 2}
```

**Interpretation of factorial:**

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end"}, "id": 3}'
```

```json
{"jsonrpc": "2.0", "result": {"type": "sint", "value": "720"}, "id": 3}
```

**A tuple and a list:**

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "(1 + 2, list_cons(true, list_nil()))"}, "id": 4}'
```

```json
{"jsonrpc": "2.0", "result": {"type": "(sint, List[bool])", "value": "(3, [true])"}, "id": 4}
```

**An unbound variable.** LAMBDA3's type checker rejects it, so the error is a
type error, `-32011`:

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "missing_name + 1"}, "id": 5}'
```

```json
{"jsonrpc": "2.0", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"diagnostic": "unbound variable 'missing_name'"}}, "id": 5}
```

**A type error.** The program is rejected before it is evaluated:

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "(lam (x: sint) => x)(true)"}, "id": 6}'
```

```json
{"jsonrpc": "2.0", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"diagnostic": "function application: expected sint, got bool"}}, "id": 6}
```

**A syntax error** has its own code, `-32010`, and the error's position:

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "if then"}, "id": 7}'
```

```json
{"jsonrpc": "2.0", "error": {"code": -32010, "message": "LAMBDA syntax error", "data": {"diagnostic": "Expected an expression", "line": 1, "column": 4}}, "id": 7}
```

**A runtime error**, `-32013`. The program is well typed but fails during
evaluation:

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "1 / 0"}, "id": 8}'
```

```json
{"jsonrpc": "2.0", "error": {"code": -32013, "message": "LAMBDA runtime error", "data": {"diagnostic": "division by zero"}}, "id": 8}
```

**Compilation to Python.** The response is
`{"jsonrpc": "2.0", "result": {"target": "python", "code": "..."}, "id": 9}`.
This command prints the `code` string:

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "lambda.compile", "params": {"source": "1 + 2", "target": "python"}, "id": 9}' \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["result"]["code"])'
```

The code is 4,872 characters. It starts with the runtime helpers that LAMBDA3
puts in front of every program, and it ends with the program itself:

```python
def _lambda_main():
    _v1 = 1
    _v2 = 2
    _v3 = (_v1 + _v2)
    return _v3

_lambda_result = _lambda_main()
```

The whole response is in
[`examples/compile-python-response.json`](examples/compile-python-response.json).

**Compilation to JavaScript.** This is the same request with
`"target": "javascript"`:

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "lambda.compile", "params": {"source": "1 + 2", "target": "javascript"}, "id": 10}' \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["result"]["code"])'
```

The code is 4,996 characters, and it ends with:

```javascript
function _lambda_main() {
  let _v1 = 1;
  let _v2 = 2;
  let _v3 = (_v1 + _v2);
  return _v3;
}
const _lambda_result = _lambda_main();
```

The whole response is in
[`examples/compile-javascript-response.json`](examples/compile-javascript-response.json).

**A supplied library.** A program can include the declarations from
`../LAMBDA3/mylib/` in a `let`. This command builds that request from
`list.lam`, so the file's text doesn't need escaping by hand:

```bash
python3 -c 'import json; library = open("LAMBDA3/mylib/list.lam").read(); print(json.dumps({"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": f"let\n{library}\nin list_length(list_range(0, 3)) end"}, "id": 11}))' \
  | curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' --data-binary @-
```

```json
{"jsonrpc": "2.0", "result": {"type": "sint", "value": "3"}, "id": 11}
```

The test `test_methods.InterpretTests.test_supplied_list_library` checks the
same request.

**A timeout.** This program terminates, but it needs about 11 seconds, which
is far past the deadline:

```bash
curl -s -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let fib : sint -> sint = fix fib(n: sint): sint => if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(26) end"}, "id": 12}'
```

The answer arrived 2.01 seconds after the request was sent:

```json
{"jsonrpc": "2.0", "error": {"code": -32012, "message": "Execution timed out", "data": {"limit_seconds": 2.0}}, "id": 12}
```

**A notification** is a request without an `id`. The service runs it, then
answers HTTP 204 with an empty body:

```bash
curl -s -i -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc": "2.0", "method": "service.health", "params": {}}'
```

```text
HTTP/1.1 204 NO CONTENT
Server: Werkzeug/3.1.9 Python/3.14.10
Date: Wed, 11 Nov 2026 00:56:47 GMT
Connection: close
```

Werkzeug writes the reason phrase in capitals, and HTTP clients ignore it.
[`RPC.md`](RPC.md) §7 has more examples, including a batch, malformed JSON,
an invalid request, and a transport error.

## Generated code is not run

`lambda.compile` returns the code from LAMBDA3's compiler (`d0exp_compile` or
`d0exp_compile_js`) as a JSON string, exactly as the compiler produced it. The
service never runs that code:
- It uses no `exec`, no `eval` and no JavaScript runtime.
- The worker process only calls LAMBDA3's parser, type checker, evaluator and
  compilers.
- Compiling doesn't evaluate the program. `1 / 0` and the slow `fib(26)`
  program both compile at once, with no runtime error and no timeout, as
  `test_methods.CompileTests.test_compile_does_not_evaluate` checks.

Running the generated code is up to whoever receives it, outside the service.

## Timeouts

- Each `lambda.*` call runs in a new worker process with a 2-second
  wall-clock deadline. The deadline starts before the process does, and it
  covers parsing and type checking too, which matters because type inference
  can take exponential time.
- When the deadline passes, the service:
  1. terminates the worker,
  2. kills it if it is still alive half a second later,
  3. waits for it to exit,
  4. answers `-32012`.
- The computation doesn't continue in the background.
- A timeout means only that the program didn't finish within the deadline.
  **It does not mean the program never terminates.** `fib(26)` above does
  terminate. The service makes no attempt to decide termination.
- Notifications and batch members have the same deadline. The members of a
  batch run one after another.

## Limits and scope

- **Limits:** a `source` may be at most 65,536 bytes, a request body at most
  1 MiB, and a batch at most 20 members.
- **Not limited:** worker memory, result size, and the number of concurrent
  requests.
- **Recursion:** Python's recursion limit is left at its default, and each
  LAMBDA call uses several Python stack frames. Recursion more than about 140
  LAMBDA calls deep therefore gets `-32013`: `fact(141)` evaluates, but
  `fact(142)` doesn't.
- **Details:** [`RPC.md`](RPC.md) §5 covers the limits, and §4 covers what
  each error code means.
- **Out of scope:** accounts, persistence, authentication, and deployment.
  The server listens on 127.0.0.1 by default.

## Files

```text
MySolution/
├── __main__.py         command line: python -m MySolution
├── app.py              HTTP transport (Flask): POST /rpc, 404/405/413/415
├── rpc.py              JSON-RPC 2.0: decoding, envelope checks, IDs, notifications, batches
├── errors.py           error codes and RpcError
├── service.py          the four methods: parameter checks and error-code mapping
├── worker.py           worker process: deadline, LAMBDA3 calls, error classification
├── RPC.md              the contract
├── rpc.schema.json     JSON Schema for requests and responses
├── examples/           complete compile responses for RPC.md §7.4 and §7.5
├── tests/              the local test suite
├── TESTING.md          requirement-to-test map, architecture, observed results
└── requirements.txt    pinned dependencies
```
