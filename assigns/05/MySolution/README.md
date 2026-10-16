# Assign05: Pretty Printing and Capture-Avoiding Substitution

Two operations on the supplied LAMBDA syntax tree, written as visitors over the
expression classes in `../lambda1_vp.py`:

- `d0exp_pretty(e)` prints an expression on one line in the format given by
  the assignment.
- `d0exp_substitute(e, x, r)` returns `e[x := r]`. Binders are renamed when
  needed, so free variables of `r` are never captured.

Neither operation evaluates or changes its input. The supplied interpreter is
imported unchanged.

## Requirements

- Python 3.12 or later, because `lambda1_vp.py` uses `type` statements.
  Developed and tested with Python 3.14.8 on macOS.
- pytest 9.1.1, pinned in `requirements.txt`. The `unittest` suite needs only
  the standard library.

## Setup

From the repository root:

```bash
cd assigns/05
python3 -m venv MySolution/.venv
MySolution/.venv/bin/pip install -r MySolution/requirements.txt
```

If `python3 --version` reports a version older than 3.12, create the virtual
environment with a newer interpreter instead, for example
`python3.14 -m venv MySolution/.venv`.

On Windows (not tested), use `py -3.14 -m venv MySolution\.venv`, then
`MySolution\.venv\Scripts\python` in place of `MySolution/.venv/bin/python`.

## Running the tests

Run both commands from `assigns/05`. Each suite runs on its own and finishes
in under a second.

**unittest** (28 tests, with a subtest for each case):

```bash
MySolution/.venv/bin/python -m unittest discover -s MySolution/tests_unittest -t MySolution -v
```

**pytest** (389 tests, one per case):

```bash
MySolution/.venv/bin/python -m pytest MySolution/tests_pytest -v
```

The pytest suite reads its settings from `MySolution/pytest.ini`. Both suites
take their cases and expected results from `MySolution/examples.py`.

## Examples

From `assigns/05/MySolution`, start `.venv/bin/python` and enter:

```python
>>> from lambda1_visitors import (
...     D0Eint, D0Elam, D0Eop2, D0Evar, d0exp_pretty, d0exp_substitute)
>>> e = D0Elam("y", D0Eop2("+", D0Evar("x"), D0Evar("y")))
>>> d0exp_pretty(e)
'(lam y. (x + y))'
>>> d0exp_pretty(d0exp_substitute(e, "x", D0Evar("y")))
'(lam y_1. (y + y_1))'
>>> d0exp_pretty(e)
'(lam y. (x + y))'
>>> d0exp_pretty(D0Eop2("/", D0Eint(1), D0Eint(0)))
'(1 / 0)'
```

The examples from the assignment give these results. Each one is also a test
case.

| Expression | Substitution | Result |
| --- | --- | --- |
| `(x + z)` | `x := 3` | `(3 + z)` |
| `(lam x. (x + y))` | `x := 3` | `(lam x. (x + y))` |
| `(lam y. (x + y))` | `x := y` | `(lam y_1. (y + y_1))` |
| `(let x = x in (x + y))` | `x := 3` | `(let x = 3 in (x + y))` |
| `(let y = x in (x + y))` | `x := y` | `(let y_1 = y in (y + y_1))` |
| `(fix f(n). (x + (f n)))` | `x := f` | `(fix f_1(n). (f + (f_1 n)))` |
| `x` | `x := (x + 1)` | `(x + 1)` |

## Fresh-name policy

A binder is renamed only when the target occurs free in its scope and the
binder's name is free in the replacement. A binder named `y` becomes the first
of `y_1`, `y_2`, `y_3` and so on as long as its is not already used. A name counts as
used if it is one of these:

- any name in the original expression, whether free, bound or a binder that is
  never referenced
- any name in the replacement
- the substitution target
- any name already generated during the same call

The suffix is always added to the whole binder name. A binder named `y_1` is
renamed to `y_1_1` or later, never to `y_2`.

`AllNamesVisitor` collects the used names once, before the traversal starts.
One `FreshNames` supply then serves the whole call, including every renaming
step. The same inputs therefore always produce the same names. When both
binders of a `fix` must be renamed, the parameter is renamed first, so
`(fix f(f). (x + f))` with `x := f` becomes `(fix f_2(f_1). (f + f_1))`.

## Design

All three visitors subclass the supplied generic `D0ExpVisitor[R]`, where the
type parameter is the result of the operation. `PrettyPrintVisitor` is a
`D0ExpVisitor[str]` and builds each string from the strings of its children.
`AllNamesVisitor` is a `D0ExpVisitor[frozenset[dvar]]` with the same shape as
the supplied `FreeVariableVisitor`, except that it adds binder names instead of
removing them. `SubstitutionVisitor` is a `D0ExpVisitor[d0exp]` and returns an
expression. Every visitor reaches a child only through `child.accept(self)`, so
dispatch always goes through the expression classes and no code tests the type
of a node.

Substitution needs context that the expression does not hold. Instead of
passing extra arguments down the tree, the visitor keeps it in fields set by
its constructor: the target, the replacement, the replacement's free variables
(computed once) and the shared fresh-name supply. `d0exp_substitute` collects
every name in both inputs, seeds the supply with those names and the target,
then starts the traversal. These fields never change during a call, so one
visitor object serves every child.

Scope is handled at the three binding forms. A lambda, `fix` or `let` first
checks whether it binds the target or whether the target is absent from its
body. In either case nothing in the body can change, so the original subtree is
returned and no renaming happens. Otherwise, if a binder name is free in the
replacement, that binder is renamed before substitution continues into the
body. Renaming is itself a substitution. A new `SubstitutionVisitor` replaces
the old name with `D0Evar(fresh)` and shares the same fresh-name supply, so
renaming follows exactly the same scope rules. It stops at an inner binder
that reuses the name and leaves the occurrences that binder owns alone, which a
global string replacement would get wrong. For `let`, the initializer lies
outside the scope. It is substituted before the binder is considered, and
renaming applies only to the body. For `fix`, the parameter is renamed before
the function name. When both binders share a name, the body's occurrences
belong to the parameter, matching the supplied evaluator.

Adding an operation and adding a constructor are not symmetric in this design.
A new operation is one new subclass of `D0ExpVisitor` with a method for each
constructor. No existing class changes, which is why both operations here were
added without editing `lambda1_vp.py`. A new constructor works the other way
around. It needs a new class with its own `accept`, a new abstract method in
`D0ExpVisitor` and a new method in every existing visitor. That includes the
supplied `FreeVariableVisitor` and `EvaluateVisitor` as well as the three
visitors here. The abstract methods keep this safe, since Python refuses to
create a visitor that lacks one, but the change still touches every operation.
The Visitor pattern makes operations cheap to add and constructors expensive,
which suits a language whose syntax is fixed while its tools keep growing.

## Test coverage

Both suites check the same requirements with the same cases, and their tests
have the same names. Cases live in `examples.py`. The group names below are
the comment headings inside `SUBST_CASES`. Exact expected outputs follow the
fresh-name policy above.

| Requirement | Cases | Tests |
| --- | --- | --- |
| 1. Printing every constructor, nesting, negative and large integers, both booleans | `PRETTY_CASES` | `test_pretty_*`: `test_exact_output`, `test_cases_cover_every_constructor` |
| 2. Substitution through every constructor, matching and nonmatching variables, a replacement containing the target | groups "every constructor, matching and nonmatching variables" and "replacement containing the target", plus `SUBST_AST_CASES` | `test_substitute_*`: `test_exact_output`, `test_exact_structure`, `test_cases_cover_every_constructor` |
| 3. Shadowing by lambda, both `fix` binders and `let`, including `fix x(x)` | group "shadowing" | `test_exact_output` |
| 4. Capture avoidance for lambda, `let` and each `fix` binder, including a replacement that conflicts with both | groups "capture avoidance" and "no unnecessary renaming", plus `SUBST_AST_CASES` | `test_exact_output`, `test_exact_structure` |
| 5. Nested shadowing during renaming, collisions with existing bound names and earlier generated names | groups "nested shadowing while renaming" and "fresh names avoid every existing name and earlier generated names" | `test_exact_output`, plus the `FreshNames` tests in `test_names_*` |
| 6. Let initializer versus body | group "let initializer versus body", plus the `let` cases under shadowing and capture avoidance | `test_exact_output`, `test_exact_structure` |
| 7. Inputs preserved, deterministic results, no evaluation | all of `SUBST_CASES`, plus `SUBST_NO_EVAL_CASES` and `PRETTY_NO_EVAL_CASES` | `test_inputs_unchanged`, `test_repeated_calls_agree`, `test_substitutes_without_evaluating`, `test_prints_without_evaluating`, `test_no_eval_*_fail_when_evaluated` |
| Free-variable property | all of `SUBST_CASES`: 44 with the target free and 9 without | `test_free_variables_when_target_is_free`, `test_unchanged_when_target_is_not_free` |

The no-evaluation tests replace `EvaluateVisitor.__init__` with a function that
fails, and they first confirm that evaluation really is blocked. In the pytest
suite that check is its own test, `test_evaluation_is_blocked`.

`test_names_*` also checks `AllNamesVisitor` on every constructor.
`test_imports_*` checks that the solution imports the supplied `lambda1_vp.py`
from `assigns/05`. The pretty, names and substitute tests also check that
each visitor is reached through `accept`.

## Known limitations

- Integers with more than 4,300 digits cannot be printed. Python limits
  integer-to-string conversion to 4,300 digits by default, so `d0exp_pretty`
  raises `ValueError`. `sys.set_int_max_str_digits` raises the limit.
- Each level of nesting uses two Python stack frames, one for `accept` and one
  for the `visit_` method. With the default recursion limit of 1,000,
  expressions nested more than about 500 levels deep raise `RecursionError`.
  The supplied `d0exp_fvset` has the same limit.
- Each binding form that substitution passes through computes the free
  variables of its body, and each renaming walks the body again. Substitution
  can therefore take time quadratic in the size of the expression. Within the
  recursion limit this is not noticeable.
- Results share unchanged subtrees with the inputs, and every occurrence of
  the target is replaced by the same replacement object. The supplied
  expression classes are mutable dataclasses, so changing a result in place
  could also change an input. Neither operation mutates anything itself.
- Fresh names depend on every name in both inputs. The same substitution
  inside a larger expression can therefore choose different names. The results
  are still alpha-equivalent.
- Names and operators are not validated. The printer inserts them as given.

