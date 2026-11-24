"""The documented limits (API.md section 4), gathered in one value.

The defaults are the contract. Tests may build a Limits with smaller
capacities so boundaries can be reached quickly.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    max_body_bytes: int = 1_048_576
    max_name_chars: int = 100
    max_description_chars: int = 1_000
    max_source_bytes: int = 65_536          # the Assign07 LAMBDA3 service's own limit
    max_expected_value_bytes: int = 8_192
    max_programs: int = 500
    max_collections: int = 100
    max_cases_per_collection: int = 100
    default_page_size: int = 50
    max_page_size: int = 100
    max_snapshots: int = 100
    snapshot_idle_seconds: float = 600.0
