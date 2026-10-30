import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from seance import cli
from seance.demo import build_demo_repo
from seance.gitscan import summon
from seance.prompts import facts
from seance.verify import check


class VerifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.repo = build_demo_repo(cls.tmp / "haunted")
        cls.found = summon(cls.repo)
        cls.authors = {g.author for gs in cls.found.values() for g in gs}
        cls.merged = next(g for g in cls.found["branch"] if g.name == "hotfix/friday-deploy")
        cls.unmerged = next(g for g in cls.found["branch"] if g.name == "feature/auth-v2")
        cls.deleted = next(g for g in cls.found["file"] if g.name == "auth_v1.py")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def chk(self, text, g, mode="haunt"):
        return check(text, g, facts(g), mode, self.authors)

    def test_clean_text_passes(self):
        g = self.merged
        t = f"{g.name} sleeps, merged long ago but never buried. Ben Okafor left it {g.age_days // 30} months back."
        self.assertEqual(self.chk(t, g), [])

    def test_merge_contradictions(self):
        self.assertTrue(self.chk("The merge failed and the branch lingers.", self.merged))
        self.assertTrue(self.chk("It was merged into main in the end.", self.unmerged))
        self.assertEqual(self.chk("It was never merged, and it never will be.", self.unmerged), [])

    def test_invented_numbers_hashes_dates(self):
        g = self.deleted
        self.assertTrue(self.chk("Gone only two weeks ago.", g))
        self.assertTrue(self.chk("Killed by commit deadbee1.", g))
        self.assertTrue(self.chk("It died in 1999.", g))
        self.assertTrue(self.chk("It died in the month of March.", g) or g.died.strftime("%B") == "March")
        sha = g.detail.split("deleted in ")[1][:7]
        self.assertEqual(self.chk(f"Deleted in {sha} after 600 days of service.", g), [])

    def test_digit_soup_gibberish_and_vague_durations(self):
        g = self.unmerged
        soup = f"{g.name} 2026/06/18 04:00:00 4 123 2 1 1 2 1 2 3 1 1 2 1 2 3"
        self.assertTrue(self.chk(soup, g))
        self.assertTrue(self.chk("It carries a1a2ab3c4d5e6f7g8h9i0j1k and 12345678901234567890123.", g))
        self.assertTrue(self.chk("Gone for a year now.", self.deleted))
        self.assertTrue(self.chk("It was last touched on 2020-01-01.", g))
        self.assertTrue(self.chk("It holds 283 items.", g))

    def test_may_the_verb_is_not_a_month(self):
        g = self.unmerged
        self.assertEqual(self.chk("May it rest well, never merged.", g), [])

    def test_exact_date_copied_from_facts_passes(self):
        g = self.unmerged
        d = g.died.strftime("%Y-%m-%d")
        self.assertEqual(self.chk(f"Last touched on {d}, never merged.", g), [])

    def test_canned_whispers_pass_their_own_verifier(self):
        from seance.prompts import canned
        for kind, ghosts in self.found.items():
            for g in ghosts:
                for mode in ("haunt", "ofrenda"):
                    self.assertEqual(self.chk(canned(mode, g), g, mode), [], (mode, g.name))

    def test_wrong_person(self):
        self.assertTrue(self.chk("Ana left this behind.", self.merged))

    def test_exorcise_needs_verdict(self):
        self.assertTrue(self.chk("Delete it.", self.unmerged, "exorcise"))
        self.assertEqual(self.chk("VERDICT: INVESTIGATE. Never merged.", self.unmerged, "exorcise"), [])


class FakeMedium:
    replies = []
    calls = 0

    def __init__(self, *a, **k):
        pass

    def check(self):
        return True, "fake"

    def channel(self, system, prompt, max_tokens=140, temperature=0.9):
        FakeMedium.calls += 1
        r = FakeMedium.replies
        return r[(FakeMedium.calls - 1) % len(r)]


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.repo = build_demo_repo(cls.tmp / "haunted")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_cli(self, replies, *extra):
        FakeMedium.replies, FakeMedium.calls = replies, 0
        out = self.tmp / "stats.json"
        with mock.patch.object(cli, "Medium", FakeMedium), redirect_stdout(io.StringIO()):
            rc = cli.main([str(self.repo), "-n", "2", "--stats-json", str(out), *extra])
        self.assertEqual(rc, 0)
        return json.loads(out.read_text(encoding="utf-8"))

    def test_no_verify_flags_but_keeps_text(self):
        d = self.run_cli(["It was merged at deadbee1 in 1999."])
        self.assertEqual(d["summary"]["first_try_flagged"], 2)
        self.assertEqual(d["summary"]["final_flagged"], 2)
        self.assertEqual(d["summary"]["fell_back"], 0)

    def test_verify_retries_then_succeeds(self):
        d = self.run_cli(["It was merged at deadbee1 in 1999.", "Something stirs in the dark."], "--verify")
        self.assertEqual(d["summary"]["first_try_flagged"], 2)
        self.assertEqual(d["summary"]["regenerated"], 2)
        self.assertEqual(d["summary"]["final_flagged"], 0)

    def test_verify_falls_back_to_canned(self):
        d = self.run_cli(["It was merged at deadbee1 in 1999."], "--verify", "--retries", "1")
        self.assertEqual(d["summary"]["fell_back"], 2)
        self.assertTrue(all(g["fell_back"] and g["attempts"] == 2 for g in d["ghosts"]))


if __name__ == "__main__":
    unittest.main()
