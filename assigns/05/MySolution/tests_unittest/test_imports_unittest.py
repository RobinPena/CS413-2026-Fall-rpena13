"""The solution module loads the supplied interpreter from the assignment directory."""
import unittest
from pathlib import Path

import lambda1_visitors  # puts the assignment directory on sys.path
import lambda1_vp

ASSIGN_DIR = Path(__file__).resolve().parents[2]


class ImportTests(unittest.TestCase):
    def test_supplied_module_comes_from_assignment_directory(self):
        self.assertEqual(Path(lambda1_vp.__file__).resolve(),
                         ASSIGN_DIR / "lambda1_vp.py")

    def test_reexported_classes_are_the_supplied_classes(self):
        self.assertIs(lambda1_visitors.D0Eint, lambda1_vp.D0Eint)
        self.assertIs(lambda1_visitors.D0ExpVisitor, lambda1_vp.D0ExpVisitor)


if __name__ == "__main__":
    unittest.main()
