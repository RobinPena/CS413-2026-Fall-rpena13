"""The identifier rule and the deterministic fresh-name supply."""
import unittest

from MySolution.names import FreshNames, is_identifier


class IdentifierTests(unittest.TestCase):
    def test_valid_and_invalid_identifiers(self):
        for name in ("x", "_", "y_1", "Loop2", "_tmp"):
            with self.subTest(name):
                self.assertTrue(is_identifier(name))
        for name in ("", "1x", "x-y", "lam x", "x.", "é"):
            with self.subTest(name):
                self.assertFalse(is_identifier(name))


class FreshNamesTests(unittest.TestCase):
    def test_first_suffix_when_unused(self):
        self.assertEqual(FreshNames(set()).fresh("y"), "y_1")

    def test_skips_names_already_used(self):
        self.assertEqual(FreshNames({"y", "y_1", "y_2"}).fresh("y"), "y_3")

    def test_never_repeats_a_generated_name(self):
        supply = FreshNames({"y"})
        self.assertEqual([supply.fresh("y") for _ in range(3)],
                         ["y_1", "y_2", "y_3"])

    def test_suffix_is_added_to_the_whole_base(self):
        self.assertEqual(FreshNames({"y_1"}).fresh("y_1"), "y_1_1")

    def test_independent_supplies_agree(self):
        # No global counter: a second supply with the same seed starts over.
        first, second = FreshNames({"u"}), FreshNames({"u"})
        first.fresh("u")
        self.assertEqual(second.fresh("u"), "u_1")

    def test_generated_names_are_identifiers(self):
        supply = FreshNames({"s", "s_1"})
        self.assertTrue(all(is_identifier(supply.fresh(b)) for b in ("s", "_", "Z")))


if __name__ == "__main__":
    unittest.main()
