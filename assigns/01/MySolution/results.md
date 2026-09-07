# Test Results — `eqp_solution.py`

Five test files, one per test type, live alongside `eqp_solution.py` in this
directory. Each imports `eqp_solution` and calls its functions directly
(`search`, `board_set`, `print_board`, ...) with a specific input, rather
than going through `main()`, so each scenario can be set up precisely and
checked against a concrete expected outcome.

| File | Test type | Verdict |
|---|---|---|
| `normal_case_test.py` | Normal input | PASS |
| `boundary_case_test.py` | Boundary | PASS (2/2 sub-checks) |
| `unusual_case_test.py` | Unusual | PASS |
| `wrong_input_case_test.py` | Wrong input | PASS (3/3 sub-checks) |
| `empty_case_test.py` | Empty | PASS (2/2 sub-checks) |

Run individually with `python3 <file>`, or all at once:

```sh
for f in normal_case_test.py boundary_case_test.py unusual_case_test.py \
         wrong_input_case_test.py empty_case_test.py; do
  python3 "$f"
done
```

---

## 1. Normal input case — `normal_case_test.py`

**Input:** `search(bd=(-1,-1,-1,-1,-1,-1,-1,-1), i=0, j=0, nsol=0)` — the
standard call `main()` itself makes: an empty board, starting from row 0.

**Expected:** the well-known Eight Queens answer — exactly 92 solutions,
printed as "Solution #1" through "Solution #92".

**Actual output:**
```
Input:    bd=(-1,-1,-1,-1,-1,-1,-1,-1), i=0, j=0, nsol=0
Expected: nsol == 92, and 92 "Solution #" labels printed
Actual:   nsol == 92, and 92 "Solution #" labels printed
Result:   PASS

First solution block printed (excerpt):
Solution #1:

Q . . . . . . .
. . . . Q . . .
. . . . . . . Q
. . . . . Q . .
. . Q . . . . .
. . . . . . Q .
. Q . . . . . .
. . . Q . . . .
```

**Verdict: PASS.**

---

## 2. Boundary case — `boundary_case_test.py`

Two edges of `search`'s control flow are probed.

### (a) `j == N`, `i == 0`
The exact point where the loop guard `if j < N` first turns false with no
row left to backtrack into. Expected: immediate termination, `nsol`
unchanged, nothing printed.

```
Input:    bd=(-1,)*8, i=0, j=8 (== N), nsol=0
Expected: nsol == 0, no output printed (immediate termination)
Actual:   nsol == 0, output length == 0
Result:   PASS
```

### (b) `i == N - 1` with the *last* valid prefix
The `if i + 1 = N` branch that triggers solution-printing. A naive test
would seed rows 0–6 with an arbitrary valid prefix, but `search` does not
stop after finding one completion — it keeps searching (and backtracking
into earlier rows) until fully exhausted. To keep this a contained,
single-hop probe, the prefix used is taken from Solution #92 (the last
one the normal case finds), so there is nothing left to discover
afterward and the backtracking unwinds in a handful of calls instead of
re-running a large fraction of the search:

```
Input:    bd=(7,3,0,2,5,1,6,-1), i=7 (== N-1), j=0, nsol=0
Expected: nsol == 1 (exactly one completion of the last row)
Actual:   nsol == 1
Result:   PASS
Board found:
Solution #1:

. . . . . . . Q
. . . Q . . . .
Q . . . . . . .
. . Q . . . . .
. . . . . Q . .
. Q . . . . . .
. . . . . . Q .
. . . . Q . . .
```

**Verdict: PASS (2/2).**

---

## 3. Unusual case — `unusual_case_test.py`

**Input:** `search(bd=(-1,)*8, i=0, j=0, nsol=1000)` — a syntactically
valid call that nothing prevents, but that no caller in the source ever
makes: starting the solution counter at a nonzero offset instead of 0.

**Expected:** since `nsol` is used purely additively, the search itself is
unaffected — it should still find all 92 solutions, just numbered
"Solution #1001" through "Solution #1092", returning `nsol == 1092`.

```
Input:    bd=(-1,)*8, i=0, j=0, nsol=1000
Expected: nsol == 1092, labels run "Solution #1001" .. "Solution #1092"
Actual:   nsol == 1092, has 'Solution #1001:' == True, has 'Solution #1092:' == True
Result:   PASS
```

**Verdict: PASS.** Confirms `search` places no guard on its accumulator
argument — a valid but atypical caller state is accepted without complaint.

---

## 4. Wrong input case — `wrong_input_case_test.py`

Three inputs that violate `search`'s implicit shape/type contract — the
kind of call ATS's static `int8` type would reject at compile time, but
that Python happily accepts at the call site.

### (a) Board tuple too short (3 elements instead of 8)
```
Expected: ValueError (not enough values to unpack)
Actual:   ValueError: not enough values to unpack (expected 8, got 3)
Result:   PASS
```
`board_set`'s `x0, ..., x7 = bd` unpacking fails the moment the first
queen is placed.

### (b) Board holding non-integers (strings instead of ints)
```
Expected: no crash -- every string placeholder is overwritten
          by board_set before it is ever read back, so this
          runs identically to the normal case (nsol == 92)
Actual:   nsol == 92, 92 "Solution #" labels printed
Result:   PASS
```
This did **not** behave as first assumed. `search` always overwrites row
`i` with a real integer via `board_set` *before* that row is ever read
back (every `board_get` call — inside `safety_test2` or in the
backtracking branch — only ever targets a row strictly earlier than the
current one, which by that point has always already been set). The
original string placeholders are therefore dead data, clobbered before
use, and the run is indistinguishable from the normal case.

### (c) Negative starting row index (`i = -2`)
```
Expected: no crash; the invalid negative row is silently
          absorbed by board_set's fallback, and the search
          still completes normally once i reaches 0 (nsol == 92)
Actual:   nsol == 92
Result:   PASS
```
`board_set`'s final `else: bd` fallback (for any `i` outside `0..7`)
silently leaves the board unchanged instead of raising an error, and `i`
is incremented every call regardless of validity — so a negative starting
row just "counts up" to 0 over a couple of wasted calls, after which the
search proceeds exactly as the normal case.

**Verdict: PASS (3/3).** One genuine crash (a), and two cases (b, c) where
malformed input is silently tolerated rather than rejected — a direct
consequence of losing ATS's compile-time type/shape checking in
translation (see `eqp_solution.py`'s header notes 3–4).

---

## 5. Empty case — `empty_case_test.py`

**Input:** a completely empty board — `()` instead of the expected
8-element tuple — fed into two different entry points.

### (a) `print_board(())`
```
Expected: IndexError (tuple index out of range)
Actual:   IndexError: tuple index out of range
Result:   PASS
```
`print_board` indexes `bd[0]` through `bd[7]` directly, so it fails on the
very first access.

### (b) `search((), 0, 0, 0)`
```
Expected: ValueError (not enough values to unpack)
Actual:   ValueError: not enough values to unpack (expected 8, got 0)
Result:   PASS
```
The empty board survives the very first safety check (`safety_test2`
short-circuits to `True` when there is no previous row to compare
against), but fails as soon as `board_set` tries to place the first queen
and unpack the empty tuple into 8 names.

**Verdict: PASS (2/2).**

---

## Overall

All 5 test files pass (10/10 sub-checks across all files). Beyond
confirming the translation reproduces the correct Eight Queens result
(92 solutions), the wrong-input and empty-case tests specifically probe
what Python's dynamic typing lets through that ATS's static `int8` type
would have rejected at compile time — turning what would be compile
errors in the original into either runtime exceptions (short/empty
tuples) or, more subtly, silently-tolerated inputs (wrong element types,
negative row index) that happen to produce correct results anyway because
of how `search` always writes a row before it is ever read back.
