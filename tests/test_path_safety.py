"""Containment tests for resolve_within.

Deliberately free of both the MCP SDK and the game data, so a fresh checkout can
run them. Save and building names come straight from MCP tool arguments, so this
is the boundary between caller-controlled strings and the filesystem.
"""

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from paths import resolve_within


class ResolveWithinTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.base = self.root / "media_soviet" / "save"
        (self.base / "autosave1").mkdir(parents=True)
        (self.base / "autosave1" / "stats.ini").write_text("[stats]\n")
        # A file outside the base that an attacker would want to reach.
        (self.root / "secret.ini").write_text("password=hunter2\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_accepts_a_normal_save_name(self):
        got = resolve_within(self.base, "autosave1", "stats.ini")

        self.assertEqual(got, (self.base / "autosave1" / "stats.ini").resolve())

    def test_accepts_a_nested_name(self):
        (self.base / "campaign" / "run2").mkdir(parents=True)

        got = resolve_within(self.base, "campaign/run2", "stats.ini")

        self.assertEqual(got, (self.base / "campaign" / "run2" / "stats.ini").resolve())

    def test_rejects_parent_traversal(self):
        self.assertIsNone(resolve_within(self.base, "../..", "secret.ini"))
        self.assertIsNone(resolve_within(self.base, "../../secret.ini"))
        self.assertIsNone(resolve_within(self.base, "autosave1/../../..", "secret.ini"))

    def test_rejects_absolute_paths(self):
        # joinpath() silently discards the base when handed an absolute path.
        self.assertIsNone(resolve_within(self.base, "/etc/passwd"))
        self.assertIsNone(resolve_within(self.base, str(self.root / "secret.ini")))

    def test_rejects_symlink_pointing_outside(self):
        link = self.base / "escape"
        try:
            link.symlink_to(self.root)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this platform")

        self.assertIsNone(resolve_within(self.base, "escape", "secret.ini"))

    def test_rejects_empty_and_missing_parts(self):
        self.assertIsNone(resolve_within(self.base))
        self.assertIsNone(resolve_within(self.base, ""))
        self.assertIsNone(resolve_within(self.base, "autosave1", ""))

    def test_rejects_null_bytes(self):
        self.assertIsNone(resolve_within(self.base, "autosave1\x00/../../etc"))

    def test_containment_does_not_require_existence(self):
        # A name may legitimately point at a save that is not there yet; the
        # check is about location, and existence is the caller's business.
        got = resolve_within(self.base, "not_yet", "stats.ini")

        self.assertIsNotNone(got)
        self.assertFalse(got.exists())

    def test_base_itself_is_inside_base(self):
        self.assertIsNotNone(resolve_within(self.base, "."))


if __name__ == "__main__":
    unittest.main()
