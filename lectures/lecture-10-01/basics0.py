########################################################################
# Requires Python 3.12 or later.
from abc import ABC
from dataclasses import dataclass
########################################################################
#
@dataclass
class fnoptn[T](ABC):
    pass
@dataclass
class fnoptn_nil[T](fnoptn[T]):
    pass
@dataclass
class fnoptn_cons[T](fnoptn[T]):
    arg1: T
    pass
#
########################################################################
#
@dataclass
class fnlist[T](ABC):
    pass
@dataclass
class fnlist_nil[T](fnlist[T]):
    pass
@dataclass
class fnlist_cons[T](fnlist[T]):
    arg1: T
    arg2: fnlist[T]
    pass
#
########################################################################

def fnlist_reverse[T](items: fnlist[T]) -> fnlist[T]:
    result = fnlist_nil()
    while isinstance(items, fnlist_cons):
        result = fnlist_cons(items.arg1, result)
        items = items.arg2
    return result

########################################################################
