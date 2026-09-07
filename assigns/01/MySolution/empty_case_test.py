"""
Test type: EMPTY CASE

Rationale:
"Empty" input here means literally providing no board data at all -- a
zero-length tuple instead of the expected 8-element board. Two entry
points into the program are exercised:

  (a) print_board(()) -- print_board indexes bd[0] through bd[7]
      directly, so an empty tuple fails on the very first access.
  (b) search((), 0, 0, 0) -- the empty board survives the very first
      safety check (safety_test2 short-circuits to True when there is no
      previous row to compare against), but fails as soon as board_set
      tries to place the first queen and unpack the (empty) tuple into
      8 names.

Expected result:
Both calls should raise an error rather than silently returning a result,
since there is no valid board state an empty tuple could represent.
  (a) IndexError from print_board's direct bd[0] access.
  (b) ValueError from board_set's tuple-unpacking.
"""
import eqp_solution as eqp


def run():
    all_ok = True

    print("=== EMPTY CASE (a): print_board(()) ===")
    try:
        eqp.print_board(())
        print("Expected: IndexError (tuple index out of range)")
        print("Actual:   no exception raised")
        print("Result:   FAIL")
        all_ok = False
    except IndexError as e:
        print("Expected: IndexError (tuple index out of range)")
        print(f"Actual:   IndexError: {e}")
        print("Result:   PASS")
    except Exception as e:  # noqa: BLE001
        print(f"Actual:   unexpected {type(e).__name__}: {e}")
        print("Result:   FAIL")
        all_ok = False
    print()

    print("=== EMPTY CASE (b): search((), 0, 0, 0) ===")
    try:
        eqp.search((), 0, 0, 0)
        print("Expected: ValueError (not enough values to unpack)")
        print("Actual:   no exception raised")
        print("Result:   FAIL")
        all_ok = False
    except ValueError as e:
        print("Expected: ValueError (not enough values to unpack)")
        print(f"Actual:   ValueError: {e}")
        print("Result:   PASS")
    except Exception as e:  # noqa: BLE001
        print(f"Actual:   unexpected {type(e).__name__}: {e}")
        print("Result:   FAIL")
        all_ok = False

    return all_ok


if __name__ == "__main__":
    run()
