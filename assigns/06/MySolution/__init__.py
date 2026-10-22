"""Lambda Arcade: compile extended LAMBDA into pure lambda calculus (CS413 Assign06).

Run commands from assigns/06 so that `MySolution` resolves to this package.
"""
import sys

# The supplied lambda1_vp.py uses `type` statements, so older interpreters fail
# with a SyntaxError deep inside the import. Say what is wrong up front instead.
if sys.version_info < (3, 12):
    raise ImportError(
        "MySolution needs Python 3.12 or later; this is Python "
        + sys.version.split()[0])
