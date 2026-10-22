"""Expected kinds and the strict data comparison used to check results."""
import unittest

from MySolution.results import (
    BOOL, NAT, PairKind, format_data, has_kind, same_data,
)


class KindTests(unittest.TestCase):
    def test_booleans_are_not_naturals(self):
        self.assertTrue(has_kind(NAT, 0))
        self.assertTrue(has_kind(BOOL, False))
        self.assertFalse(has_kind(NAT, True))
        self.assertFalse(has_kind(BOOL, 1))
        self.assertFalse(has_kind(NAT, -1))

    def test_nested_pair_kind(self):
        kind = PairKind(PairKind(NAT, BOOL), NAT)
        self.assertTrue(has_kind(kind, ((2, True), 3)))
        self.assertFalse(has_kind(kind, ((2, 1), 3)))
        self.assertFalse(has_kind(kind, (2, True)))
        self.assertEqual(str(kind), "((natural, boolean), natural)")

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(TypeError):
            has_kind("natural", 3)


class DataTests(unittest.TestCase):
    def test_same_data_keeps_one_and_true_apart(self):
        self.assertTrue(1 == True)  # the trap that same_data avoids
        self.assertFalse(same_data(1, True))
        self.assertFalse(same_data((0, 1), (False, 1)))
        self.assertTrue(same_data(((2, True), 3), ((2, True), 3)))

    def test_format_data(self):
        self.assertEqual(format_data(((2, True), 3)), "((2, true), 3)")
        self.assertEqual(format_data(False), "false")
        self.assertEqual(format_data(0), "0")


if __name__ == "__main__":
    unittest.main()
