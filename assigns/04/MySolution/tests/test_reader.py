"""Restricted constructor reader: accepts LAMBDA constructors only and
never executes the input."""
import pytest

from lambda_web.backend import lambda1 as L
from lambda_web.backend.reader import ReadError, read_d0exp
from tests.programs import fact

V, I = L.D0Evar, L.D0Eint


@pytest.mark.parametrize("source, expected", [
    ('D0Eint(-7)', I(-7)),
    ('D0Ebtf(False)', L.D0Ebtf(False)),
    ('D0Eop1("-1", D0Eint(3))', L.D0Eop1("-1", I(3))),
    ('D0Eop2("+", D0Eint(1), D0Eint(2))', L.D0Eop2("+", I(1), I(2))),
    ('D0Evar("x")', V("x")),
    ('D0Elam("x", D0Evar("x"))', L.D0Elam("x", V("x"))),
    ('D0Efix("f", "x", D0Evar("x"))', L.D0Efix("f", "x", V("x"))),
    ('D0Eapp(D0Evar("f"), D0Eint(1))', L.D0Eapp(V("f"), I(1))),
    ('D0Eif0(D0Ebtf(True), D0Eint(1), D0Eint(2))',
     L.D0Eif0(L.D0Ebtf(True), I(1), I(2))),
    ('D0Elet("x", D0Eint(1), D0Evar("x"))', L.D0Elet("x", I(1), V("x"))),
    ('D0Epair(D0Eint(1), D0Eint(2))', L.D0Epair(I(1), I(2))),
    ('D0Epfst(D0Evar("p"))', L.D0Epfst(V("p"))),
    ('D0Epsnd(D0Evar("p"))', L.D0Epsnd(V("p"))),
])
def test_reads_every_constructor(source, expected):
    assert read_d0exp(source) == expected


def test_accepts_comments_multiline_and_indentation():
    assert read_d0exp("  # leading comment\n    D0Eint(7)  # trailing\n") \
        == I(7)
    assert isinstance(read_d0exp(fact(5)), L.D0Eapp)


@pytest.mark.parametrize("source, fragment", [
    ('__import__("os").system("echo hacked")', "constructor call"),
    ('D0Eint.__class__', "constructor call"),
    ('D0Eint(1), D0Eint(2)', "constructor call"),
    ('D0Eint(1)) + (D0Eint(2)', "constructor call"),
    ('D0Eexec("rm -rf /")', "unknown constructor"),
    ('D0Eint("x")', "integer literal"),
    ('D0Eint(True)', "integer literal"),
    ('D0Ebtf(1)', "True or False"),
    ('D0Evar(x)', "variable name"),
    ('D0Eop2("+", D0Eint(1))', "takes 3 argument"),
    ('D0Eint(arg1=1)', "keyword"),
    ('D0Eint(', "syntax error"),
    ('D0Epfst(' * 1000 + 'D0Eint(1)' + ')' * 1000, "syntax error"),
])
def test_rejects_non_constructor_input(source, fragment):
    with pytest.raises(ReadError, match=fragment):
        read_d0exp(source)


def test_rejected_code_is_never_executed(tmp_path):
    marker = tmp_path / "pwned"
    with pytest.raises(ReadError):
        read_d0exp(f'__import__("pathlib").Path({str(marker)!r}).touch()')
    assert not marker.exists()


def test_error_reports_user_line_number():
    with pytest.raises(ReadError) as err:
        read_d0exp('D0Eop2("+",\n  D0Eint(1),\n  D0Eint(2.5))')
    assert err.value.line == 3
