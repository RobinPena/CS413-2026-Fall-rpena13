# Testing

Requirement IDs (CON-1, REV-6, …) are defined in `DESIGN.md` §2. Test names
below are `Class.test_method` inside the file named in the same row.

## How to run

From `assigns/09/`:

```sh
python3 -m venv MySolution/.venv
MySolution/.venv/bin/python -m pip install -r MySolution/requirements.txt
MySolution/.venv/bin/python -B -m unittest discover -s MySolution/tests -t .
```

One file at a time: `MySolution/.venv/bin/python -B -m unittest MySolution.tests.test_revisions`.
`-B` keeps `__pycache__` out of the submission.

## Environment of the recorded runs

| Item | Version |
| --- | --- |
| OS | macOS (Darwin 27.0.0) |
| Python | 3.14.10 |
| Flask / Werkzeug | 3.1.3 / 3.1.9 |
| jsonschema | 4.26.0 (tests only) |

## Results

Latest full run, 2026-11-24: **`Ran 191 tests in 3.263s` — `OK`**.

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
| DATA-12 | Inspection | The service modules import only `argparse`, `collections`, `contextlib`, `dataclasses`, `datetime`, `json`, `logging`, `re`, `secrets`, `threading`, `time`, `typing`, `flask`, and `werkzeug`. A search for `sqlite`, `shelve`, `pickle`, and `open(` finds nothing. |
| DATA-13 | Inspection | The same search finds no `subprocess`, `socket`, `urllib`, `http.client`, `exec(`, `eval(`, `lambda3`, `interpret`, or `typecheck` in the service modules. |
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

## Running service

The service was started with its documented command and called with `curl`:

```sh
cd assigns/09
MySolution/.venv/bin/python -B -m MySolution
```

Observed on 2026-11-23:

- **Startup log:** the API at `http://127.0.0.1:8009/api/v1`, CORS allowed
  for `http://127.0.0.1:8010` and `http://localhost:8010`, and the warning
  `Records are kept in process memory only and are lost when this process stops.`
- **`GET /api/v1/health`:** `200`, `Content-Type: application/json`, body
  `{"status": "ok", "version": "1.0"}`.
- **`POST /api/v1/programs`** with name `"  factorial "`: `201`, `ETag: "1"`,
  a `Location` naming the new ID, and the stored name `"factorial"`.
- **`PUT`:** with `If-Match: "1"` it returned `200` and `ETag: "2"`; with
  `If-Match: "0"` it returned `400 malformed_if_match`.
- **Preflight `OPTIONS`** from `http://127.0.0.1:8010`: `204` with
  `Allow: GET, HEAD, PUT, DELETE, OPTIONS` and the documented
  `Access-Control-*` headers.
- **`DELETE`** with `If-Match: "2"`: `204` with no `Content-Type`.
  `GET /api/v1/programs?limit=0` returned `400 out_of_range` with
  `"limit": 100`.

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
