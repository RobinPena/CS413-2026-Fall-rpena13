"""Restricted reader: turns constructor-expression text into a d0exp.

Only LAMBDA expression constructors with literal arguments are accepted.
The text is parsed with `ast` and walked by hand; it is never passed to
eval/exec, so uploaded Python code cannot run.
"""
import ast

from lambda_web.backend import lambda1 as L


class ReadError(ValueError):
    """The source is not a well-formed constructor expression."""

    def __init__(self, message: str, line: int | None = None):
        self.line = line
        super().__init__(f"line {line}: {message}" if line else message)


# Argument kinds: "exp" nested d0exp, "var" variable name,
# "name" operator name, "int" integer literal, "bool" boolean literal.
_SCHEMA: dict[str, tuple[type, tuple[str, ...]]] = {
    "D0Eint":  (L.D0Eint,  ("int",)),
    "D0Ebtf":  (L.D0Ebtf,  ("bool",)),
    "D0Eop1":  (L.D0Eop1,  ("name", "exp")),
    "D0Eop2":  (L.D0Eop2,  ("name", "exp", "exp")),
    "D0Evar":  (L.D0Evar,  ("var",)),
    "D0Elam":  (L.D0Elam,  ("var", "exp")),
    "D0Efix":  (L.D0Efix,  ("var", "var", "exp")),
    "D0Eapp":  (L.D0Eapp,  ("exp", "exp")),
    "D0Eif0":  (L.D0Eif0,  ("exp", "exp", "exp")),
    "D0Elet":  (L.D0Elet,  ("var", "exp", "exp")),
    "D0Epair": (L.D0Epair, ("exp", "exp")),
    "D0Epfst": (L.D0Epfst, ("exp",)),
    "D0Epsnd": (L.D0Epsnd, ("exp",)),
}

_KIND_TEXT = {
    "int": "an integer literal",
    "bool": "True or False",
    "var": "a non-empty variable name string",
    "name": "a non-empty operator name string",
}


def read_d0exp(source: str) -> L.D0E000:
    """Parse `source` into a d0exp, or raise ReadError.

    The source is wrapped in parentheses before parsing. Python rejects an
    expression that starts indented ("unexpected indent"), which is common
    when code is pasted or written below a comment; inside parentheses
    indentation is ignored. The wrapper adds one line at the top, so
    reported line numbers are shifted back by `_line`. Wrapping cannot let
    code run: the tree is only walked, and anything that escapes the
    parentheses is not a constructor call and is rejected.
    """
    try:
        tree = ast.parse("(\n" + source + "\n)", mode="eval")
        return _build(tree.body)
    except SyntaxError as e:
        raise ReadError(f"syntax error: {e.msg}", _line(e.lineno)) from None
    except (RecursionError, MemoryError):
        raise ReadError("expression is nested too deeply") from None


def _line(lineno: int | None) -> int | None:
    """Map a line number in the wrapped text back to the user's source."""
    return max(lineno - 1, 1) if lineno else None


def _build(node: ast.expr) -> L.D0E000:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        raise ReadError("expected a constructor call such as D0Eint(1)",
                        _line(node.lineno))
    ctor = node.func.id
    if ctor not in _SCHEMA:
        raise ReadError(f"unknown constructor {ctor!r}", _line(node.lineno))
    if node.keywords:
        raise ReadError(f"{ctor}: keyword arguments are not supported",
                        _line(node.lineno))
    cls, kinds = _SCHEMA[ctor]
    if len(node.args) != len(kinds):
        raise ReadError(f"{ctor} takes {len(kinds)} argument(s), "
                        f"got {len(node.args)}", _line(node.lineno))
    args = [_arg(ctor, pos, kind, arg)
            for pos, (kind, arg) in enumerate(zip(kinds, node.args), 1)]
    return cls(*args)


def _arg(ctor: str, pos: int, kind: str, node: ast.expr):
    if kind == "exp":
        return _build(node)
    value = _literal(node)
    match kind:
        case "int":
            ok = type(value) is int
        case "bool":
            ok = type(value) is bool
        case _:
            ok = type(value) is str and value != ""
    if not ok:
        raise ReadError(f"{ctor} argument {pos}: expected {_KIND_TEXT[kind]}",
                        _line(node.lineno))
    return value


def _literal(node: ast.expr):
    """Value of a plain literal (including negative ints), else None."""
    if isinstance(node, ast.Constant):
        return node.value
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and type(node.operand.value) is int):
        return -node.operand.value
    return None
