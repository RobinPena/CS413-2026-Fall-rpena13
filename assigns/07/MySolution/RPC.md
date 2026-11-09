# LAMBDA3 JSON-RPC Service — Contract

API version **1.0**. This document is the contract for the service in this
directory. The machine-readable form is [`rpc.schema.json`](rpc.schema.json)
(JSON Schema, draft 2020-12). Where the prose and the schema differ, the prose
wins. The schema cannot express byte counts or which check runs first.

The service makes the supplied LAMBDA3 implementation (`../LAMBDA3/lambda3.py`)
available to local clients over JSON-RPC 2.0. It is for local development and
automated tests only. There are no accounts and no storage, and it is not
meant for public deployment. Generated programs are returned as text and are
never run by the service.

## 1. Transport

There is exactly one endpoint:

```text
POST http://127.0.0.1:8000/rpc
Content-Type: application/json
```

The host and port are the defaults of the startup command (see `README.md`).
Every operation is a JSON-RPC method sent to this endpoint. Operations are not
separate URLs.

**Request requirements**

- The HTTP method must be `POST`.
- The `Content-Type` media type must be `application/json`, compared without
  regard to case. Parameters are allowed, but a `charset` parameter must be
  `utf-8`.
- The body must be at most **1,048,576 bytes (1 MiB)**.
- The body is decoded as strict UTF-8 and parsed as strict JSON (RFC 8259):
  - A byte-order mark is rejected.
  - Invalid UTF-8 is rejected.
  - The non-standard constants `NaN`, `Infinity` and `-Infinity` are rejected.
  - Numbers that cannot be represented and echoed back are rejected. That
    means a number too large for a 64-bit float (such as `1e400`), or an
    integer with more than 4,300 digits (Python's default conversion limit).
  - Arrays and objects nested too deeply for the decoder are rejected. The
    limit depends on the decoder's stack, not on a fixed number.
  - If a member name repeats in one object, the last occurrence wins.

### HTTP status versus RPC outcome

HTTP status describes the **transport**: whether the service accepted the HTTP
request as a JSON-RPC exchange. The **RPC outcome** (success or a JSON-RPC
error) is always in the body. A JSON-RPC error is a successful HTTP exchange.
That includes a parse error, an invalid request, a LAMBDA syntax error and a
timeout, so all of them come back with HTTP 200.

| Situation | HTTP status | Body |
| --- | --- | --- |
| A JSON-RPC response object or array is returned, whatever the RPC outcome | `200 OK` | `application/json` |
| A single valid notification, or a batch that produces no responses | `204 No Content` | empty (zero bytes) |
| Path other than `/rpc` | `404 Not Found` | short `text/plain` explanation |
| HTTP method other than `POST` on `/rpc` | `405 Method Not Allowed`, with `Allow: POST` | short `text/plain` explanation |
| `Content-Type` missing, not `application/json`, or with a non-UTF-8 charset | `415 Unsupported Media Type` | short `text/plain` explanation |
| Body larger than 1 MiB | `413 Content Too Large` | short `text/plain` explanation |

Transport checks run in the order of the table: path, then method, then media
type, then size. A transport error body is **not** a JSON-RPC response.
Clients should act on the status code alone. Framework-generated error pages
(such as HTML 400 pages) are never returned for `/rpc`. Anything the
transport accepts gets a JSON-RPC answer.

## 2. The JSON-RPC 2.0 envelope

### Request object

```json
{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "1 + 2"}, "id": 1}
```

| Member | Rule |
| --- | --- |
| `jsonrpc` | Required. Exactly the string `"2.0"`. |
| `method` | Required. A string. Method names are case-sensitive. |
| `params` | Optional in the envelope, but must be an object or an array if present. **Every method of this service requires an object** (see §3). |
| `id` | Optional. If present: a string, a number, or `null`. Booleans, objects and arrays are not valid IDs. |

No other members are allowed.

### IDs

- A response to a call carries the call's `id`, **unchanged** as a JSON value.
  - The empty string `""` and the number `0` are valid IDs and are never
    replaced.
  - An integer of any size comes back exactly as sent.
  - A fractional number comes back with the same value, though its text may
    be normalized (`1.50` comes back as `1.5`).
  - IDs are never turned into strings.
- **Parse Error (`-32700`) and Invalid Request (`-32600`) responses always have
  `"id": null`.** This holds even when the request contained a usable ID, as
  in `{"jsonrpc": "1.0", "method": "service.health", "id": 1}`. Once the
  envelope is invalid, the service does not trust any of its members.
- An explicit `"id": null` makes a **call**, not a notification, and gets a
  response with `"id": null`. JSON-RPC discourages it, because the client
  cannot tell that response apart from an invalid-request response.
- Repeated IDs are not rejected or merged. Each call is processed and answered
  separately.

### Notifications

A **notification** is a request that passes every envelope check and has **no
`id` member**. Leaving `id` out is the only way to make one.

- A notification is processed like a call. For example, a `lambda.interpret`
  notification really runs the interpreter under the same deadline.
- **No response is ever produced for a valid notification.** This includes an
  unknown method, invalid params, a LAMBDA error, a timeout or an internal
  error.
- A request that fails the envelope checks is not a notification, even without
  an `id`. It always gets an Invalid Request response with `"id": null`.

### Response object

Every response has `"jsonrpc": "2.0"` and an `id`, and **exactly one** of
`result` or `error`:

```json
{"jsonrpc": "2.0", "result": {"type": "sint"}, "id": 1}
{"jsonrpc": "2.0", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"diagnostic": "unbound variable 'x'"}}, "id": 1}
```

An `error` object has an integer `code`, a string `message`, and the optional
structured `data` described in §4.

### Validation order

Each request object (a single request or one batch member) goes through these
steps. The first failing step decides the response.

1. **Envelope** (the structural checks above). Failure gives `-32600` Invalid
   Request with `id: null`.
   - The value must be a JSON object.
   - It may contain only the four members above.
   - `jsonrpc` must be `"2.0"`, `method` a string, `params` an object or array
     if present, and `id` a valid ID if present.
2. **Notification or call** is decided: no `id` member means a notification.
3. **Method lookup**, case-sensitive. An unknown name gives `-32601` Method not
   found.
4. **Method parameters** (§3). Failure gives `-32602` Invalid params.
5. **Execution**. The result is either `result` or one of `-32010`, `-32011`,
   `-32012`, `-32013` or `-32603`.

The envelope check (step 1) only asks whether the request is a well-formed
JSON-RPC 2.0 request. The method checks (steps 3–4) ask what this service
accepts. For example, `"params": "x"` is malformed in any JSON-RPC 2.0
service, so it gets `-32600`. `"params": ["1 + 2"]` is a well-formed
positional request that these methods do not accept, so it gets `-32602`.

## 3. Methods

| Method | `params` (object, required) | `result` |
| --- | --- | --- |
| `service.health` | `{}` | `{"status": "ok", "version": "1.0"}` |
| `lambda.typecheck` | `{"source": string}` | `{"type": string}` |
| `lambda.interpret` | `{"source": string}` | `{"type": string, "value": string}` |
| `lambda.compile` | `{"source": string, "target": "python" \| "javascript"}` | `{"target": string, "code": string}` |

### Parameter rules (`-32602` Invalid params)

The checks run in this order. The first failure is reported, and the reason
codes are listed in §4.

1. **`params` must be present and must be an object.**
   - A missing `params` gives `params_required`.
   - Positional (array) `params` gives `params_not_object`.
   - Nothing falls back to a default.
2. **No members other than the ones listed for the method** (`unexpected_param`).
   - `service.health` takes exactly `{}`.
   - `lambda.typecheck` and `lambda.interpret` take only `source`.
   - `lambda.compile` takes `source` and `target`.
3. **`source`** (all three `lambda.*` methods), in order:
   1. It must be present (`missing`).
   2. It must be a string (`wrong_type`).
   3. It must be valid Unicode text that can be encoded as UTF-8; JSON escapes
      for unpaired surrogates such as `"\ud800"` are rejected (`invalid_text`).
   4. It must be at most **65,536 bytes** when encoded as UTF-8
      (`too_large`). Bytes are counted, not characters, so `"é"` counts as 2.
   5. It must not be empty or whitespace only (`blank`).

   A source that passes is given to LAMBDA3 exactly as received, with no
   trimming or rewriting.
4. **`target`** (`lambda.compile` only), in order:
   1. It must be present (`missing`).
   2. It must be a string (`wrong_type`).
   3. It must be exactly `"python"` or `"javascript"`. Names are case-sensitive
      (`unsupported_target`).

### What the source methods do

All three `lambda.*` methods first call
`d0exp_parse_and_typecheck(source)`. If parsing or type checking fails, the
method stops there, and nothing is evaluated or compiled.

| Method | After a successful parse and type check |
| --- | --- |
| `lambda.typecheck` | Returns `format_type(type)`. |
| `lambda.interpret` | Calls `d0exp_evaluate(expression)` and returns `format_type(type)` and `d0val_format(value)`. Function values appear as `d0val_format` prints them (`<lam>`, `<fix>`), and closures and environments are never serialized. Output from LAMBDA `print` is discarded. Only the final value is returned. |
| `lambda.compile` | Calls `d0exp_compile(expression)` for `python` or `d0exp_compile_js(expression)` for `javascript` and returns that string **unchanged**. The program is not evaluated, and the generated code is never run (no `exec`, `eval` or JavaScript runtime). |

All three methods run inside a separate worker process under the deadline in
§5. Type checking needs the deadline too: unannotated lambdas can make type
inference grow exponentially. A 379-byte source took more than 8 seconds to
type-check when LAMBDA3 was called directly.

`service.health` does not touch LAMBDA3 or the worker. Its `version` is the
API version of this contract.

## 4. Errors

| Code | `message` | When | `data` |
| --- | --- | --- | --- |
| `-32700` | `Parse error` | The body is not valid UTF-8 JSON text, or it holds a value the service cannot represent (§1). | `{"reason": "invalid_utf8"}`, `{"reason": "invalid_json", "line": L, "column": C}`, `{"reason": "unsupported_number"}`, or `{"reason": "nesting_too_deep"}` |
| `-32600` | `Invalid Request` | Envelope check failed, empty batch, or batch too large. | `{"reason": R}`, plus `"limit"` for `batch_too_large` |
| `-32601` | `Method not found` | Unknown method name. | none |
| `-32602` | `Invalid params` | A parameter rule in §3 failed. | `{"param": P, "reason": R, ...}` (see below) |
| `-32603` | `Internal error` | An unexpected failure: a bug, a worker crash, or an exception that LAMBDA3 errors don't explain. | `{"incident": "<12 hex digits>"}` |
| `-32010` | `LAMBDA syntax error` | Parsing failed (`LambdaSyntaxError`), or the source is nested too deeply to parse. | `{"diagnostic": D, "line": L, "column": C}`; `line` and `column` are left out when unknown |
| `-32011` | `LAMBDA type error` | Type checking failed (`TypeCheckError`), including an **unbound variable**, or the source is nested too deeply to type-check. | `{"diagnostic": D}` |
| `-32012` | `Execution timed out` | The deadline expired before the worker returned a result. | `{"limit_seconds": 2.0}` |
| `-32013` | `LAMBDA runtime error` | Evaluation of a well-typed program failed. | `{"diagnostic": D}` |

**`-32600` reasons:**
- `not_an_object`
- `bad_jsonrpc`
- `bad_method`
- `bad_params`
- `bad_id`
- `unexpected_member`
- `empty_batch`
- `batch_too_large`

**`-32602` data:**
- `param` is `"source"`, `"target"`, or `null` when the whole `params` value
  is at fault.
- `reason` is one of:
  - `params_required`
  - `params_not_object`
  - `unexpected_param`
  - `missing`
  - `wrong_type`
  - `invalid_text`
  - `too_large`
  - `blank`
  - `unsupported_target`
- Extra members for some reasons:
  - `too_large` adds `limit_bytes` and `size_bytes`.
  - `unexpected_param` and `unsupported_target` add `allowed` (the accepted
    names or values).

**Runtime errors (`-32013`).** These are failures the type checker cannot
rule out:
- division by zero (`1 / 0`)
- the head or tail of an empty list
- getting the value out of an empty option
- an array index out of range
- a negative array size
- recursion deeper than Python's default recursion limit, which is
  unchanged. LAMBDA3 reaches it after roughly 140 nested LAMBDA calls.

These are mistakes in the client's program, not server faults, so they get a
LAMBDA error code instead of `-32603`.

**Information handling.**
- A `diagnostic` is LAMBDA3's own message for syntax and type errors, or the
  evaluator's message for runtime errors.
  - A diagnostic longer than 1,000 characters is cut to 1,000 characters,
    ending in `...`.
  - Recursion-limit failures use a fixed sentence instead of Python's message.
- Responses never contain tracebacks, Python exception class names,
  filesystem paths or internal object representations.
- For `-32603`, the server logs the full details together with the `incident`
  value. The client receives only that value, so a report can be matched to
  the log.

## 5. Limits

| Limit | Value | Applies to | When exceeded | Configuration |
| --- | --- | --- | --- | --- |
| Source size | 65,536 bytes of UTF-8 | each `source` parameter, measured before LAMBDA3 sees it | `-32602`, reason `too_large` | `--max-source-bytes` |
| Deadline | 2.0 seconds of wall-clock time | each `lambda.*` call | `-32012` | `--deadline` |
| Request body | 1,048,576 bytes | the whole HTTP body | HTTP `413` | fixed |
| Batch size | 20 members | one batch | one `-32600` object, reason `batch_too_large` | fixed |

The source limit and the body limit are separate. A single request may carry a
source of up to 65,536 bytes, and a batch may carry several, as long as the
whole body stays within 1 MiB. The source limit leaves plenty of room for the
standard libraries in `../LAMBDA3/mylib/`. All four together take 14,164 bytes
when wrapped in `let … in … end`.

**The deadline** is measured on a monotonic clock:
- It starts when the worker process is started and ends when the parent
  receives the worker's result. Process startup, parsing, type checking,
  evaluation or compilation, and formatting all count against it.
- When it expires, the parent terminates the worker, kills it if it is still
  alive after a short grace period, and waits for it to exit. Then it returns
  `-32012`.
- The computation does not continue in the background.
- **A timeout does not prove nontermination.** For example, the doubly
  recursive Fibonacci program in §7.10 does terminate. It just needs far
  longer than 2 seconds.

**Not limited:**
- the memory a worker uses
- the size of a successful result
- the number of concurrent requests (each `lambda.*` call gets its own
  worker process)

Batch members run one at a time, so a batch can take up to 20 × the deadline.

## 6. Batches

A **batch** is a JSON array of request objects.

- Each member is checked and processed **independently**, in array order. One
  member's failure does not affect the others.
- The response array holds one response for every call and every invalid
  member (Invalid Request with `id: null`). **Valid notifications get no
  entry.**
- Clients must **match responses by `id`, not by position**. This service
  happens to answer in member order, but JSON-RPC does not guarantee it.
- If the batch produces no responses (all of its members are valid
  notifications), the reply is HTTP **204** with an empty body.
- An **empty batch** `[]` is itself an invalid request. It gets **one**
  Invalid Request object with `"id": null`, not an array.
- A batch with more than 20 members gets **one** Invalid Request object
  (`batch_too_large`), and none of its members are executed.
- A JSON value that is neither an object nor an array (`1`, `"x"`, `null`)
  gets one Invalid Request object with `"id": null`.

## 7. Examples

Each example shows the HTTP request body, then the HTTP status and response
body. Every request is `POST /rpc` with `Content-Type: application/json`.
LAMBDA types, values and diagnostics are the strings LAMBDA3 returns for these
sources.

### 7.1 Health

```json
{"jsonrpc": "2.0", "method": "service.health", "params": {}, "id": "health-1"}
```

`200 OK`

```json
{"jsonrpc": "2.0", "result": {"status": "ok", "version": "1.0"}, "id": "health-1"}
```

### 7.2 Successful type check

```json
{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "lam (x: sint) => x * 2"}, "id": 2}
```

`200 OK`

```json
{"jsonrpc": "2.0", "result": {"type": "sint -> sint"}, "id": 2}
```

### 7.3 Successful interpretation (factorial)

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n    if n <= 1 then 1 else n * fact(n - 1)\nin fact(6) end"}, "id": 3}
```

`200 OK`

```json
{"jsonrpc": "2.0", "result": {"type": "sint", "value": "720"}, "id": 3}
```

### 7.4 Compilation to Python

```json
{"jsonrpc": "2.0", "method": "lambda.compile", "params": {"source": "1 + 2", "target": "python"}, "id": "compile-py"}
```

`200 OK`. The complete response, with the full 4,872-character string that
`d0exp_compile` returns, is in
[`examples/compile-python-response.json`](examples/compile-python-response.json).
Its shape is below; **the `code` value is abbreviated here and is not the real
output**:

```text
{"jsonrpc": "2.0", "result": {"target": "python", "code": "<4,872 characters: runtime helpers, then def _lambda_main(): ...>"}, "id": "compile-py"}
```

### 7.5 Compilation to JavaScript

```json
{"jsonrpc": "2.0", "method": "lambda.compile", "params": {"source": "1 + 2", "target": "javascript"}, "id": "compile-js"}
```

`200 OK`. The complete response, with the full 4,996-character string that
`d0exp_compile_js` returns, is in
[`examples/compile-javascript-response.json`](examples/compile-javascript-response.json).
**The `code` value is abbreviated here and is not the real output**:

```text
{"jsonrpc": "2.0", "result": {"target": "javascript", "code": "<4,996 characters: runtime helpers, then function _lambda_main() { ... }>"}, "id": "compile-js"}
```

### 7.6 LAMBDA syntax error

```json
{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "if then"}, "id": "syntax"}
```

`200 OK`

```json
{"jsonrpc": "2.0", "error": {"code": -32010, "message": "LAMBDA syntax error", "data": {"diagnostic": "Expected an expression", "line": 1, "column": 4}}, "id": "syntax"}
```

### 7.7 LAMBDA type error

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "(lam (x: sint) => x)(true)"}, "id": "type"}
```

`200 OK`. The program was rejected before evaluation.

```json
{"jsonrpc": "2.0", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"diagnostic": "function application: expected sint, got bool"}}, "id": "type"}
```

### 7.8 Unbound variable (a type error in LAMBDA3)

```json
{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "missing_name + 1"}, "id": "unbound"}
```

`200 OK`

```json
{"jsonrpc": "2.0", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"diagnostic": "unbound variable 'missing_name'"}}, "id": "unbound"}
```

### 7.9 LAMBDA runtime error

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "1 / 0"}, "id": "runtime"}
```

`200 OK`

```json
{"jsonrpc": "2.0", "error": {"code": -32013, "message": "LAMBDA runtime error", "data": {"diagnostic": "division by zero"}}, "id": "runtime"}
```

### 7.10 Execution timeout

This doubly recursive Fibonacci program terminates, but evaluating `fib(26)`
took about 11 seconds when LAMBDA3 was called directly. That is well past the
2-second deadline.

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let fib : sint -> sint = fix fib(n: sint): sint => if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(26) end"}, "id": "slow"}
```

`200 OK`, about 2 seconds after the request:

```json
{"jsonrpc": "2.0", "error": {"code": -32012, "message": "Execution timed out", "data": {"limit_seconds": 2.0}}, "id": "slow"}
```

### 7.11 Invalid params (blank source)

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "   "}, "id": "blank"}
```

`200 OK`

```json
{"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params", "data": {"param": "source", "reason": "blank"}}, "id": "blank"}
```

### 7.12 Unknown method

```json
{"jsonrpc": "2.0", "method": "Lambda.Typecheck", "params": {"source": "1"}, "id": 12}
```

`200 OK`. Method names are case-sensitive.

```json
{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": 12}
```

### 7.13 Malformed JSON

Request body (truncated JSON text): `{"jsonrpc":`

`200 OK`

```json
{"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error", "data": {"reason": "invalid_json", "line": 1, "column": 12}}, "id": null}
```

### 7.14 Invalid request (the usable `id` is not echoed)

```json
{"jsonrpc": "1.0", "method": "service.health", "id": 1}
```

`200 OK`

```json
{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "bad_jsonrpc"}}, "id": null}
```

### 7.15 Batch with calls, a notification and an invalid member

```json
[
  {"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "6 * 7"}, "id": "answer"},
  {"jsonrpc": "2.0", "method": "service.health", "params": {}},
  {"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "x + 1"}, "id": 7},
  "not-a-request"
]
```

`200 OK`. There is no entry for the notification (second member). Match the
entries by `id`:

```json
[
  {"jsonrpc": "2.0", "result": {"type": "sint", "value": "42"}, "id": "answer"},
  {"jsonrpc": "2.0", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"diagnostic": "unbound variable 'x'"}}, "id": 7},
  {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "not_an_object"}}, "id": null}
]
```

### 7.16 Notification-only batch

```json
[
  {"jsonrpc": "2.0", "method": "service.health", "params": {}},
  {"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "1 + 2"}}
]
```

`204 No Content`. The response body is empty (zero bytes).

### 7.17 Single notification

```json
{"jsonrpc": "2.0", "method": "service.health", "params": {}}
```

`204 No Content`. The response body is empty (zero bytes).

### 7.18 Empty batch

```json
[]
```

`200 OK`. A single object, not an array:

```json
{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "empty_batch"}}, "id": null}
```

### 7.19 Transport error (wrong media type)

`POST /rpc` with `Content-Type: text/plain` and any body gets
`415 Unsupported Media Type` with a short plain-text explanation and no
JSON-RPC body.

## 8. JSON Schema

[`rpc.schema.json`](rpc.schema.json) defines these entry points under `$defs`:

| Definition | Describes |
| --- | --- |
| `RequestBody` | A valid HTTP request body: one `MethodRequest`, or a batch of 1–20 of them. |
| `EnvelopeRequest` | The structural JSON-RPC 2.0 request (validation step 1). Failing it gives `-32600`. |
| `MethodRequest` | `EnvelopeRequest` plus this service's method names and `params` shapes (steps 3–4). |
| `Call`, `Notification` | `EnvelopeRequest` with `id` required, or with `id` forbidden. |
| `ResponseBody` | An HTTP 200 body: one `Response`, or an array of 1–20 of them. |
| `Response` | Exactly one of `SuccessResponse` and `ErrorResponse`. Neither allows extra members, so no response can contain both `result` and `error`. |
| `ErrorObject` | The error codes, their messages and their `data` shapes from §4. `-32700` and `-32600` responses must have `"id": null`. |

Three rules are approximations in the schema:
- The source limit is in UTF-8 bytes. JSON Schema can only count characters,
  so the schema's `maxLength` is an upper bound, not the real check.
- Whitespace-only sources are excluded with a pattern.
- The order in which validation steps run is defined only in §2 and §3.

## 9. Processing pipeline

```text
HTTP client
   │  POST /rpc (application/json)
   ▼
Transport (Flask)         404 / 405 / 415 / 413 checks; strict UTF-8 JSON decode
   │  decoded JSON value, or a parse error
   ▼
JSON-RPC dispatcher       envelope, IDs, notifications, batches, method table,
   │                      response objects; HTTP 200 / 204
   │  method name + params
   ▼
Service adapter           params rules and source limit; maps outcomes to error codes
   │  (operation, source, target): plain strings only
   ═══════════ process boundary: spawned worker, deadline, terminate → kill → join ═══════════
   ▼
Worker process            d0exp_parse_and_typecheck → format_type
                          + d0exp_evaluate → d0val_format  |  d0exp_compile / d0exp_compile_js
   │  small payload of strings, or an error category and diagnostic
   ▼
LAMBDA3 (../LAMBDA3/lambda3.py, basics0.py), loaded by absolute path
```

`service.health` is answered by the service adapter and never crosses the
process boundary.
