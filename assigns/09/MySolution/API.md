# LAMBDA-studio Database Service — REST API v1

This is the contract for the in-memory database service in this directory
[CON-1]. The machine-readable form is [`api.schema.json`](api.schema.json) (JSON
Schema, draft 2020-12), with one definition per request and response body
[CON-2].
Where this document and the schema differ, this document wins. The schema
cannot express byte counts, name trimming, uniqueness, or the order of checks.

The service stores LAMBDA-studio programs and test collections for a single
local user. **It never parses, type-checks, interprets, compiles, or runs
LAMBDA source** [DATA-13]. Sources and expected outcomes are opaque data to it. The
studio runs stored cases itself, through the separate LAMBDA3 service from
Assign07.

> **Data lives only in process memory.** Records survive browser reloads and
> new browser sessions while the service process is running. They are lost
> when the process stops or restarts. There is no file, SQLite, browser
> storage, or other persistence. List cursors stop working after a restart
> too [DATA-12].

Requirement IDs in brackets, such as [REV-3], refer to `DESIGN.md` §2.

## Contents

1. [Transport](#1-transport)
2. [Records](#2-records)
3. [Routes](#3-routes)
4. [Validation, uniqueness, and limits](#4-validation-uniqueness-and-limits)
5. [Revisions, ETags, and If-Match](#5-revisions-etags-and-if-match)
6. [Lists, cursors, and snapshots](#6-lists-cursors-and-snapshots)
7. [Atomicity and concurrency](#7-atomicity-and-concurrency)
8. [Errors](#8-errors)
9. [Order of checks](#9-order-of-checks)
10. [Cross-origin access (CORS)](#10-cross-origin-access-cors)
11. [Examples](#11-examples)

## 1. Transport

Base URL with the default startup options: `http://127.0.0.1:8009/api/v1`.
The `v1` path segment is the API version. The health route reports it as
`"version": "1.0"`. An incompatible change would use a new path, `/api/v2`.

**Paths** are matched exactly. A path that is not in the route table (§3),
including one with a trailing slash such as `/api/v1/programs/`, returns
`404 record_not_found` [CON-7]. Route IDs (`{id}`, `{case_id}`) are opaque.
An ID that names no current record returns `404`. IDs are compared exactly
and never parsed.

**Methods.** Each route accepts the methods listed in §3. Every route also
accepts:

- `HEAD` wherever `GET` is accepted. It returns the same status and headers
  as `GET`, with no body.
- `OPTIONS`. It returns `204 No Content` with an `Allow` header, plus CORS
  headers for the studio origin (§10).

Any other method on a known path returns `405 method_not_allowed`, with an
`Allow` header that lists the accepted methods [CON-8].

**Request bodies.** `POST` and `PUT` take a JSON body:

- **Media type:** `Content-Type` must be `application/json`, compared without
  regard to case. Parameters are allowed, but a `charset` parameter must be
  `utf-8`. Anything else, including a missing `Content-Type`, returns
  `415 unsupported_media_type` [CON-5].
- **Size:** the body may be at most **1,048,576 bytes (1 MiB)**. A larger body
  returns `413 payload_too_large` [CON-9]. The limit leaves room for a source
  at its maximum size even with heavy JSON escaping.
- **Encoding:** the body is decoded as strict UTF-8 and parsed as strict JSON
  (RFC 8259). Each of these returns `400 invalid_request` with reason
  `malformed_json` [CON-6]:
  - invalid UTF-8
  - a byte-order mark
  - empty or truncated JSON
  - trailing text after the value
  - the constants `NaN`, `Infinity`, and `-Infinity`
  - an integer too long to convert (more than 4,300 digits)
  - nesting too deep to decode
- **Duplicate members:** a member name repeated within one object returns
  `400` with reason `duplicate_member` and `field: null`, so different JSON
  parsers can never disagree about a body's meaning.
- **Methods without a body:** the service does not read the body of `GET`,
  `HEAD`, `DELETE`, or `OPTIONS` requests. Any such body is ignored.

**Query parameters.** Only the list routes define query parameters (`limit`,
`cursor`). An unknown parameter returns `400` (`unknown_parameter`), and so
does a repeated parameter (`repeated_parameter`), on every route [VAL-7].

**Responses.** Every response with a body is JSON with
`Content-Type: application/json`, encoded as UTF-8 [CON-4]. This includes
errors [CON-12]. A `204` response has no body and no `Content-Type`. Field
order in examples is the order the service produces, but clients must not
depend on it.

**Headers the service sends or reads:**

| Header | Direction | Use |
| --- | --- | --- |
| `Content-Type` | both | `application/json` |
| `ETag` | response | Strong entity tag for a record's revision, such as `"3"` (§5) |
| `If-Match` | request | Required on every update and delete, and on every case mutation (§5) |
| `Location` | response | On `201` program and collection creation: the new record's path |
| `Allow` | response | On `405` and `OPTIONS` responses |
| `Origin`, `Access-Control-*`, `Vary` | both | CORS for the studio page (§10) |

## 2. Records

Every returned record contains all of its fields [DATA-1–3]. Records are
JSON objects. Python objects are never serialized.

### Program

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Opaque ID generated by the service [DATA-4] |
| `name` | string | Trimmed, 1–100 characters, unique among programs |
| `source` | string | LAMBDA source text exactly as saved: 1–65,536 UTF-8 bytes, never trimmed |
| `description` | string | 0–1,000 characters. `""` when not given |
| `created_at` | string | UTC creation time [DATA-5] |
| `updated_at` | string | UTC time of the latest successful update. Equal to `created_at` until then |
| `revision` | integer | 1 when created, plus 1 on every successful update [REV-1] |

### Test collection

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Opaque ID generated by the service |
| `name` | string | Trimmed, 1–100 characters, unique among collections |
| `description` | string | 0–1,000 characters. `""` when not given |
| `created_at` | string | UTC creation time |
| `updated_at` | string | UTC time of the latest successful change, including case changes |
| `revision` | integer | 1 when created, plus 1 on every metadata update and every case mutation |
| `cases` | array of cases | In stored order: insertion order, unchanged by edits. 0–100 cases |

### Test case

A case exists only inside its collection. It has no timestamps or revision of
its own; the collection's revision covers it.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Opaque ID generated by the service, unique within its collection |
| `name` | string | Trimmed, 1–100 characters, unique within its collection |
| `source` | string | The case's own copy of the LAMBDA source, never trimmed |
| `expected` | object | The expected outcome (below) |
| `description` | string | 0–1,000 characters. `""` when not given |

A case holds a **snapshot** of its source. It never refers to a program
record, so updating or deleting a program never changes a test case
[DATA-11].

### Expected outcome

Exactly one of three tagged shapes [VAL-5]:

```json
{ "kind": "value", "value": "720" }
{ "kind": "error", "category": "syntax" }
{ "kind": "error", "category": "type" }
```

- **`value`** is the formatted value that LAMBDA3 returns, for example
  `"720"`, `"true"`, or `"(3, [true])"`. It is a string of 0–8,192 UTF-8
  bytes. It is stored exactly as sent, never trimmed or compared by the
  service.
- **`"syntax"`** means the source should fail LAMBDA3 parsing.
- **`"type"`** means the source should fail LAMBDA3 type checking.

The service only stores the expectation. It does not decide whether it is
correct. How the studio matches outcomes is described in `README.md`.

### IDs and timestamps

- **IDs** are opaque strings generated by the service from 96 random bits.
  The service also checks each new ID against existing records. In this
  version they look like `prg_7hK2mQ9xWv3LpA0s`, `col_…`, and `case_…`, but
  clients must not construct, parse, or rely on that form. Request bodies
  never contain IDs.
- **Timestamps** are UTC in ISO 8601 with millisecond precision and a `Z`
  suffix: `YYYY-MM-DDTHH:MM:SS.sssZ`, for example `2026-11-24T15:00:00.000Z`.
  They come from the server's wall clock and are informational. Ordering
  never depends on them (§6).

## 3. Routes

All paths are relative to the base URL `/api/v1`. Schema names refer to
`api.schema.json#/$defs/…`. "Collection ETag" means the parent collection's
current ETag. Every error response uses `ErrorResponse` (§8).

| Method and path | Request body | `If-Match` | Success | Success body | Success headers |
| --- | --- | --- | --- | --- | --- |
| `GET /health` | — | — | `200` | `Health` | — |
| `POST /programs` | `ProgramInput` | — | `201` | `ProgramResponse` | `ETag`, `Location` |
| `GET /programs?limit=&cursor=` | — | — | `200` | `ProgramPage` | — |
| `GET /programs/{id}` | — | — | `200` | `ProgramResponse` | `ETag` |
| `PUT /programs/{id}` | `ProgramInput` | required | `200` | `ProgramResponse` | `ETag` (new) |
| `DELETE /programs/{id}` | — | required | `204` | none | — |
| `POST /collections` | `CollectionInput` | — | `201` | `CollectionResponse` | `ETag`, `Location` |
| `GET /collections?limit=&cursor=` | — | — | `200` | `CollectionPage` | — |
| `GET /collections/{id}` | — | — | `200` | `CollectionResponse` | `ETag` |
| `PUT /collections/{id}` | `CollectionInput` | required | `200` | `CollectionResponse` | `ETag` (new) |
| `DELETE /collections/{id}` | — | required | `204` | none | — |
| `POST /collections/{id}/cases` | `CaseInput` | collection ETag | `201` | `CollectionResponse` | `ETag` (new) |
| `PUT /collections/{id}/cases/{case_id}` | `CaseInput` | collection ETag | `200` | `CollectionResponse` | `ETag` (new) |
| `DELETE /collections/{id}/cases/{case_id}` | — | collection ETag | `200` | `CollectionResponse` | `ETag` (new) |

**Methods accepted on each path** (the `Allow` header):

| Path | `Allow` |
| --- | --- |
| `/health` | `GET, HEAD, OPTIONS` |
| `/programs`, `/collections` | `GET, HEAD, POST, OPTIONS` |
| `/programs/{id}`, `/collections/{id}` | `GET, HEAD, PUT, DELETE, OPTIONS` |
| `/collections/{id}/cases` | `POST, OPTIONS` |
| `/collections/{id}/cases/{case_id}` | `PUT, DELETE, OPTIONS` |

Cases are read through their collection. There is no `GET` for a single case,
so case creation returns no `Location`.

### What each route does

- **`GET /health`** returns `{"status": "ok", "version": "1.0"}` [CON-3]. It
  does not touch the store.
- **`POST /programs`** creates a program at revision 1. An omitted
  `description` becomes `""`.
- **`GET /programs`** returns one page of full program records (§6).
- **`GET /programs/{id}`** returns the program, with `ETag` set to its
  revision.
- **`PUT /programs/{id}`** **replaces** `name`, `source`, and `description`
  [DATA-6]. An omitted `description` becomes `""`. The revision increases by
  exactly 1, even if the new values equal the old ones, and `updated_at`
  changes.
- **`DELETE /programs/{id}`** removes the program. It does not create a new
  revision. The response has no `ETag`, because no representation remains.
  Test cases are unaffected.
- **`POST /collections`** creates a collection at revision 1 with
  `"cases": []`.
- **`GET /collections`** and **`GET /collections/{id}`** work like the
  program routes. Every collection includes its full ordered `cases`
  [PAGE-6].
- **`PUT /collections/{id}`** replaces `name` and `description` only. The
  cases and their order are untouched [DATA-7]. The revision increases by 1.
- **`DELETE /collections/{id}`** removes the collection and all of its cases
  [DATA-10]. Its case routes then return `404`.
- **`POST /collections/{id}/cases`** appends one case at the end, with a new
  case ID. The collection revision increases by 1. The response is the whole
  updated collection [DATA-8].
- **`PUT /collections/{id}/cases/{case_id}`** replaces the case's `name`,
  `source`, `expected`, and `description`. Its ID and position stay the same,
  and the collection revision increases by 1.
- **`DELETE /collections/{id}/cases/{case_id}`** removes the case. The
  remaining cases keep their order, and the collection revision increases by
  1. The response is `200` with the updated collection and its new `ETag`.

## 4. Validation, uniqueness, and limits

### Request bodies

| Body | Fields it accepts | Server-managed fields (rejected) |
| --- | --- | --- |
| `ProgramInput` | `name` (required), `source` (required), `description` | `id`, `created_at`, `updated_at`, `revision` |
| `CollectionInput` | `name` (required), `description` | `id`, `created_at`, `updated_at`, `revision`, `cases` |
| `CaseInput` | `name` (required), `source` (required), `expected` (required), `description` | `id` |

- **Fields** [VAL-1]:
  - The body must be a JSON object. Otherwise the error is `not_object`, with
    `field: null`.
  - A server-managed field returns `server_managed_field`.
  - Any other unaccepted member returns `unknown_field`.
  - Members are checked in body order, and the first offender is reported.
  - `null` is never accepted in place of a string. It returns `wrong_type`.
- **`name`** [VAL-2]:
  - It must be a string.
  - Leading and trailing whitespace is removed, as Python's `str.strip()`
    defines whitespace.
  - The trimmed name must not be empty (`blank`) and may have at most 100
    characters (`too_long`).
  - The trimmed name is what is stored, returned, and compared.
  - Names are not case-folded or Unicode-normalized. `Factorial` and
    `factorial` are different names.
- **`source`** [VAL-3]:
  - It must be a string of at most 65,536 bytes when encoded as UTF-8
    (`too_large`). This is the default limit of the Assign07 LAMBDA3 service,
    so any stored source can be sent to it.
  - It must contain at least one non-whitespace character (`blank`).
  - It is stored and returned **exactly as sent**. Whitespace is never
    trimmed or altered.
- **`description`** [VAL-4]:
  - It is optional, and an omitted description is `""`.
  - When present it must be a string of at most 1,000 characters
    (`too_long`).
  - It is not trimmed.
- **`expected`** [VAL-5]:
  - It must be an object (`wrong_type`).
  - `expected.kind` must be the string `"value"` or `"error"`
    (`missing`, `wrong_type`, `invalid_value`).
  - Then only the members of that shape are accepted. For example,
    `expected.value` inside an error expectation returns `unknown_field`.
  - For `"value"`: `expected.value` must be a string of at most 8,192 UTF-8
    bytes (`too_large`). It may be empty.
  - For `"error"`: `expected.category` must be `"syntax"` or `"type"`
    (`invalid_value`).
- **Text:** every string must be encodable as UTF-8. JSON escapes for
  unpaired surrogates, such as `"\ud800"`, return `invalid_text`. This is
  checked right after the field's type.

**Order of body checks:**

1. The body is an object.
2. Every member is an accepted field, checked in body order.
3. The fields themselves are checked in the order `name`, `source`,
   `expected`, `description`. Within each field the checks run in the order
   listed above.

Only the first failure is reported, as `400 invalid_request` with `field` and
`reason` (§8). A failed validation changes nothing [REV-5].

Character limits count Unicode code points (Python `len`). Byte limits count
UTF-8 bytes, so `"é"` is 1 character and 2 bytes.

### Uniqueness [DATA-9]

Trimmed names are unique:

- among all programs;
- among all collections;
- among the cases of one collection.

A program, a collection, and cases in different collections may share a name.
Creating or renaming a record to a name already taken in its scope returns
`409 duplicate_name` with `"field": "name"`. Updating a record without
changing its own name is not a conflict. Names are compared after trimming,
exactly, code point by code point.

### Limits [VAL-6]

| Limit | Value | Unit | Exceeding it returns |
| --- | --- | --- | --- |
| HTTP request body | 1,048,576 | bytes | `413 payload_too_large`, `limit` |
| `name` after trimming | 1–100 | characters | `400`, `blank` or `too_long`, `limit` |
| `source` | 1–65,536 | UTF-8 bytes | `400`, `blank` or `too_large`, `limit` |
| `description` | 0–1,000 | characters | `400`, `too_long`, `limit` |
| `expected.value` | 0–8,192 | UTF-8 bytes | `400`, `too_large`, `limit` |
| Programs stored | 500 | records | `409 capacity_limit`, `resource: "programs"` |
| Collections stored | 100 | records | `409 capacity_limit`, `resource: "collections"` |
| Cases per collection | 100 | cases | `409 capacity_limit`, `resource: "cases"` |
| Page size `limit` | 1–100, default 50 | records | `400`, `out_of_range`, `limit: 100` |
| Open list snapshots | 100 | snapshots | `409 capacity_limit`, `resource: "list_snapshots"` (§6) |
| Snapshot idle lifetime | 600 | seconds | Its cursors return `400 unknown_cursor` |

At a boundary, the limit value itself is accepted. For example, a 100-character
name is accepted and a 101-character name is rejected. The 500th program can
be created, and the 501st returns `409`. Deleting a record frees its place.

Worst case, a single program is under 75 KB of JSON and a full collection
under 8 MB. A page of 100 maximal collections could therefore approach
800 MB. That is reachable only by deliberately filling every limit, and
clients can request smaller pages. The studio's records are far smaller.

## 5. Revisions, ETags, and If-Match

- **Revisions** [REV-1]:
  - A new record has revision `1`.
  - Each successful update adds exactly 1. For programs that is `PUT`. For
    collections it is `PUT` and each case `POST`, `PUT`, or `DELETE`.
  - A failed request never changes a revision.
  - A delete checks the revision but does not create a new one.
- **ETag** [REV-2]: a strong entity tag whose value is the revision as a
  quoted decimal number, for example `ETag: "3"`. It is sent:
  - on `GET` of a program or collection;
  - on `201` creation;
  - on every successful `PUT`;
  - on every case mutation, including case deletion. This is the parent
    collection's new ETag.

  It is not sent on `204` deletes, on lists, or on errors. List items carry
  their `revision` field.
- **If-Match** [REV-3] is required on:
  - `PUT` and `DELETE` of a program or collection;
  - every case `POST`, `PUT`, and `DELETE`, where it carries the collection's
    ETag.

  The value must be exactly one strong entity tag in the service's form: a
  quoted positive decimal with no leading zeros and at most 18 digits, such
  as `If-Match: "3"`.
  Spaces around it are ignored. `If-Match` is ignored on `POST /programs` and
  `POST /collections`.

### Precondition outcomes

These checks run in order on an existing route, after the body has been
validated (§9). The first one that applies decides the response.

| Situation | Response |
| --- | --- |
| The record does not exist: the program or collection, or for case routes the collection or the case | `404 record_not_found`, whatever `If-Match` says |
| The record exists and `If-Match` is missing | `428 precondition_required` |
| `If-Match` is malformed: unquoted (`3`), weak (`W/"3"`), a wildcard (`*`), a list (`"3", "4"`), empty, or not a positive decimal | `400 invalid_request`, `field: "If-Match"`, `reason: "malformed_if_match"` |
| `If-Match` names a revision other than the current one | `409 revision_conflict` with `current_revision`. The record is unchanged [REV-4] |
| `If-Match` equals the current ETag | The operation continues: uniqueness, capacity, then the change |

`*` is rejected on purpose. In general HTTP it matches any revision, which
would let a client overwrite a newer version without seeing it.

## 6. Lists, cursors, and snapshots

`GET /programs` and `GET /collections` take two optional query parameters:

| Parameter | Rule |
| --- | --- |
| `limit` [PAGE-1] | Decimal digits only. Must be 1–100; default 50. Anything that is not digits (`-1`, `ten`, `5.0`, empty) returns `invalid_value`. A number outside 1–100 returns `out_of_range`. |
| `cursor` | A `next_cursor` value from an earlier page of the **same** list route. Omit it for the first page. |

Each response is `{"items": [...], "next_cursor": ...}`. `items` holds full
records; collections include their cases [PAGE-6]. `next_cursor` is `null` on
the last page.

- **Order** [PAGE-2]: oldest first, by creation. The store keeps records in
  insertion order, so ties are impossible and the order does not depend on
  clocks. Updates do not move a record.
- **Snapshots** [PAGE-3]: a request **without** a cursor captures, in one
  atomic step, the list of all current records of that kind in order. A
  `HEAD` request does the same, because it is answered like `GET`.
  - If they all fit in one page, the page is returned with
    `next_cursor: null`, and nothing is kept.
  - Otherwise the capture is kept as a snapshot, and the page is returned
    with a cursor to the rest.
  - Every later page in that cursor chain is cut from the **same captured
    list**. Records created after the first page never appear. Records
    updated or deleted later still appear exactly as captured, with their
    old revision and fields.
  - A cursor names a position in one snapshot, so a client may repeat a
    request with the same cursor and get the same page. Each request may use
    a different `limit`.
- **What a snapshot holds:** stored records are immutable values. An update
  creates a new value and leaves the old one untouched. A snapshot is
  therefore a tuple of references to the captured values, not a copy of
  them, and it cannot be changed through the store or by clients. This
  avoids both slicing the live store and looking IDs up again later.
- **Cursor tokens:** a cursor is an opaque string. It contains a random
  128-bit snapshot key that cannot be guessed, plus the page position.
  Clients must not construct or edit cursors.
  - A cursor that is not of the service's form returns `400 invalid_request`
    with reason `malformed_cursor`.
  - A well-formed cursor that names no live snapshot of this list returns
    reason `unknown_cursor`. That covers an expired snapshot, one from a
    previous process, one from the other list route, or a position past the
    end of the snapshot [PAGE-4].
- **Lifetime** [PAGE-5]:
  - A snapshot stays valid while it is in use. It expires **600 seconds
    after the last request that used it**. Each page request using its
    cursor resets that timer.
  - Snapshots are kept only in process memory, so every cursor stops working
    when the service stops.
  - At most **100** snapshots can be open at once. When that many are open
    and a first page needs a new snapshot, the request returns
    `409 capacity_limit` with `"resource": "list_snapshots"`.
  - **A valid snapshot is never evicted early to make room.** Expired
    snapshots are discarded as new snapshots are created.
  - Clients can avoid holding snapshots by using a `limit` large enough for
    one page.
- **Memory cost:** a snapshot costs one reference per captured record: at
  most 500 for programs and 100 for collections. Record values that have
  since been updated or deleted stay in memory until the last snapshot
  referring to them expires. The snapshot cap and the idle lifetime bound how
  long that can last.

## 7. Atomicity and concurrency

The service runs Flask's threaded development server, so requests can run at
the same time. One lock protects the whole store. Each store operation runs
from start to finish while holding it:

1. look up the record;
2. check the precondition;
3. check uniqueness;
4. check capacity;
5. make the change;
6. capture the result.

Parsing and validating the request happen before the lock is taken. Turning
the captured immutable record into JSON happens after it is released.
Therefore [REV-5, REV-6]:

- Callers see either the whole effect of a mutation or none of it. A failure
  at any check leaves the store unchanged.
- Two updates sent concurrently with the same `If-Match` are applied one at a
  time. The first succeeds, and the second sees the new revision and returns
  `409 revision_conflict`.
- A read returns a record as it was between mutations, never half-changed.

List snapshots (§6) have a separate lock of their own. A first page captures
the records under the store lock in one step, then files the snapshot under
the snapshot lock. The two locks are never held together.

The service never makes network calls, so the lock is never held while
waiting on another service.

## 8. Errors

Every error is JSON with `Content-Type: application/json` [CON-12]:

```json
{ "error": { "code": "revision_conflict", "message": "If-Match \"1\" is stale; the program is at revision 2.", "current_revision": 2 } }
```

`code` is stable and machine-readable; clients act on it. `message` is a
human-readable explanation and may change. Error bodies never contain
tracebacks, exception text, file paths, or other internal details [CON-11].

| Status | `code` | When | Extra members |
| --- | --- | --- | --- |
| `400` | `invalid_request` | Malformed JSON, an invalid field, query parameter, or `If-Match` header | `field`, `reason`, sometimes `limit` |
| `404` | `record_not_found` | No such record, or no such route | — |
| `405` | `method_not_allowed` | Known path, unsupported method. The `Allow` header lists the methods. | — |
| `409` | `duplicate_name` | The trimmed name is taken in its scope [CON-10] | `field: "name"` |
| `409` | `revision_conflict` | `If-Match` is stale | `current_revision` |
| `409` | `capacity_limit` | A record, case, or snapshot capacity is full | `resource`, `limit` |
| `413` | `payload_too_large` | Body over 1,048,576 bytes | `limit` |
| `415` | `unsupported_media_type` | `POST` or `PUT` without `Content-Type: application/json` | — |
| `428` | `precondition_required` | An update or delete of an existing record without `If-Match` | — |
| `500` | `internal_error` | An unexpected failure. It is logged on the server, and its details are not returned. | — |

The six codes Assign09 requires are `invalid_request`, `record_not_found`,
`duplicate_name`, `revision_conflict`, `capacity_limit`, and
`internal_error`. This contract adds four, one per remaining status:
`method_not_allowed`, `payload_too_large`, `unsupported_media_type`, and
`precondition_required`.

**`invalid_request` members:**

- `field` is the offending body field as a dotted path (`name`,
  `expected.kind`), the query parameter (`limit`, `cursor`), or the header
  (`If-Match`). It is `null` when the body as a whole is at fault, such as
  malformed JSON or a non-object.
- `reason` is one of:

| `reason` | Meaning |
| --- | --- |
| `malformed_json` | Body is not strict UTF-8 JSON (§1) |
| `duplicate_member` | A member name repeats within one JSON object |
| `not_object` | The request body is not a JSON object; `field` is `null` |
| `unknown_field` | A member the body does not accept |
| `server_managed_field` | A field only the service sets (`id`, timestamps, `revision`, `cases`) |
| `missing` | A required field is absent |
| `wrong_type` | Wrong JSON type, including `null` |
| `invalid_text` | String contains an unpaired surrogate and cannot be UTF-8 |
| `blank` | `name` empty after trimming, or `source` whitespace only |
| `too_long` | Over a character limit; `limit` gives it |
| `too_large` | Over a UTF-8 byte limit; `limit` gives it |
| `invalid_value` | Right type, not an allowed value (`expected.kind`, `expected.category`, non-numeric `limit`) |
| `unknown_parameter` | Query parameter the route does not define |
| `repeated_parameter` | Query parameter given more than once |
| `out_of_range` | `limit` outside 1–100; `limit` member is 100 |
| `malformed_cursor` | `cursor` is not of the service's form |
| `unknown_cursor` | `cursor` names no live snapshot of this list |
| `malformed_if_match` | `If-Match` is not one strong quoted revision |

An `expected` value that is not an object is reported as `wrong_type` with
`field: "expected"`.

## 9. Order of checks

Checks run in this order. The first failure decides the response, and nothing
is changed by a failed request.

1. **Path** is in the route table. Otherwise `404 record_not_found`.
2. **Method** is accepted on that path. Otherwise `405 method_not_allowed`.
   `OPTIONS` is answered here with `204`.
3. **Media type**, for `POST` and `PUT` only. Otherwise
   `415 unsupported_media_type`.
4. **Body size**, for `POST` and `PUT` only. Otherwise
   `413 payload_too_large`.
5. **JSON syntax**: `400`, with reason `malformed_json` or
   `duplicate_member`.
6. **Query parameters, then body fields** (§4, §6): `400 invalid_request`.
   Parameter names are checked first (`unknown_parameter`,
   `repeated_parameter`), then `limit`, then `cursor`.
7. **Record existence**: the program or collection, then the case.
   Otherwise `404 record_not_found`.
8. **`If-Match` present**, on updates and deletes. Otherwise
   `428 precondition_required`.
9. **`If-Match` well formed**. Otherwise `400`, with reason
   `malformed_if_match`.
10. **Revision current**. Otherwise `409 revision_conflict`.
11. **Name unique** in its scope. Otherwise `409 duplicate_name`.
12. **Capacity**: programs, collections, cases, or snapshots. Otherwise
    `409 capacity_limit`.
13. **The change is made**, and the response is captured.

Steps 1–6 inspect only the request. Steps 7–13 run atomically under the store
lock (§7). For a list, the snapshot capacity check comes right after the
capture, under the snapshot lock.

Assign09 requires a missing record to return `404` even when its `If-Match`
is missing or stale. Steps 7–10 ensure this. An invalid request body is
reported before the store is consulted, so an invalid body sent to a missing
record gets `400`.

## 10. Cross-origin access (CORS)

The studio page is served by the studio host (`http://127.0.0.1:8010` by
default), a different origin from this service. Browsers therefore need CORS
headers to let the page read responses and send `If-Match`. The allowed
origins are `http://127.0.0.1:8010` and `http://localhost:8010` by default.
Repeat the startup option `--studio-origin` to replace them.

- **Request from an allowed origin.** When `Origin` exactly equals an allowed
  origin, every response carries these headers, including errors:
  - `Access-Control-Allow-Origin` set to that origin;
  - `Access-Control-Expose-Headers: ETag, Location`, so the page can read
    revisions.
- **Preflight from an allowed origin.** An `OPTIONS` preflight also gets:
  - `Access-Control-Allow-Methods: GET, HEAD, POST, PUT, DELETE`;
  - `Access-Control-Allow-Headers: Content-Type, If-Match`;
  - `Access-Control-Max-Age: 600`.
- **Every response** carries `Vary: Origin`.
- **Any other origin** gets no CORS headers. The request is otherwise
  processed normally. CORS controls what a browser page may read. It is not
  authentication.

## 11. Examples

Sections 11.2–11.5 walk through complete client sequences. The examples in
11.6 and 11.7 stand alone.

- IDs, cursors, and timestamps are illustrative.
- `Date`, `Server`, `Content-Length`, `Vary`, and CORS headers are omitted.
- Status lines use RFC 9110 reason phrases. Werkzeug prints some of them
  differently, for example `413 REQUEST ENTITY TOO LARGE`. Clients act on the
  status code alone.
- Every JSON body below validates against the schema named in §3, which
  `tests/test_schema.py` checks.

### 11.1 Health

```http
GET /api/v1/health HTTP/1.1
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status": "ok", "version": "1.0"}
```

### 11.2 Create, read, update, and delete a program

Create:

```http
POST /api/v1/programs HTTP/1.1
Content-Type: application/json

{"name": "  factorial  ", "source": "let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end"}
```

```http
HTTP/1.1 201 Created
Content-Type: application/json
ETag: "1"
Location: /api/v1/programs/prg_7hK2mQ9xWv3LpA0s

{"program": {"id": "prg_7hK2mQ9xWv3LpA0s", "name": "factorial", "source": "let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end", "description": "", "created_at": "2026-11-24T15:00:00.000Z", "updated_at": "2026-11-24T15:00:00.000Z", "revision": 1}}
```

The name was trimmed. The omitted description became `""`.

Read (for example, after a browser reload):

```http
GET /api/v1/programs/prg_7hK2mQ9xWv3LpA0s HTTP/1.1
```

```http
HTTP/1.1 200 OK
Content-Type: application/json
ETag: "1"

{"program": {"id": "prg_7hK2mQ9xWv3LpA0s", "name": "factorial", "source": "let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end", "description": "", "created_at": "2026-11-24T15:00:00.000Z", "updated_at": "2026-11-24T15:00:00.000Z", "revision": 1}}
```

Update with the current ETag:

```http
PUT /api/v1/programs/prg_7hK2mQ9xWv3LpA0s HTTP/1.1
Content-Type: application/json
If-Match: "1"

{"name": "factorial", "source": "let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(10) end", "description": "Factorial of 10"}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json
ETag: "2"

{"program": {"id": "prg_7hK2mQ9xWv3LpA0s", "name": "factorial", "source": "let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(10) end", "description": "Factorial of 10", "created_at": "2026-11-24T15:00:00.000Z", "updated_at": "2026-11-24T15:05:00.000Z", "revision": 2}}
```

Delete with the current ETag:

```http
DELETE /api/v1/programs/prg_7hK2mQ9xWv3LpA0s HTTP/1.1
If-Match: "2"
```

```http
HTTP/1.1 204 No Content
```

```http
GET /api/v1/programs/prg_7hK2mQ9xWv3LpA0s HTTP/1.1
```

```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{"error": {"code": "record_not_found", "message": "No program has ID 'prg_7hK2mQ9xWv3LpA0s'."}}
```

### 11.3 Stale revision conflict and recovery

A second browser tab still holds revision 1 of a program that is now at
revision 2:

```http
PUT /api/v1/programs/prg_Lw4rT8bN1cYe6ZqU HTTP/1.1
Content-Type: application/json
If-Match: "1"

{"name": "square", "source": "(lam (x: sint) => x * x)(7)"}
```

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{"error": {"code": "revision_conflict", "message": "If-Match \"1\" is stale; the program is at revision 2.", "current_revision": 2}}
```

Nothing changed. The client shows the conflict and keeps its local edits. If
the user chooses to reload, the client fetches the server copy and its new
`ETag`:

```http
GET /api/v1/programs/prg_Lw4rT8bN1cYe6ZqU HTTP/1.1
```

```http
HTTP/1.1 200 OK
Content-Type: application/json
ETag: "2"

{"program": {"id": "prg_Lw4rT8bN1cYe6ZqU", "name": "square", "source": "(lam (x: sint) => x * x)(9)", "description": "", "created_at": "2026-11-24T15:01:00.000Z", "updated_at": "2026-11-24T15:06:00.000Z", "revision": 2}}
```

Without `If-Match`, an update or delete of an existing record is refused:

```http
DELETE /api/v1/programs/prg_Lw4rT8bN1cYe6ZqU HTTP/1.1
```

```http
HTTP/1.1 428 Precondition Required
Content-Type: application/json

{"error": {"code": "precondition_required", "message": "This request requires If-Match with the record's current ETag."}}
```

### 11.4 Listing with a snapshot

There are three programs, A, B, and C, created in that order:

```http
GET /api/v1/programs?limit=2 HTTP/1.1
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"items": [{"id": "prg_7hK2mQ9xWv3LpA0s", "name": "A", "source": "1 + 1", "description": "", "created_at": "2026-11-24T15:00:00.000Z", "updated_at": "2026-11-24T15:00:00.000Z", "revision": 1}, {"id": "prg_Lw4rT8bN1cYe6ZqU", "name": "B", "source": "2 + 2", "description": "", "created_at": "2026-11-24T15:01:00.000Z", "updated_at": "2026-11-24T15:01:00.000Z", "revision": 1}], "next_cursor": "q8ZtN3wXyR5vK1mB7cJd0A.2"}
```

Meanwhile, C is updated to revision 2, A is deleted, and a new program D is
created. The next page still comes from the snapshot. It shows C as
captured, at revision 1, and excludes D:

```http
GET /api/v1/programs?limit=2&cursor=q8ZtN3wXyR5vK1mB7cJd0A.2 HTTP/1.1
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"items": [{"id": "prg_d3FgH5jK7lMn9PqR", "name": "C", "source": "3 + 3", "description": "", "created_at": "2026-11-24T15:02:00.000Z", "updated_at": "2026-11-24T15:02:00.000Z", "revision": 1}], "next_cursor": null}
```

A new first-page request (no cursor) would capture the current state: B, C at
revision 2, and D.

### 11.5 Collections and ordered cases

Create a collection:

```http
POST /api/v1/collections HTTP/1.1
Content-Type: application/json

{"name": "smoke tests", "description": "Quick checks after a compiler change"}
```

```http
HTTP/1.1 201 Created
Content-Type: application/json
ETag: "1"
Location: /api/v1/collections/col_Xc8vB2nM4aS6dF0g

{"collection": {"id": "col_Xc8vB2nM4aS6dF0g", "name": "smoke tests", "description": "Quick checks after a compiler change", "created_at": "2026-11-24T15:10:00.000Z", "updated_at": "2026-11-24T15:10:00.000Z", "revision": 1, "cases": []}}
```

Add a case that expects a value, using the collection ETag:

```http
POST /api/v1/collections/col_Xc8vB2nM4aS6dF0g/cases HTTP/1.1
Content-Type: application/json
If-Match: "1"

{"name": "factorial 6", "source": "let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end", "expected": {"kind": "value", "value": "720"}}
```

```http
HTTP/1.1 201 Created
Content-Type: application/json
ETag: "2"

{"collection": {"id": "col_Xc8vB2nM4aS6dF0g", "name": "smoke tests", "description": "Quick checks after a compiler change", "created_at": "2026-11-24T15:10:00.000Z", "updated_at": "2026-11-24T15:11:00.000Z", "revision": 2, "cases": [{"id": "case_q1W2e3R4t5Y6u7I8", "name": "factorial 6", "source": "let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end", "expected": {"kind": "value", "value": "720"}, "description": ""}]}}
```

Two more cases are appended the same way, with `If-Match: "2"` and then
`"3"`: `"bad syntax"` (source `if then`, expected
`{"kind": "error", "category": "syntax"}`) and `"bad argument"` (source
`(lam (x: sint) => x)(true)`, expected `{"kind": "error", "category": "type"}`).
The collection is now at revision 4 with cases in the order factorial 6, bad
syntax, bad argument.

Update the middle case in place. Its ID and position stay the same:

```http
PUT /api/v1/collections/col_Xc8vB2nM4aS6dF0g/cases/case_o9P0a1S2d3F4g5H6 HTTP/1.1
Content-Type: application/json
If-Match: "4"

{"name": "bad syntax", "source": "let x = in x end", "expected": {"kind": "error", "category": "syntax"}, "description": "missing expression"}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json
ETag: "5"

{"collection": {"id": "col_Xc8vB2nM4aS6dF0g", "name": "smoke tests", "description": "Quick checks after a compiler change", "created_at": "2026-11-24T15:10:00.000Z", "updated_at": "2026-11-24T15:14:00.000Z", "revision": 5, "cases": [{"id": "case_q1W2e3R4t5Y6u7I8", "name": "factorial 6", "source": "let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end", "expected": {"kind": "value", "value": "720"}, "description": ""}, {"id": "case_o9P0a1S2d3F4g5H6", "name": "bad syntax", "source": "let x = in x end", "expected": {"kind": "error", "category": "syntax"}, "description": "missing expression"}, {"id": "case_j7K8l9Z0x1C2v3B4", "name": "bad argument", "source": "(lam (x: sint) => x)(true)", "expected": {"kind": "error", "category": "type"}, "description": ""}]}}
```

Delete the first case. The remaining cases keep their order:

```http
DELETE /api/v1/collections/col_Xc8vB2nM4aS6dF0g/cases/case_q1W2e3R4t5Y6u7I8 HTTP/1.1
If-Match: "5"
```

```http
HTTP/1.1 200 OK
Content-Type: application/json
ETag: "6"

{"collection": {"id": "col_Xc8vB2nM4aS6dF0g", "name": "smoke tests", "description": "Quick checks after a compiler change", "created_at": "2026-11-24T15:10:00.000Z", "updated_at": "2026-11-24T15:15:00.000Z", "revision": 6, "cases": [{"id": "case_o9P0a1S2d3F4g5H6", "name": "bad syntax", "source": "let x = in x end", "expected": {"kind": "error", "category": "syntax"}, "description": "missing expression"}, {"id": "case_j7K8l9Z0x1C2v3B4", "name": "bad argument", "source": "(lam (x: sint) => x)(true)", "expected": {"kind": "error", "category": "type"}, "description": ""}]}}
```

Rename the collection. This is a metadata update, and the cases and their
order are unchanged:

```http
PUT /api/v1/collections/col_Xc8vB2nM4aS6dF0g HTTP/1.1
Content-Type: application/json
If-Match: "6"

{"name": "error cases"}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json
ETag: "7"

{"collection": {"id": "col_Xc8vB2nM4aS6dF0g", "name": "error cases", "description": "", "created_at": "2026-11-24T15:10:00.000Z", "updated_at": "2026-11-24T15:16:00.000Z", "revision": 7, "cases": [{"id": "case_o9P0a1S2d3F4g5H6", "name": "bad syntax", "source": "let x = in x end", "expected": {"kind": "error", "category": "syntax"}, "description": "missing expression"}, {"id": "case_j7K8l9Z0x1C2v3B4", "name": "bad argument", "source": "(lam (x: sint) => x)(true)", "expected": {"kind": "error", "category": "type"}, "description": ""}]}}
```

The omitted description became `""`, because `PUT` replaces the metadata.

List collections. Each item includes its cases:

```http
GET /api/v1/collections?limit=50 HTTP/1.1
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"items": [{"id": "col_Xc8vB2nM4aS6dF0g", "name": "error cases", "description": "", "created_at": "2026-11-24T15:10:00.000Z", "updated_at": "2026-11-24T15:16:00.000Z", "revision": 7, "cases": [{"id": "case_o9P0a1S2d3F4g5H6", "name": "bad syntax", "source": "let x = in x end", "expected": {"kind": "error", "category": "syntax"}, "description": "missing expression"}, {"id": "case_j7K8l9Z0x1C2v3B4", "name": "bad argument", "source": "(lam (x: sint) => x)(true)", "expected": {"kind": "error", "category": "type"}, "description": ""}]}], "next_cursor": null}
```

Delete the collection. Its cases go with it:

```http
DELETE /api/v1/collections/col_Xc8vB2nM4aS6dF0g HTTP/1.1
If-Match: "7"
```

```http
HTTP/1.1 204 No Content
```

```http
PUT /api/v1/collections/col_Xc8vB2nM4aS6dF0g/cases/case_j7K8l9Z0x1C2v3B4 HTTP/1.1
Content-Type: application/json
If-Match: "7"

{"name": "bad argument", "source": "(lam (x: sint) => x)(true)", "expected": {"kind": "error", "category": "type"}}
```

```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{"error": {"code": "record_not_found", "message": "No collection has ID 'col_Xc8vB2nM4aS6dF0g'."}}
```

### 11.6 Invalid input

An invalid query parameter:

```http
GET /api/v1/programs?limit=0 HTTP/1.1
```

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error": {"code": "invalid_request", "message": "limit must be a whole number from 1 to 100.", "field": "limit", "reason": "out_of_range", "limit": 100}}
```

A server-managed field in a body:

```http
POST /api/v1/programs HTTP/1.1
Content-Type: application/json

{"name": "answer", "source": "42", "revision": 7}
```

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error": {"code": "invalid_request", "message": "Field 'revision' is set by the service and cannot be sent.", "field": "revision", "reason": "server_managed_field"}}
```

An expected outcome that mixes two shapes:

```http
POST /api/v1/collections/col_Xc8vB2nM4aS6dF0g/cases HTTP/1.1
Content-Type: application/json
If-Match: "1"

{"name": "mixed", "source": "1", "expected": {"kind": "error", "category": "type", "value": "1"}}
```

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error": {"code": "invalid_request", "message": "Field 'expected.value' is not accepted for an expected error.", "field": "expected.value", "reason": "unknown_field"}}
```

A blank name:

```http
POST /api/v1/collections HTTP/1.1
Content-Type: application/json

{"name": "   "}
```

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error": {"code": "invalid_request", "message": "name must contain a non-whitespace character.", "field": "name", "reason": "blank"}}
```

An oversized source:

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error": {"code": "invalid_request", "message": "source is 65537 UTF-8 bytes; the limit is 65536.", "field": "source", "reason": "too_large", "limit": 65536}}
```

Malformed JSON:

```http
POST /api/v1/programs HTTP/1.1
Content-Type: application/json

{"name": "broken",
```

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error": {"code": "invalid_request", "message": "The request body is not valid JSON.", "field": null, "reason": "malformed_json"}}
```

### 11.7 Other errors

A duplicate name (names are compared after trimming):

```http
POST /api/v1/programs HTTP/1.1
Content-Type: application/json

{"name": "square ", "source": "(lam (x: sint) => x * x)(3)"}
```

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{"error": {"code": "duplicate_name", "message": "Another program is already named 'square'.", "field": "name"}}
```

A full collection:

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{"error": {"code": "capacity_limit", "message": "A collection holds at most 100 cases.", "resource": "cases", "limit": 100}}
```

An unknown route, and a method that a known route does not accept:

```http
GET /api/v1/tests HTTP/1.1
```

```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{"error": {"code": "record_not_found", "message": "No API route matches this path."}}
```

```http
PATCH /api/v1/programs/prg_Lw4rT8bN1cYe6ZqU HTTP/1.1
```

```http
HTTP/1.1 405 Method Not Allowed
Content-Type: application/json
Allow: GET, HEAD, PUT, DELETE, OPTIONS

{"error": {"code": "method_not_allowed", "message": "PATCH is not allowed on this route."}}
```

A body that is not JSON, and a body that is too large:

```http
POST /api/v1/programs HTTP/1.1
Content-Type: text/plain

name=answer
```

```http
HTTP/1.1 415 Unsupported Media Type
Content-Type: application/json

{"error": {"code": "unsupported_media_type", "message": "Request bodies must be sent with Content-Type: application/json."}}
```

```http
HTTP/1.1 413 Content Too Large
Content-Type: application/json

{"error": {"code": "payload_too_large", "message": "Request bodies are limited to 1048576 bytes.", "limit": 1048576}}
```

An unexpected failure:

```http
HTTP/1.1 500 Internal Server Error
Content-Type: application/json

{"error": {"code": "internal_error", "message": "The service failed unexpectedly. The failure was logged."}}
```
