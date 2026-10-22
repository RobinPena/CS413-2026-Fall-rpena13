"""Pure lambda terms: the three-form target AST and its name operations.

    Term ::= Var(name) | Lam(name, body) | App(fn, arg)

Terms are immutable, so a result can share unchanged subtrees with its input
without either one ever changing the other. Each node also caches its set of
free variables, computed from its children when the node is built. That cache
is derived data, not a fourth form: it is left out of the constructor,
equality and printing. It lets substitution skip, in constant time, every
subtree in which the substituted name is not free.

Every operation walks terms with an explicit stack instead of Python
recursion, because evaluation can build terms nested far deeper than
Python's default limit of 1,000 frames.

Nothing in this module knows about the source language or Church encodings.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from .names import FreshNames, is_identifier


def _check_name(name: object) -> None:
    if not isinstance(name, str) or not is_identifier(name):
        raise ValueError(f"not a valid identifier: {name!r}")


def _check_term(value: object, role: str) -> None:
    if not isinstance(value, (Var, Lam, App)):
        raise TypeError(f"{role} must be a target term, not {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class Var:
    name: str
    fv: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _check_name(self.name)
        object.__setattr__(self, "fv", frozenset((self.name,)))

    def __str__(self) -> str:
        return show(self)


@dataclass(frozen=True, slots=True)
class Lam:
    name: str
    body: Term
    fv: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _check_name(self.name)
        _check_term(self.body, "a lambda body")
        body_fv = self.body.fv
        object.__setattr__(self, "fv", body_fv - {self.name}
                           if self.name in body_fv else body_fv)

    def __str__(self) -> str:
        return show(self)


@dataclass(frozen=True, slots=True)
class App:
    fn: Term
    arg: Term
    fv: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _check_term(self.fn, "an applied function")
        _check_term(self.arg, "an argument")
        fn_fv, arg_fv = self.fn.fv, self.arg.fv
        object.__setattr__(self, "fv", fn_fv | arg_fv
                           if fn_fv and arg_fv else fn_fv or arg_fv)

    def __str__(self) -> str:
        return show(self)


type Term = Var | Lam | App

TERM_TYPES = (Var, Lam, App)


def is_term(value: object) -> bool:
    return isinstance(value, TERM_TYPES)


########################################################################
# Builders. They only nest the three forms; there is no multi-argument node.

def app(fn: Term, *args: Term) -> Term:
    """Left-nested application: app(f, a, b) is ((f a) b)."""
    if not args:
        raise ValueError("app needs at least one argument")
    term = fn
    for arg in args:
        term = App(term, arg)
    return term


def lam(*parts: str | Term) -> Lam:
    """Nested abstraction: lam("a", "b", body) is (lam a. (lam b. body))."""
    *names, body = parts
    if not names:
        raise ValueError("lam needs at least one parameter name")
    for name in reversed(names):
        body = Lam(name, body)
    return body


########################################################################
# Printing and traversal.

def show(term: Term) -> str:
    """Print in the required notation: x, (lam x. body) and (fn arg)."""
    pieces: list[str] = []
    todo: list[Term | str] = [term]
    while todo:
        item = todo.pop()
        match item:
            case str():
                pieces.append(item)
            case Var(name):
                pieces.append(name)
            case Lam(name, body):
                pieces.append(f"(lam {name}. ")
                todo += [")", body]
            case App(fn, arg):
                pieces.append("(")
                todo += [")", arg, " ", fn]
    return "".join(pieces)


def iter_nodes(term: Term) -> Iterator[Term]:
    """Yield every node occurrence in pre-order, shared subtrees each time."""
    todo = [term]
    while todo:
        node = todo.pop()
        yield node
        match node:
            case Lam(_, body):
                todo.append(body)
            case App(fn, arg):
                todo += [arg, fn]


def size(term: Term) -> int:
    """Number of nodes in the printed term."""
    return sum(1 for _ in iter_nodes(term))


def free_vars(term: Term) -> frozenset[str]:
    """Names with a free occurrence: lambda binds its name in its body."""
    return term.fv


def all_names(term: Term) -> frozenset[str]:
    """Every variable and binder name, bound or free, used or unused.

    Freshness needs this rather than free_vars: a fresh name must also
    differ from existing binders.
    """
    found: set[str] = set()
    seen: set[int] = set()  # a shared subtree only needs one visit
    todo = [term]
    while todo:
        node = todo.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        match node:
            case Var(name):
                found.add(name)
            case Lam(name, body):
                found.add(name)
                todo.append(body)
            case App(fn, arg):
                todo += [fn, arg]
    return frozenset(found)


########################################################################
# Capture-avoiding substitution.

def substitute(term: Term, name: str, replacement: Term) -> Term:
    """Return term[name := replacement] without capturing any free name.

    Only free occurrences of `name` are replaced, so substitution stops at a
    binder for `name`. A binder is renamed only if `name` occurs free beneath
    it and the binder's own name is free in the replacement. The renaming
    obeys the same scope rules, so occurrences that belong to an inner binder
    of the same name are left alone.

    A renamed binder y becomes the first of y_1, y_2, ... (see FreshNames)
    not used anywhere in `term` or `replacement`, not equal to `name`, and
    not generated earlier in this call. If `name` is not free in `term`,
    `term` itself is returned. Neither input is changed.
    """
    _check_name(name)
    _check_term(term, "the term")
    _check_term(replacement, "the replacement")
    if name not in term.fv:
        return term
    return _substitute_all(term, {name: replacement})


def _substitute_all(term: Term, subst: Mapping[str, Term]) -> Term:
    """Apply a simultaneous substitution, which may also carry renamings.

    Renaming binder y to y_1 just adds y := y_1 to the substitution for the
    binder's body. One walk thus performs both the requested substitution
    and every renaming it causes, each respecting inner shadowing.
    """
    supply: FreshNames | None = None

    def fresh(base: str) -> str:
        nonlocal supply
        if supply is None:  # only built if some binder really must be renamed
            used = set(all_names(term)) | set(subst)
            for replacement in subst.values():
                used |= all_names(replacement)
            supply = FreshNames(used)
        return supply.fresh(base)

    done: list[Term] = []
    todo: list[tuple] = [("visit", term, subst)]
    while todo:
        task = todo.pop()
        if task[0] == "app":
            arg = done.pop()
            done.append(App(done.pop(), arg))
            continue
        if task[0] == "lam":
            done.append(Lam(task[1], done.pop()))
            continue
        _, node, pending = task
        # Keep only the entries that can change this subtree.
        if any(key not in node.fv for key in pending):
            pending = {key: r for key, r in pending.items() if key in node.fv}
        if not pending:
            done.append(node)
            continue
        match node:
            case Var(var):
                done.append(pending[var])
            case App(fn, arg):
                todo += [("app",), ("visit", arg, pending), ("visit", fn, pending)]
            case Lam(binder, body):
                # The binder is not free in node, so it is not a key here.
                if any(binder in r.fv for r in pending.values()):
                    renamed = fresh(binder)
                    pending = {**pending, binder: Var(renamed)}
                    binder = renamed
                todo += [("lam", binder), ("visit", body, pending)]
    return done.pop()


########################################################################
# Alpha-equivalence.

def alpha_equivalent(left: Term, right: Term) -> bool:
    """Whether two terms differ at most in the names of bound variables.

    Each bound occurrence must refer to a binder at the same position, and
    free names must match exactly. This is not beta or eta equivalence.
    """
    todo = [(left, right, {}, {}, 0)]
    while todo:
        a, b, binders_a, binders_b, depth = todo.pop()
        match a, b:
            case Var(x), Var(y):
                level_a, level_b = binders_a.get(x), binders_b.get(y)
                if level_a != level_b or (level_a is None and x != y):
                    return False
            case Lam(x, body_a), Lam(y, body_b):
                todo.append((body_a, body_b, {**binders_a, x: depth},
                             {**binders_b, y: depth}, depth + 1))
            case App(fn_a, arg_a), App(fn_b, arg_b):
                todo.append((fn_a, fn_b, binders_a, binders_b, depth))
                todo.append((arg_a, arg_b, binders_a, binders_b, depth))
            case _:
                return False
    return True
