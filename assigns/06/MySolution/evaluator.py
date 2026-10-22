"""One evaluator for both source ASTs and pure target terms.

    evaluate(program, budget=None, on_step=None) -> Completed | Exhausted

Both languages use weak, left-to-right call-by-value, and both are run by
the same machine, `_run`. The machine keeps its pending work on an explicit
stack of frames instead of recursing in Python, so a long or deeply nested
reduction can never hit Python's recursion limit and be mistaken for a spent
budget.

Each language tells the machine two things:

- `start(node)`: how evaluation of a node begins. Variables, lambdas and
  applications are reported as the shared cases CoreVar, CoreLam and
  CoreApp, and the machine handles those cases identically for both
  languages. Only source nodes have further forms, each of which begins by
  evaluating a subexpression with a source frame waiting for its value.
- `contract(fn, arg)`: what applying a function value to an argument value
  produces. For target terms this is the beta-value step
  (lam x. body) v --> body[x := v], with capture-avoiding substitution. For
  source programs it is substitution into a lambda body or, for the
  source-only fix form, unrolling the recursive function.

Every contraction goes through the machine's single application rule, which
checks the budget and counts the step. For target terms the count is
therefore exactly the number of beta-value steps; traversal, name analysis,
renaming and printing are never counted. For source programs the same count
is the number of function applications (of lam or fix values); arithmetic,
let, conditionals and projections are not counted.

Target values are lambdas. The target path uses only target terms and
target substitution: it never sees a source node or a source operation.
Source values are source expressions too (literals, lambdas, fix functions
and pairs of values), substituted into bodies just like target values, so
neither language uses closures or environments.

Execution is restricted to closed programs in both languages, checked
before running (OpenTermError). Source programs are also checked over the
whole tree for unsupported forms before running (UnsupportedSourceError).
A target run must be given a budget; a source run may omit it, which is
fine for terminating programs but would never return for a divergent one.
This module never imports or runs the compiler.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .results import Completed, Exhausted, OpenTermError, SourceEvaluationError
from .source_support import (
    D0E000, D0Eapp, D0Ebtf, D0Efix, D0Eif0, D0Eint, D0Elam, D0Elet, D0Eop1,
    D0Eop2, D0Epair, D0Epfst, D0Epsnd, D0Evar, D0ExpVisitor, show_source,
    source_fv, source_substitute, validate_source,
)
from .target import App, Lam, Term, Var, free_vars, is_term, substitute

type StepHook = Callable[[int, object, object], None]


def evaluate(program: Term | D0E000, budget: int | None = None,
             on_step: StepHook | None = None) -> Completed | Exhausted:
    """Evaluate a closed source AST or target term.

    `budget` is the most contractions allowed. A value completes with zero
    steps even when the budget is zero, and a value reached on the last
    allowed step completes. Exhausted means another contraction was needed
    after the budget was spent. `on_step(step, fn, arg)` is called after
    each contraction is counted, with the function and argument values.
    """
    if budget is not None and (type(budget) is not int or budget < 0):
        raise ValueError(f"budget must be a nonnegative integer, not {budget!r}")
    if is_term(program):
        if budget is None:
            raise ValueError("target execution needs a step budget")
        language, free = TARGET, free_vars(program)
    elif isinstance(program, D0E000):
        validate_source(program)
        language, free = SOURCE, source_fv(program)
    else:
        raise TypeError(f"not a source AST or target term: {program!r}")
    if free:
        raise OpenTermError(free)
    return _run(program, language, budget, on_step)


########################################################################
# Instructions: what the machine does next.

@dataclass(frozen=True, slots=True)
class Eval:
    """Evaluate `node`; if `then` is given, push it to receive the value."""
    node: object
    then: object = None


@dataclass(frozen=True, slots=True)
class Return:
    """Hand `value` to the innermost waiting frame."""
    value: object


# The three cases shared by both languages.

@dataclass(frozen=True, slots=True)
class CoreVar:
    name: str


@dataclass(frozen=True, slots=True)
class CoreLam:
    function: object


@dataclass(frozen=True, slots=True)
class CoreApp:
    fn: object
    arg: object


# The two frames of the shared application rule.

@dataclass(frozen=True, slots=True)
class _EvalArg:
    """The function is a value; evaluate the argument next."""
    arg: object


@dataclass(frozen=True, slots=True)
class _Call:
    """The argument is a value; contract `fn` applied to it."""
    fn: object


def _run(program, language, budget: int | None,
         on_step: StepHook | None) -> Completed | Exhausted:
    steps = 0
    stack: list = []
    instruction = Eval(program)
    while True:
        match instruction:
            case CoreVar(name):
                # Unreachable for a closed program: substitution replaces
                # each bound variable before evaluation can reach it.
                raise OpenTermError(frozenset({name}))
            case CoreLam(function):
                # A function is a value; its body waits until it is applied.
                instruction = Return(function)
            case CoreApp(fn, arg):
                instruction = Eval(fn, _EvalArg(arg))
            case Eval(node, then):
                if then is not None:
                    stack.append(then)
                instruction = language.start(node)
            case Return(value):
                if not stack:
                    return Completed(value, steps, budget)
                frame = stack.pop()
                match frame:
                    case _EvalArg(arg):
                        instruction = Eval(arg, _Call(value))
                    case _Call(fn):
                        if budget is not None and steps == budget:
                            return Exhausted(steps, budget)
                        steps += 1
                        if on_step is not None:
                            on_step(steps, fn, value)
                        instruction = Eval(language.contract(fn, value))
                    case _:
                        instruction = frame.resume(value)


########################################################################
# Target terms: only the shared cases, and beta-value contraction.

class _Target:
    @staticmethod
    def start(node: Term):
        match node:
            case Var(name):
                return CoreVar(name)
            case Lam():
                return CoreLam(node)
            case App(fn, arg):
                return CoreApp(fn, arg)
        raise TypeError(f"not a target term: {node!r}")

    @staticmethod
    def contract(fn: Lam, arg: Lam) -> Term:
        # Every target value is a lambda, so fn is (lam x. body) and arg is v.
        return substitute(fn.body, fn.name, arg)


TARGET = _Target()


########################################################################
# Source programs: the shared cases plus the source-only rules.

def _boolean(value: D0E000, where: str) -> bool:
    if isinstance(value, D0Ebtf):
        return value.arg1
    raise SourceEvaluationError(f"{where} needs a boolean, got {show_source(value)}")


def _natural(value: D0E000, where: str) -> int:
    if isinstance(value, D0Eint):
        return value.arg1
    raise SourceEvaluationError(f"{where} needs a natural, got {show_source(value)}")


# Python arithmetic is allowed here: this is the source language's own
# semantics, never used on target terms.
_BINARY = {
    "+": lambda m, n: D0Eint(m + n),
    "-": lambda m, n: D0Eint(max(m - n, 0)),  # truncated subtraction
    "*": lambda m, n: D0Eint(m * n),
    "<": lambda m, n: D0Ebtf(m < n),
    "<=": lambda m, n: D0Ebtf(m <= n),
    ">": lambda m, n: D0Ebtf(m > n),
    ">=": lambda m, n: D0Ebtf(m >= n),
    "==": lambda m, n: D0Ebtf(m == n),
    "!=": lambda m, n: D0Ebtf(m != n),
}


# Source frames. Each waits for one value, then says what happens next.

@dataclass(frozen=True, slots=True)
class _Not:
    def resume(self, value):
        return Return(D0Ebtf(not _boolean(value, "not")))


@dataclass(frozen=True, slots=True)
class _LeftOperand:
    """The left operand is done. and/or may skip the right operand."""
    op: str
    right: D0E000

    def resume(self, left):
        if self.op == "and":
            if not _boolean(left, "and"):
                return Return(D0Ebtf(False))
            return Eval(self.right, _BooleanResult("and"))
        if self.op == "or":
            if _boolean(left, "or"):
                return Return(D0Ebtf(True))
            return Eval(self.right, _BooleanResult("or"))
        return Eval(self.right, _RightOperand(self.op, _natural(left, self.op)))


@dataclass(frozen=True, slots=True)
class _BooleanResult:
    """The selected right operand of and/or is the result."""
    op: str

    def resume(self, right):
        _boolean(right, self.op)
        return Return(right)


@dataclass(frozen=True, slots=True)
class _RightOperand:
    op: str
    left: int

    def resume(self, right):
        return Return(_BINARY[self.op](self.left, _natural(right, self.op)))


@dataclass(frozen=True, slots=True)
class _Branch:
    then: D0E000
    else_: D0E000

    def resume(self, cond):
        return Eval(self.then if _boolean(cond, "if") else self.else_)


@dataclass(frozen=True, slots=True)
class _LetBody:
    name: str
    body: D0E000

    def resume(self, value):
        return Eval(source_substitute(self.body, self.name, value))


@dataclass(frozen=True, slots=True)
class _PairSecond:
    second: D0E000

    def resume(self, first):
        return Eval(self.second, _PairDone(first))


@dataclass(frozen=True, slots=True)
class _PairDone:
    first: D0E000

    def resume(self, second):
        return Return(D0Epair(self.first, second))


@dataclass(frozen=True, slots=True)
class _Project:
    first: bool

    def resume(self, value):
        if not isinstance(value, D0Epair):
            where = "fst" if self.first else "snd"
            raise SourceEvaluationError(
                f"{where} needs a pair, got {show_source(value)}")
        return Return(value.arg1 if self.first else value.arg2)


class _SourceStart(D0ExpVisitor[object]):
    """How evaluation of each source form begins, chosen through accept."""

    # The shared cases.
    def visit_var(self, dexp: D0Evar):
        return CoreVar(dexp.arg1)

    def visit_lam(self, dexp: D0Elam):
        return CoreLam(dexp)

    def visit_app(self, dexp: D0Eapp):
        return CoreApp(dexp.arg1, dexp.arg2)

    # Source-only values.
    def visit_int(self, dexp: D0Eint):
        return Return(dexp)

    def visit_btf(self, dexp: D0Ebtf):
        return Return(dexp)

    def visit_fix(self, dexp: D0Efix):
        return Return(dexp)

    # Source-only forms that first evaluate a subexpression, left to right.
    def visit_op1(self, dexp: D0Eop1):
        return Eval(dexp.arg1, _Not())

    def visit_op2(self, dexp: D0Eop2):
        return Eval(dexp.arg1, _LeftOperand(dexp.name, dexp.arg2))

    def visit_if0(self, dexp: D0Eif0):
        return Eval(dexp.arg1, _Branch(dexp.arg2, dexp.arg3))

    def visit_let(self, dexp: D0Elet):
        # The initializer runs first and outside the let's scope.
        return Eval(dexp.arg2, _LetBody(dexp.arg1, dexp.arg3))

    def visit_pair(self, dexp: D0Epair):
        return Eval(dexp.arg1, _PairSecond(dexp.arg2))

    def visit_pfst(self, dexp: D0Epfst):
        return Eval(dexp.arg1, _Project(first=True))

    def visit_psnd(self, dexp: D0Epsnd):
        return Eval(dexp.arg1, _Project(first=False))


class _Source:
    _starter = _SourceStart()

    def start(self, node: D0E000):
        return node.accept(self._starter)

    @staticmethod
    def contract(fn: D0E000, arg: D0E000) -> D0E000:
        match fn:
            case D0Elam(param, body):
                return source_substitute(body, param, arg)
            case D0Efix(fname, param, body):
                # Unroll: the body sees the function itself and the argument.
                # If both names coincide, the parameter shadows the function
                # name, so only the argument is substituted.
                if fname != param:
                    body = source_substitute(body, fname, fn)
                return source_substitute(body, param, arg)
        raise SourceEvaluationError(f"cannot apply a non-function: {show_source(fn)}")


SOURCE = _Source()
