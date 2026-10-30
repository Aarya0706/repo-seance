import shutil
import tempfile
import unittest
from pathlib import Path

from seance.demo import build_demo_repo
from seance.gitscan import GitError, interleave, summon
from seance.prompts import canned


class SeanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.repo = build_demo_repo(cls.tmp / "haunted")
        cls.found = summon(cls.repo, stale_days=180)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_deleted_files(self):
        names = {g.name for g in self.found["file"]}
        self.assertEqual(names, {"legacy/cobol_bridge.py", "auth_v1.py"})
        cobol = next(g for g in self.found["file"] if "cobol" in g.name)
        self.assertEqual(cobol.author, "Cara Lindqvist")
        self.assertIn("lived", cobol.detail)

    def test_stale_branches(self):
        by = {g.name: g for g in self.found["branch"]}
        self.assertIn("feature/auth-v2", by)
        self.assertEqual(by["feature/auth-v2"].detail, "never merged")
        self.assertIn("hotfix/friday-deploy", by)
        self.assertNotIn("main", by)

    def test_todos_are_blamed(self):
        todos = self.found["todo"]
        self.assertTrue(any("handle refunds" in g.epitaph and g.author == "Ben Okafor" for g in todos))
        self.assertTrue(any("HACK" in g.epitaph for g in todos))

    def test_regrettable_commits(self):
        msgs = {g.epitaph for g in self.found["commit"]}
        self.assertTrue({"wip", "fix later", "asdf", "final2"} <= msgs)

    def test_author_filter_and_interleave(self):
        picked = interleave(self.found, ["file", "branch", "todo", "commit"], 20, author="cara")
        self.assertTrue(picked and all("cara" in g.author.lower() for g in picked))
        kinds = [g.kind for g in interleave(self.found, ["file", "branch"], 4)]
        self.assertEqual(kinds[:2], ["file", "branch"])

    def test_canned_never_crashes(self):
        for mode in ("haunt", "ofrenda", "exorcise"):
            for kind, ghosts in self.found.items():
                for g in ghosts:
                    if mode == "exorcise" and kind not in ("branch", "todo"):
                        continue
                    self.assertTrue(canned(mode, g))

    def test_not_a_repo(self):
        with self.assertRaises(GitError):
            summon(Path(tempfile.gettempdir()) / "definitely-not-a-repo-xyz")


if __name__ == "__main__":
    unittest.main()
