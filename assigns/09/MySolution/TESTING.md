# Testing

Requirement IDs (CON-1, REV-6, …) are defined in `DESIGN.md` §2. Python test
names below are `Class.test_method` inside the file named in the same row.
Node tests are named by their title, and browser checks by their ID (S1, F1a, …).

## How to run

`README.md` covers setup for both virtual environments ("Setup") and what
each suite needs ("Running the tests"). From `assigns/09/`:

```sh
MySolution/.venv/bin/python -B -m unittest discover -s MySolution/tests -t .
node --test MySolution/tests/js/*.test.mjs
node MySolution/tests/browser/studio_flows.mjs
```

To run one Python file at a time, use for example
`MySolution/.venv/bin/python -B -m unittest MySolution.tests.test_revisions`.

## Environment of the recorded runs

| Item | Version |
| --- | --- |
| OS | macOS (Darwin 27.0.0) |
| Python | 3.14.10 |
| Flask / Werkzeug | 3.1.3 / 3.1.9 |
| jsonschema | 4.26.0 (tests only) |
| Node | 26.13.1 |
| Google Chrome | 158.0.8127.89 (headless) |
| LAMBDA3 service | Assign07, unchanged, started from `../07` |

## Results

Latest runs, 2026-11-27, in the working tree:

| Suite | Command | Result |
| --- | --- | --- |
| Python | `unittest discover` | **`Ran 204 tests in 4.744s` — `OK`** (none skipped) |
| Node | `node --test MySolution/tests/js/*.test.mjs` | **25 tests, 25 pass, 0 fail** |
| Browser | `node MySolution/tests/browser/studio_flows.mjs` | **`18/18 checks passed`**, three runs in a row, 6–7 s each |

The same three suites also passed in a fresh copy set up from `README.md`
(see [End-to-end demonstration](#end-to-end-demonstration)):

- Python: `Ran 204 tests in 4.626s` — `OK`;
- Node: 25 pass;
- Browser: 18/18 in each of three runs.

| File | Through | Tests | Covers |
| --- | --- | ---: | --- |
| `test_transport.py` | HTTP test client | 28 | Health, unknown routes, 405 + `Allow`, `OPTIONS`, `HEAD`, media types, body size, malformed JSON, query parameters on every route, CORS |
| `test_failures.py` | HTTP test client | 3 | Sanitized `500 internal_error`, server-side logging, no partial write |
| `test_validation.py` | HTTP test client | 16 | Every field rule on create and update, `expected` shapes, check order, trimming, size boundaries, name uniqueness scopes |
| `test_programs.py` | HTTP test client | 9 | Program CRUD, complete records, reload by a new client, program/case independence |
| `test_collections.py` | HTTP test client | 6 | Collection CRUD, metadata-only update, cascade delete |
| `test_cases.py` | HTTP test client | 8 | Ordered case add/update/delete, unknown parent and case IDs |
| `test_revisions.py` | HTTP test client | 11 | Revision increments, ETags, `If-Match` 428/400/409/404 on all seven mutation routes, no change after failure |
| `test_pagination.py` | HTTP test client | 16 | Page size, cursors, snapshot stability, expiry |
| `test_capacity.py` | HTTP test client | 4 | 500 programs, 100 collections, 100 cases, 100 snapshots |
| `test_concurrency.py` | Real threaded HTTP server | 3 | Same-revision races: exactly one request wins |
| `test_schema.py` | Documents and app | 11 | Schema validity, API.md examples, route and error tables vs Assign09.md, schema, and app |
| `test_unit_validation.py` | Python calls | 30 | Validation boundaries and order without HTTP |
| `test_unit_service.py` | Python calls | 29 | Business rules without HTTP |
| `test_unit_pagination.py` | Python calls | 12 | Snapshot registry |
| `test_unit_concurrency.py` | Python threads | 5 | Atomic operations under 16 racing threads |
| `test_studio_host.py` | Flask test client, a stand-in upstream, and the real LAMBDA3 | 13 | The page and its modules, `/config.json`, forwarding unchanged, relayed statuses, 502/504/413, no database code in the host, real value/syntax/type/runtime outcomes |
| `js/storage.test.mjs` | Node, fake `fetch` | 8 | Adapter URLs, methods, bodies, `If-Match` from the etag, cursor chains, error decoding |
| `js/lambda3.test.mjs` | Node, fake `fetch` | 6 | JSON-RPC requests, outcome categories for every code, transport failures never thrown |
| `js/runner.test.mjs` | Node | 8 | Comparison rules, snapshots, sequential runs, continuing after failures, edit-during-run identity |
| `js/boundaries.test.mjs` | Node, source text | 3 | No REST or JSON-RPC details in `main.js`; logic modules never touch the page |
| `browser/studio_flows.mjs` | Headless Chrome, real services | 18 checks | All five studio flows, conflicts, errors, restart |

Every HTTP test response is also checked by `http_support.py`. The JSON body
must validate against its route's schema in `api.schema.json`, with
`Content-Type: application/json`. A record response must carry `ETag` equal to
its revision; lists and errors carry none. A `204` has no body and no
`Content-Type`.

## Assign09 test items

| Item | Where it is tested |
| --- | --- |
| 1. Health, content types, malformed/invalid requests | `test_transport.py`: `HealthTests`, `MediaTypeTests`, `MalformedJsonTests`, `RouteTests`, `QueryParameterTests` |
| 2. CRUD for programs and collections | `test_programs.py`: `ProgramCrudTests`; `test_collections.py`: `CollectionCrudTests` |
| 3. Case add/update/delete, ordered retrieval | `test_cases.py`: `CaseLifecycleTests` |
| 4. Missing, wrong-type, blank, oversized, unknown fields | `test_validation.py`: `ProgramFieldTests`, `CollectionFieldTests`, `CaseFieldTests` |
| 5. Duplicate names, unknown IDs, page/cursor boundaries | `test_validation.py`: `NameUniquenessTests`; `test_programs.py`: `test_unknown_ids_are_404`; `test_cases.py`: `test_unknown_collection_and_case_ids_are_404`; `test_pagination.py` |
| 6. Revision increments, stale conflicts, no partial mutation | `test_revisions.py`: `RevisionTests`, `PreconditionTests` |
| 7. Concurrent same-revision updates, exactly one succeeds | `test_concurrency.py`: `test_two_updates_with_the_same_revision_exactly_one_succeeds` |
| 8. Collection delete removes cases; program delete keeps case snapshots | `test_collections.py`: `test_delete_removes_the_collection_and_its_cases`; `test_programs.py`: `test_updating_or_deleting_a_program_leaves_case_sources_intact` |
| 9. Studio saves and reloads a program, creates and runs a collection through LAMBDA3, reports an expected success and an expected error | Browser checks F1a–F1c (save, run, browser reload, reopen) and F3a–F4. In F4, `factorial 6` gives `720 : sint`, `bad syntax` gives `-32010`, and `bad argument` gives `-32011`: all three PASS. Two failing cases are reported as FAIL, and the run continues. The same steps were also followed by hand against services started with the README commands (see [End-to-end demonstration](#end-to-end-demonstration)). |

## Requirements → tests

All tests listed passed in the run recorded above.

| ID | File | Tests |
| --- | --- | --- |
| CON-1 | `test_schema.py` | `RouteTableTests.test_routes_and_success_statuses_match_the_assignment`, `ExampleTests.test_every_example_body_matches_its_schema_and_status`, `ExampleTests.test_example_headers_follow_the_etag_rules`, `CrossReferenceTests.test_contents_links_resolve`, `CrossReferenceTests.test_every_contract_requirement_is_cited_and_every_citation_exists` |
| CON-2 | `test_schema.py` | `SchemaDocumentTests.test_schema_is_valid_draft_2020_12`, `SchemaDocumentTests.test_schema_rejects_contract_violations`, `ExampleTests.test_example_request_bodies_match_their_schema`, `RouteTableTests.test_app_serves_exactly_the_documented_routes_and_methods` |
| CON-3 | `test_transport.py` | `HealthTests.test_health`, `HealthTests.test_head_answers_like_get_without_a_body` |
| CON-4 | `test_transport.py`, `test_programs.py` | `ResponseFormatTests.test_json_bodies_are_utf8_json`, `RouteTests.test_location_names_the_new_record`, `ProgramCrudTests.test_delete_removes_the_program` (`204`) |
| CON-5 | `test_transport.py` | `MediaTypeTests.test_json_media_types_are_accepted`, `MediaTypeTests.test_other_media_types_are_415`, `MediaTypeTests.test_every_body_route_checks_the_media_type_before_the_record`, `MediaTypeTests.test_media_type_is_checked_before_size` |
| CON-6 | `test_transport.py` | `MalformedJsonTests.test_malformed_bodies`, `MalformedJsonTests.test_duplicate_members_are_rejected`, `MalformedJsonTests.test_body_must_be_an_object`, `MalformedJsonTests.test_json_is_checked_before_the_record` |
| CON-7 | `test_transport.py`, `test_programs.py`, `test_cases.py` | `RouteTests.test_unknown_paths_are_404_record_not_found`, `ProgramCrudTests.test_unknown_ids_are_404`, `CaseLifecycleTests.test_unknown_collection_and_case_ids_are_404` |
| CON-8 | `test_transport.py` | `RouteTests.test_wrong_method_is_405_with_allow`, `RouteTests.test_options_lists_the_accepted_methods`, `RouteTests.test_path_is_checked_before_method_and_method_before_media_type` |
| CON-9 | `test_transport.py` | `BodySizeTests.test_body_at_the_limit_is_accepted`, `BodySizeTests.test_body_over_the_limit_is_413`, `BodySizeTests.test_size_is_checked_before_json` |
| CON-10 | `test_validation.py`, `test_revisions.py`, `test_capacity.py` | `NameUniquenessTests.test_program_names_are_unique_after_trimming_on_create_and_update`, `PreconditionTests.test_stale_if_match_is_409_with_the_current_revision`, `RecordCapacityTests.test_500_programs_then_capacity_limit` |
| CON-11 | `test_failures.py` | `InternalErrorTests.test_failure_is_a_sanitized_json_500_and_is_logged`, `InternalErrorTests.test_an_undocumented_http_error_is_also_an_internal_error`, `InternalErrorTests.test_failed_mutation_changes_nothing_and_the_service_keeps_working` |
| CON-12 | `test_schema.py`, all HTTP files | `ErrorTableTests.test_codes_and_statuses_agree_across_api_md_schema_and_app`, `ErrorTableTests.test_reasons_agree_between_api_md_and_schema`; every error response is validated against `ErrorResponse` |
| CORS (D4) | `test_transport.py` | `CorsTests.test_allowed_origin_can_read_responses_and_etags`, `CorsTests.test_errors_carry_cors_headers_too`, `CorsTests.test_preflight_allows_if_match`, `CorsTests.test_other_origins_get_no_cors_headers`, `ConfiguredOriginTests.test_configured_origins_replace_the_defaults` |
| VAL-1 | `test_validation.py` | `ProgramFieldTests.test_create_rejects_each_invalid_body`, `CollectionFieldTests.test_create_and_update_reject_each_invalid_body`, `CaseFieldTests.test_add_and_update_reject_each_invalid_body_and_change_nothing`, `ProgramFieldTests.test_check_order_members_first_then_name_source_description` |
| VAL-2 | `test_validation.py` | `ProgramFieldTests.test_name_is_trimmed_source_and_description_are_stored_exactly`, `CollectionFieldTests.test_name_trimming_and_description_limit`, `ProgramFieldTests.test_unpaired_surrogate_is_invalid_text` |
| VAL-3 | `test_validation.py` | `ProgramFieldTests.test_name_is_trimmed_source_and_description_are_stored_exactly`, `ProgramFieldTests.test_update_rejects_each_invalid_body_and_changes_nothing` |
| VAL-4 | `test_programs.py`, `test_collections.py` | `ProgramCrudTests.test_update_without_description_resets_it`, `CollectionCrudTests.test_description_defaults_to_empty` |
| VAL-5 | `test_validation.py`, `test_cases.py` | `CaseFieldTests.test_add_and_update_reject_each_invalid_body_and_change_nothing`, `CaseFieldTests.test_the_three_expected_shapes_are_stored_exactly`, `CaseLifecycleTests.test_update_can_change_the_expected_shape` |
| VAL-6 | `test_validation.py`, `test_capacity.py`, `test_pagination.py` | `ProgramFieldTests.test_field_size_boundaries`, `CaseFieldTests.test_case_size_boundaries`, `RecordCapacityTests.test_500_programs_then_capacity_limit`, `RecordCapacityTests.test_100_collections_then_capacity_limit`, `RecordCapacityTests.test_100_cases_per_collection_then_capacity_limit`, `PageSizeTests.test_limit_boundaries` |
| VAL-7 | `test_transport.py`, `test_pagination.py` | `QueryParameterTests.test_every_route_without_parameters_rejects_them_before_looking_up_records`, `PageSizeTests.test_unknown_and_repeated_parameters`, `PageSizeTests.test_parameter_names_then_limit_then_cursor` |
| DATA-1 | `test_programs.py` | `ProgramCrudTests.test_create_returns_the_complete_record` |
| DATA-2 | `test_collections.py` | `CollectionCrudTests.test_create_returns_the_complete_record_with_no_cases` |
| DATA-3 | `test_cases.py` | `CaseLifecycleTests.test_add_appends_complete_cases_in_order` |
| DATA-4 | `test_programs.py`, `test_validation.py` | `ProgramCrudTests.test_ids_are_generated_and_distinct`; `id` in a body is rejected in `ProgramFieldTests.test_create_rejects_each_invalid_body` |
| DATA-5 | `test_programs.py`, `test_collections.py` | `ProgramCrudTests.test_create_returns_the_complete_record`, `ProgramCrudTests.test_update_replaces_name_source_and_description`, `CollectionCrudTests.test_create_returns_the_complete_record_with_no_cases` |
| DATA-6 | `test_programs.py` | `ProgramCrudTests.test_get_returns_the_saved_record_to_a_new_client`, `ProgramCrudTests.test_update_replaces_name_source_and_description`, `ProgramCrudTests.test_delete_removes_the_program`, `ProgramCrudTests.test_list_returns_full_records_in_creation_order` |
| DATA-7 | `test_collections.py` | `CollectionCrudTests.test_get_returns_the_collection_with_ordered_cases`, `CollectionCrudTests.test_update_changes_metadata_only`, `CollectionCrudTests.test_list_returns_full_collections_with_their_cases` |
| DATA-8 | `test_cases.py` | `CaseLifecycleTests.test_add_returns_201_with_the_collection_and_its_new_etag`, `CaseLifecycleTests.test_update_changes_the_case_in_place`, `CaseLifecycleTests.test_delete_keeps_the_remaining_order_and_returns_the_collection`, `CaseLifecycleTests.test_delete_middle_then_add_appends_at_the_end` |
| DATA-9 | `test_validation.py` | `NameUniquenessTests.test_program_names_are_unique_after_trimming_on_create_and_update`, `NameUniquenessTests.test_collection_names_are_unique_among_collections_only`, `NameUniquenessTests.test_case_names_are_unique_within_one_collection`, `NameUniquenessTests.test_a_deleted_name_can_be_reused` |
| DATA-10 | `test_collections.py` | `CollectionCrudTests.test_delete_removes_the_collection_and_its_cases` |
| DATA-11 | `test_programs.py` | `ProgramIndependenceTests.test_updating_or_deleting_a_program_leaves_case_sources_intact` |
| DATA-12 | Browser, demonstration, inspection | Browser check DATA-12: with the database stopped, the reloaded page shows `Database: unreachable`. After the database service restarts, the reloaded page lists no programs or collections. Check S1: the page warns that data is erased when the service stops. The demonstration below restarted an isolated database process and found both lists empty. The database service modules (the top-level `*.py` files) import only `argparse`, `collections`, `contextlib`, `dataclasses`, `datetime`, `json`, `logging`, `re`, `secrets`, `threading`, `time`, `typing`, `flask`, and `werkzeug`. A search for `sqlite`, `shelve`, `pickle`, and `open(` finds nothing. |
| DATA-13 | `test_studio_host.py`, inspection | `PageTests.test_the_studio_host_does_not_load_the_database_service`. The same search finds no `subprocess`, `socket`, `urllib`, `http.client`, `exec(`, `eval(`, `lambda3`, `interpret`, or `typecheck` in the database service modules. LAMBDA3 is reached only by the studio host, which forwards requests unchanged. |
| STU-1 | `js/boundaries.test.mjs`, `js/storage.test.mjs`, browser | "main.js holds no REST or JSON-RPC details", "only storage.js sends If-Match, and only lambda3.js speaks JSON-RPC", every `storage.test.mjs` test; browser check STU-1 (every change the page sent carried `If-Match`; no JSON-RPC body went to the database) |
| STU-2 | Browser | F1a (create; unsaved marker until saved; Run in LAMBDA3 shows `720 : sint`), F1b (browser reload, list, open, edit, save as revision 2), F1c (second program, creation order) |
| STU-3 | Browser | F2a: another tab saves first. The page shows the conflict with both revisions, keeps the edits, and sends exactly one `PUT` (no automatic retry); the server copy is unchanged. F2b: Reload server copy loads revision 3, keeps the user's version visible, and the next save succeeds. |
| STU-4 | Browser | F3a (create a collection; add value, syntax, and type cases), F3b (edit in place, delete; order kept on page and server), F3c (Reload collection, and reopen after a browser reload) |
| STU-5 | Browser, `js/runner.test.mjs` | F4 (five cases through the real LAMBDA3 via `/lambda/rpc`: three PASS, two FAIL, all reported, summary "3 of 5 passed, 2 failed"), F4b (the run uses the server's saved cases); "one failure does not stop the run, even if interpret throws", "cases run one at a time, in order" |
| STU-6 | Browser | S1 (memory warning), F1a (program marker and title), STU-6 (collection and case markers; leaving warns; Reload collection keeps typed text) |
| STU-7 | Browser, `js/storage.test.mjs`, `js/lambda3.test.mjs` | STU-7a (validation and duplicate-name messages; nothing saved), STU-7b (LAMBDA3 stopped: every case is attempted and fails with "LAMBDA3 unavailable: HTTP 502"), STU-7c (database stopped: "Cannot reach the database service at …"; editor text kept); "network failures and non-API answers become actionable StorageErrors", "anything other than a JSON-RPC answer is a transport outcome, never thrown" |
| STU-8 | Browser, `js/runner.test.mjs` | Browser check STU-8: `answer` is edited through the page while the first case is still running; its row still shows `6 * 7`, `value "42"`, and PASS, marked "edited since this run". Node: "editing or deleting cases during a run cannot change what the results say", "snapshots are frozen deep copies in stored order" |
| STU-9 | `js/runner.test.mjs`, `js/lambda3.test.mjs`, browser | "a value expectation matches only a successful run with exactly that value", "syntax and type expectations match only that LAMBDA3 error", "LAMBDA3 error codes map to outcome categories"; browser F4 (a runtime error vs. an expected syntax error: FAIL), STU-8 (a timeout vs. an expected syntax error: FAIL), STU-7b (transport failures: FAIL) |
| REV-1 | `test_revisions.py` | `RevisionTests.test_program_revisions_increase_by_exactly_one`, `RevisionTests.test_collection_revision_counts_metadata_and_case_changes`, `RevisionTests.test_program_delete_checks_the_revision`, `RevisionTests.test_if_match_is_ignored_on_create` |
| REV-2 | `test_revisions.py`, `test_transport.py` | `RevisionTests.test_collection_revision_counts_metadata_and_case_changes` (including case delete), `RouteTests.test_head_on_a_record_carries_its_etag`; every record response is checked by `http_support.py` |
| REV-3 | `test_revisions.py` | `PreconditionTests.test_missing_if_match_is_428`, `PreconditionTests.test_malformed_if_match_is_400`, `PreconditionTests.test_missing_record_wins_over_any_if_match`, `PreconditionTests.test_current_if_match_succeeds_on_every_route`, `RevisionTests.test_spaces_around_if_match_are_ignored` |
| REV-4 | `test_revisions.py` | `PreconditionTests.test_stale_if_match_is_409_with_the_current_revision`, `PreconditionTests.test_revision_is_checked_before_the_name` |
| REV-5 | `test_revisions.py`, `test_validation.py`, `test_capacity.py`, `test_failures.py` | Snapshot comparisons in `PreconditionTests`, `ProgramFieldTests.test_update_rejects_each_invalid_body_and_changes_nothing`, `CaseFieldTests.test_add_and_update_reject_each_invalid_body_and_change_nothing`, `RecordCapacityTests.test_100_cases_per_collection_then_capacity_limit`, `InternalErrorTests.test_failed_mutation_changes_nothing_and_the_service_keeps_working` |
| REV-6 | `test_concurrency.py`, `test_unit_concurrency.py` | `SameRevisionRaceTests.test_two_updates_with_the_same_revision_exactly_one_succeeds`, `SameRevisionRaceTests.test_eight_case_adds_with_the_same_revision_exactly_one_succeeds`, `SameRevisionRaceTests.test_update_and_delete_with_the_same_revision_exactly_one_succeeds`; `ConcurrentMutationTests`, `ConcurrentCapacityTests` |
| PAGE-1 | `test_pagination.py` | `PageSizeTests.test_default_page_size_is_50`, `PageSizeTests.test_limit_boundaries`, `PageSizeTests.test_limit_must_be_decimal_digits` |
| PAGE-2 | `test_pagination.py` | `SnapshotTests.test_order_is_creation_order_and_repeatable`, `SnapshotTests.test_whole_chain_visits_every_record_once` |
| PAGE-3 | `test_pagination.py` | `SnapshotTests.test_later_pages_come_from_the_snapshot_despite_add_update_delete`, `SnapshotTests.test_collection_snapshots_keep_their_captured_cases`, `SnapshotTests.test_a_cursor_can_be_repeated_and_limit_can_change`, `SnapshotTests.test_single_page_has_no_cursor` |
| PAGE-4 | `test_pagination.py` | `SnapshotTests.test_malformed_cursors`, `SnapshotTests.test_unknown_cursors`, `SnapshotLifetimeTests.test_cursor_expires_600_seconds_after_its_last_use` |
| PAGE-5 | `test_pagination.py`, `test_capacity.py` | `SnapshotLifetimeTests.test_cursor_expires_600_seconds_after_its_last_use`, `SnapshotCapacityTests.test_100_open_snapshots_then_capacity_limit_without_eviction` |
| PAGE-6 | `test_pagination.py`, `test_collections.py`, `test_programs.py` | `SnapshotTests.test_collection_snapshots_keep_their_captured_cases`, `CollectionCrudTests.test_list_returns_full_collections_with_their_cases`, `ProgramCrudTests.test_list_returns_full_records_in_creation_order` |
| DOC-1 | Demonstration | `README.md` was followed in a fresh copy (see [End-to-end demonstration](#end-to-end-demonstration)). Setup installed exactly the pinned packages, the documented commands started all three services, and every REST example and studio tour step gave what the README shows. |
| DOC-2 | This file | Behaviors are mapped to test names, with the observed results above and below. |
| DOC-3 | Inspection | `README.md`, "Architecture". One chain runs studio UI → storage adapter → REST API → validation → business rules → in-memory store. The other runs studio UI → run logic → LAMBDA3 client → studio host → LAMBDA3. The database box contains no LAMBDA code. |
| DOC-4 | HTTP test files | Assign09 test items 1–8 above. Every record is created through the public routes, by way of the `http_support.py` helpers. |
| DOC-5 | Browser, demonstration | Assign09 test item 9 above. |
| DOC-6 | Inspection (2026-11-27) | Run over `assigns/09`: `git status --short --untracked-files=all` lists only source, tests, and documents. `git status --ignored` shows `MySolution/.venv/` as the only ignored path. No `__pycache__` exists outside `.venv`. There are no logs, database files, dumps, fixtures, or secrets. The database service writes no files. |

## End-to-end demonstration

Observed on 2026-11-27, following `README.md` from a clean state. Services
were already running on the default ports 8000, 8009, and 8010. They were
left untouched, so the demonstration used the README's other-ports example.

### Setup from a clean copy

`assigns/07` and `assigns/09` were copied into a scratch folder, keeping the
`assigns/07` + `assigns/09` layout and leaving out virtual environments and
caches. The two "Setup" blocks of the README were then run as written:
`python3 -m venv`, with Python 3.14.10, then `pip install -r
MySolution/requirements.txt`. In both environments, `pip freeze` listed
exactly the pinned versions. In that copy:

- **Python suite:** `Ran 204 tests in 4.626s` — `OK`. The four real-LAMBDA3
  tests ran; none was skipped.
- **Node:** 25 pass.
- **Browser:** `18/18 checks passed` in each of three runs, 7 s each.

### Services

The three services were started from that copy with the documented commands:

```sh
# assigns/07
MySolution/.venv/bin/python -B -m MySolution --port 18000
# assigns/09
MySolution/.venv/bin/python -B -m MySolution --port 18009 --studio-origin http://127.0.0.1:18010
MySolution/.venv/bin/python -B -m MySolution.studio --port 18010 \
  --database-url http://127.0.0.1:18009/api/v1 --lambda-url http://127.0.0.1:18000/rpc
```

Startup logs:

- **LAMBDA3:** `Running on http://127.0.0.1:18000`.
- **Database:**
  - `API at http://127.0.0.1:18009/api/v1; CORS allowed for http://127.0.0.1:18010`;
  - `WARNING ... Records are kept in process memory only and are lost when this process stops.`;
  - `Running on http://127.0.0.1:18009`.
- **Studio:** `Studio at http://127.0.0.1:18010/ using the database at
  http://127.0.0.1:18009/api/v1 and LAMBDA3 at http://127.0.0.1:18000/rpc`.

### REST examples

These are the README's "REST API examples", run with `curl` against that
database. Each request ran in a new `curl` process, so a record read back was
read by a different client than the one that saved it.

| Request | Observed |
| --- | --- |
| `GET /health` | `200`, `{"status": "ok", "version": "1.0"}` |
| `POST /programs` with `answer`, `6 * 7` | `201`, `ETag: "1"`, `Location: /api/v1/programs/prg_ZiNtbNjBNh43NO4T`, revision 1 |
| `GET /programs/{id}` | `200`, the same record, `ETag: "1"` |
| `PUT` with `If-Match: "1"` and a description | `200`, `ETag: "2"`, revision 2 |
| The same `PUT` again with `If-Match: "1"` | `409 revision_conflict`, `"current_revision": 2` |
| `DELETE` without `If-Match` | `428 precondition_required` |
| `POST /collections` `demo`, then `POST /collections/{id}/cases` with `If-Match: "1"` | `201`, `ETag: "1"`; then `201`, `ETag: "2"`, with the case in `cases` |
| `GET /programs?limit=10` | `200`, one item at revision 2, `"next_cursor": null` |
| `GET /programs?limit=0` | `400 invalid_request`, `out_of_range`, `"limit": 100` |
| `POST /programs` with `"id"` in the body | `400 invalid_request`, `server_managed_field` |
| `DELETE` with `If-Match: "2"`, then `GET` | `204` with no `Content-Type`; then `404 record_not_found` |
| `POST /lambda/rpc` on the studio host, `6 * 7`, then `if then` | Real LAMBDA3: `{"type": "sint", "value": "42"}`; then error `-32010`, `Expected an expression` at line 1, column 4 |
| `GET /config.json` on the studio host | `{"database_url":"http://127.0.0.1:18009/api/v1"}` |

### Restart of an isolated database process

- **Before:** `GET /collections` returned one collection, `demo`, at revision
  3 with 2 cases.
- **Restart:** that database process (port 18009) was stopped and started
  again with the same command.
- **After:** `GET /collections` and `GET /programs` both returned
  `{"items": [], "next_cursor": null}`.

### Studio tour

These are the README's "A short tour of the studio", steps 1, 3, and 4. They
were run in headless Chrome against the same three services, by a throwaway
script.

| Step | Observed |
| --- | --- |
| Open the page | `Database: connected`, `LAMBDA3: connected` |
| New program `factorial`, before Save | `Unsaved changes` shown |
| Save | `Saved "factorial" as revision 1.` |
| Run in LAMBDA3 | `720 : sint` |
| Reload the browser page | `factorial` listed; when reopened, its source is identical |
| Create `demo`; it opens straight away | The title reads `demo` |
| Add the five tour cases, then Run all cases | `3 of 5 passed, 2 failed. Each row shows the case as it was when the run started.` |
| Row `factorial`, value `"720"` | `720 : sint` — PASS |
| Row `bad syntax`, syntax error | `LAMBDA syntax error (-32010): Expected an expression at line 1, column 4` — PASS |
| Row `bad argument`, type error | `LAMBDA type error (-32011): function application: expected sint, got bool` — PASS |
| Row `wrong on purpose`, value `"41"` | `42 : sint` — FAIL |
| Row `runtime error`, syntax error | `LAMBDA runtime error (-32013): division by zero` — FAIL |
| Stop the database, reload the page | `Database: unreachable`; `Could not load the test collections: Cannot reach the database service at http://127.0.0.1:18009/api/v1. Check that it is running, then try again.` |
| Start the database again, reload the page | `Database: connected`; 0 programs and 0 collections listed |

The other required behaviors ran against the real services in every browser
run above:

- **Step 2, conflict recovery:** F2a and F2b.
- **Step 5, LAMBDA3 stopped:** STU-7b.
- **Continued execution after a failed case:** F4.
- **Run-snapshot identity:** STU-8.

The browser script checks the program's Run output in F1a and the
`unreachable` chips in DATA-12.

### Default ports

- **2026-11-23:** the database service was started with no options. Its log
  showed the API at `http://127.0.0.1:8009/api/v1`, CORS allowed for
  `http://127.0.0.1:8010` and `http://localhost:8010`, and the memory-only
  warning. A preflight `OPTIONS` from `http://127.0.0.1:8010` returned `204`,
  with `Allow: GET, HEAD, PUT, DELETE, OPTIONS` and the documented
  `Access-Control-*` headers. `If-Match: "0"` returned
  `400 malformed_if_match`.
- **2026-11-24:** all three services were started with their default commands:
  - `/config.json` on port 8010 returned `http://127.0.0.1:8009/api/v1`;
  - the database allowed the studio's origin;
  - a factorial forwarded through `http://127.0.0.1:8010/lambda/rpc` returned
    `720`.

## Sensitivity check

To confirm that the tests detect real defects, deliberate bugs were put into
a temporary copy of the code one at a time. The relevant tests were run
against each copy. These runs used throwaway scripts outside the submission.

**HTTP tests alone** (the eleven HTTP-level files, not the `test_unit_*.py`
files), with 37 bugs:

- **Service rules (15 bugs):**
  - the store lock removed;
  - a revision step of 2;
  - the stale check skipped;
  - the precondition checked before case existence;
  - names not trimmed, or sources trimmed;
  - cursors ignored;
  - snapshots never expiring, or evicted instead of refused;
  - a capacity check off by one;
  - a case delete removing two cases;
  - a metadata update clearing cases;
  - a malformed `If-Match` treated as missing;
  - a record's own name treated as a duplicate;
  - extra `expected` members accepted.
- **HTTP layer (22 bugs):**
  - `Allow` missing, or listing the methods of only one route;
  - no `ETag` on case delete;
  - no media-type check, or the charset ignored;
  - duplicate members, `NaN`, or a byte-order mark accepted;
  - query parameters not checked on `POST`/`PUT` or on `DELETE`;
  - the record looked up before the body was validated;
  - no CORS headers on errors, or no `If-Match` in the preflight;
  - `Content-Type` on a `204`;
  - no `Location`;
  - exception text in a `500`;
  - `//` redirected;
  - the body limit off by one;
  - an `ETag` on lists;
  - `duplicate_name` as `400`;
  - a non-JSON `404`;
  - case add answering `200`.

The first run detected 36 of the 37. The bug that survived was a query
parameter on `DELETE /programs/{id}`, which no test sent.
`QueryParameterTests` now covers all twelve routes that take no parameters.
The rerun detected all 37.

**Unit tests** (`test_unit_*.py`), with the same 15 service-rule bugs: all 15
were detected.

**Studio code**, with 16 bugs. Ten went to the Node tests:

- a timeout matching an expected error;
- values compared after trimming;
- a run stopping at a thrown error;
- results referring to the live cases;
- cases run in parallel;
- no `If-Match`;
- only the first list page read;
- a timeout classified as a syntax error;
- a non-200 answer treated as a result;
- `main.js` building `If-Match` itself.

Six went to the browser flows:

- a stale save retried automatically;
- a conflict discarding local edits;
- no unsaved marker;
- a run using the page's copy with unsaved form text;
- a run that does not re-read the collection;
- no memory warning.

All 16 were detected. Check F4b was added during this check. Before it, no
check showed that a run uses the server's saved cases rather than the page's
copy.

Two more bugs were tried after F1a began checking the program's Run output
and DATA-12 began checking the `unreachable` chips:

- a value shown without its type;
- different wording for an unreachable database.

They were tried together in one run, and both were detected. The first failed
F1a, F4, and STU-8; the second failed DATA-12.
