# Design: Compiling LAMBDA to Pure Lambda Calculus

## 1. Two languages, one evaluator

The source language is the extended LAMBDA syntax from
`assigns/05/lambda1_vp.py`, used unchanged: natural and boolean literals,
variables, lambdas, applications, `not`, nine strict binary operators,
`and`/`or`, `if`, `let`, pairs with projections, and `fix`. The target
language, in `target.py`, has exactly three immutable forms, `Var`, `Lam`
and `App`, which check their children, so no source node or Python value
can appear in a target term.

```
source AST --compile_expr--> pure term --evaluate--> value --observe--> data
     \                                       ^
      +------------evaluate (source mode)----+     one machine, two adapters
```

`evaluator.py` is one explicit-stack machine with a small adapter per
language: `start` classifies a node and `contract` applies a function value
to an argument value. Variables, lambdas and applications are reported as
shared cases and handled identically for both languages; only source forms
push extra frames. Budget checks and step counting live in the single
shared application frame. The evaluator and compiler do not import each
other.

## 2. Representations

Data are Church encodings, built in `encodings.py` as closed terms:

```
TRUE = lam t. lam f. t          FALSE = lam t. lam f. f
NUM(n) = lam s. lam z. s (... (s z))      PAIR = lam a. lam b. lam p. p a b
FST = lam p. p TRUE             SND = lam p. p FALSE        I = lam w. w
SUCC = lam n. lam s. lam z. s (n s z)
ADD = lam m. lam n. lam s. lam z. m s (n s z)    MUL = lam m. lam n. lam s. m (n s)
ISZERO = lam n. n (lam x. FALSE) TRUE
SHIFT = lam q. PAIR (SND q) (SUCC (SND q))
PRED = lam n. FST (n SHIFT (PAIR NUM(0) NUM(0)))     SUB = lam m. lam n. n PRED m
NOT = lam b. b FALSE TRUE   AND = lam a. lam b. a b FALSE   OR = lam a. lam b. a TRUE b
LEQ = lam m. lam n. ISZERO (SUB m n)     GEQ = lam m. lam n. ISZERO (SUB n m)
LT = lam m. lam n. NOT (GEQ m n)         GT = lam m. lam n. NOT (LEQ m n)
EQ = lam m. lam n. AND (LEQ m n) (GEQ m n)    NEQ = lam m. lam n. NOT (EQ m n)
Z = lam g. (lam x. g (lam v. x x v)) (lam x. g (lam v. x x v))
```

A numeral `n` is "apply `s` n times", which is why addition and
multiplication are short. Predecessor cannot remove an application, so it
rebuilds the number. `SHIFT` maps a pair `(previous, current)` to
`(current, current + 1)`. The invariant is that after k shifts starting from
`(0, 0)` the pair is `(k - 1, k)` for k at least 1: one shift gives `(0, 1)`,
and a shift of `(k - 1, k)` gives `(k, k + 1)`. `PRED n` performs n shifts and
takes the first component, `n - 1`. For n = 0 no shift happens and the first
component of `(0, 0)` is 0, so `PRED 0 = 0`. `SUB m n` applies `PRED` to m,
n times, so it stops at zero, which is the truncated subtraction the
language requires. Each comparison reduces to "is a truncated difference
zero": m ≤ n exactly when m − n truncates to 0.

## 3. Translation rules

`C[e]` is computed by `CompileVisitor`, a `D0ExpVisitor`. Every rule builds
the result from the translations of the children; `u` and `v` are fresh
thunk parameters.

| Source `e` | `C[e]` |
| --- | --- |
| `n` (n ≥ 0) | `NUM(n)` |
| `true` / `false` | `TRUE` / `FALSE` |
| `x` | `x` |
| `lam x. e` | `lam x. C[e]` |
| `e1 e2` | `C[e1] C[e2]` |
| `not e` | `NOT C[e]` |
| `e1 + e2`, `e1 - e2`, `e1 * e2` | `ADD C[e1] C[e2]`, `SUB C[e1] C[e2]`, `MUL C[e1] C[e2]` |
| `e1 < e2`, `e1 <= e2`, `e1 > e2` | `LT C[e1] C[e2]`, `LEQ C[e1] C[e2]`, `GT C[e1] C[e2]` |
| `e1 >= e2`, `e1 == e2`, `e1 != e2` | `GEQ C[e1] C[e2]`, `EQ C[e1] C[e2]`, `NEQ C[e1] C[e2]` |
| `e1 and e2` | `(C[e1] (lam u. C[e2]) (lam v. FALSE)) I` |
| `e1 or e2` | `(C[e1] (lam u. TRUE) (lam v. C[e2])) I` |
| `if c then e1 else e2` | `(C[c] (lam u. C[e1]) (lam v. C[e2])) I` |
| `let x = e1 in e2` | `(lam x. C[e2]) C[e1]` |
| `pair e1 e2` | `PAIR C[e1] C[e2]` |
| `fst e` / `snd e` | `FST C[e]` / `SND C[e]` |
| `fix f(x). e` | `Z (lam f. lam x. C[e])` |

Combinator names are inlined as their terms; the output contains no names
like `ADD`. Before translating, `validate_source` walks the whole tree and
rejects negative literals, division and other unsupported operator
spellings, including inside branches that would never run and bodies that
are never applied, because the program is inspected rather than executed.

## 4. Names, scope and freshness

Scope carries over directly. `lam x` binds in its body; `let x` becomes a
`lam x` around the body only, so the initializer sees the outer `x`; and
`fix f(x)` becomes `lam f. lam x`, so both names scope over the body. When
the names coincide, the inner `lam x` shadows `lam f`, so the parameter
wins, as in the source.

Combinators are closed, so inlining one can neither capture nor free a
variable. The only invented names are thunk parameters. Each `compile_expr`
call seeds a `FreshNames` supply with every name in the source (free, bound
or unused) and every library binder, then takes the first unused `u_k` and
`v_k` in translation order. No source name is reserved: a free `s`, `z`,
`t`, `f`, `x` or `u_1` stays free. Hence FV(C[e]) = FV(e), the output is
deterministic, and the source tree is never modified.

Target substitution renames a binder that would capture a free variable of
the replacement to the first unused `y_k`, carrying the renaming through
the same pass. Closed execution substitutes only closed values and never
renames; renaming is tested directly on open terms.

## 5. Call-by-value, thunks and recursion

Both languages use weak, left-to-right call-by-value: function, then
argument, then contraction; nothing under a lambda; no eta reduction. Only
contractions `(lam x. body) v` with `v` a lambda are counted.

Because arguments are evaluated first, `TRUE C[e1] C[e2]` would run both
branches, and an unused diverging branch would hang the program. So each
branch is wrapped in a lambda, which is already a value. The boolean selects
one thunk without running either, and applying the selection to `I` runs
only that one. `and` and `or` use the same shape with a constant branch.
Strict constructs get no thunks: operators, pairs and `let` pass their
translated operands as arguments, computed left to right even when unused.

`Y = lam g. (lam x. g (x x)) (lam x. g (x x))` fails under call-by-value:
`Y G` reaches `G (H H)` with `H = lam x. G (x x)`, and evaluating the
argument `H H` reproduces `G (H H)` forever (a test confirms no value
appears). `Z` instead wraps the self-application as the value
`lam v. x x v`. With `H = lam x. G (lam v. x x v)` and `R = lam v. H H v`,
`Z G` reaches `G R` in two steps and then the function
`lam x. C[e][f := R]`. Self-application waits until a recursive call
supplies an argument `a`; then `R a` unrolls one more level.

## 6. Bounded execution and observation

Execution and observation are separate runs of the same evaluator with
separate budgets. Execution returns `Completed(value, steps, budget)` or
`Exhausted(steps, budget)`; exhaustion means another step was needed, not
that the program diverges. A value reached on the last allowed step
completes, and a lambda completes in zero steps at budget zero.

A completed value may hold redexes under its binders, so
`observe(value, kind, budget)` applies it to a pure context instead of
reading its syntax. A natural runs `v STEP BASE`, leaving a finished spine
of `lam c. lam z. c tail` nodes over `lam c. lam z. z`, which Python counts
up to renaming. A boolean runs `v YES NO`, whose three-parameter markers
differ from every boolean and numeral, and compares the result with each
marker up to alpha-equivalence. A pair decodes `FST v` and `SND v`
recursively by component kind. The caller supplies the kind, since `NUM(0)`
and `FALSE` are the same term. One budget covers all components; outcomes
are `Decoded`, `ObservationExhausted` (with a component path) or
`Malformed`.

## 7. Correctness argument

The intended claim is: for closed, well-typed programs in the specified
call-by-value source language whose result is a natural, a boolean, or a
finite pair of such data, observing the result of the compiled program
yields the same data as source evaluation, given sufficient reduction
resources.

The argument relates source values to target values. A target value is
related to `n` if it behaves as "apply `s` n times", to a boolean if it
selects the matching argument, and to a pair if its projections are related
to the components. Functions cannot be compared as data, so a target value
is related to a source function if, applied to related arguments, it
behaves like the source application: both yield related values or neither
finishes. This relation for functions carries the argument through
higher-order programs such as DEMO-07. Literals and library combinators are
related to their source operations by the definitions in Section 2, which
the encoding tests check separately.

Proceeding by induction on source evaluation:

- **Application.** The source evaluates `e1` to a function, `e2` to a value
  and then the body. The target evaluates `C[e1]`, then `C[e2]`, to related
  values in the same order, then contracts. The function relation makes the
  result related. Because the order matches, a diverging subterm stalls both
  programs, which is the strict sequencing DEMO-09 shows.
- **Conditional.** `C[c]` yields a value related to a boolean, which selects
  one of the two thunk values; applying it to `I` runs only that
  branch, because the fresh parameter does not occur in it. The unselected
  branch is never applied, matching the source.
- **Let.** `(lam x. C[e2]) C[e1]` evaluates the initializer first, then
  substitutes its value for `x` in the body only, as the source does.
- **Recursion.** Section 5 shows `Z G` evaluates to a function whose
  recursive reference `R` behaves, on any argument value, like that function
  itself. Each source call unrolls `fix` once and each target call unrolls
  `R` once, so the two stay related call by call.

This is a sketch, not a formal proof. It does not claim full abstraction,
equality of functions, or general agreement on termination. Tests support
it with explicit expected answers, source and target agreement over every
constructor and operator, exhaustion where strictness requires it, and
deliberately broken copies of the code confirmed to fail the suite, but
tests only sample programs.

## 8. Tradeoffs and limitations

Substitution-based evaluation mirrors the beta rule and lets one machine
serve both languages without closures, at the cost of copying terms; cached
free-variable sets let substitution skip unaffected subterms. Target
operations use explicit stacks, so large terms and long runs never reach
Python's recursion limit. The source visitors recurse through `accept`, so
source trees nested beyond about 330 levels exceed Python's default limit;
the required examples are far shallower.

Unary numerals and pair-based predecessor make subtraction and comparison
costs grow with the operands, and weak reduction leaves work under binders
for observation: factorial 6 executes in 859 steps but observes in 6,590.
Fibonacci 10 executes in 27,560 steps (0.24 s here). Target execution
rejects open terms, though compilation handles them. The observers cannot
recognize every invalid untyped term; `I`, for example, observes as the
natural 1.
