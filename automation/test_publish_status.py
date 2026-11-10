"""Tests for the website poller's done-vs-needs-input decision.

Run:  python -m unittest automation/test_publish_status.py   (from the website folder)

Uses throwaway git repos (a bare "origin" + a clone) so git_publish_evidence is
exercised against real commits/pushes, not mocked output.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poll_and_publish_website as poller


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class PublishStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        origin, work = root / "origin.git", root / "work"
        git(root, "init", "--bare", "-b", "main", str(origin))
        git(root, "clone", str(origin), str(work))
        git(work, "config", "user.email", "t@example.com")
        git(work, "config", "user.name", "t")
        git(work, "checkout", "-b", "master")
        (work / "a.txt").write_text("1")
        git(work, "add", ".")
        git(work, "commit", "-m", "base")
        git(work, "push", "origin", "master:main")
        git(work, "fetch", "origin")
        self.work = work
        self._old_root = poller.PROJECT_ROOT
        poller.PROJECT_ROOT = work
        self.before = poller.git_head()

    def tearDown(self):
        poller.PROJECT_ROOT = self._old_root
        self.tmp.cleanup()

    def commit(self):
        (self.work / "article.html").write_text("new")
        git(self.work, "add", ".")
        git(self.work, "commit", "-m", "article")

    def classify(self, is_error=False):
        committed, pushed, _ = poller.git_publish_evidence(self.before)
        return poller.classify_run(is_error, committed, pushed)[0]

    def test_success_report_goes_to_done(self):
        # Committed + pushed; the agent's wording is irrelevant (and may even
        # mention a question about another file).
        self.commit()
        git(self.work, "push", "origin", "master:main")
        self.assertEqual(self.classify(), "success")

    def test_question_goes_to_needs_input(self):
        # Agent stopped to ask something: no commit was made.
        self.assertEqual(self.classify(), "flagged")

    def test_failed_push_goes_to_needs_input(self):
        self.commit()  # committed locally, never pushed
        self.assertEqual(self.classify(), "flagged")

    def test_pushed_run_that_asks_a_question_needs_input_with_reason(self):
        self.commit()
        git(self.work, "push", "origin", "master:main")
        committed, pushed, _ = poller.git_publish_evidence(self.before)
        text = ("The article is live at https://thebutlerrealty.com/community-news/x. "
                "Should I also publish the spending-cap article?")
        status, needs_input, reason = poller.decide_run(False, committed, pushed, text)
        self.assertEqual(status, "success")  # it did publish
        self.assertTrue(needs_input)
        self.assertIn("Should I also publish the spending-cap article?", reason)

    def test_pushed_run_that_offers_options_needs_input(self):
        self.commit()
        git(self.work, "push", "origin", "master:main")
        committed, pushed, _ = poller.git_publish_evidence(self.before)
        text = "Published. One thing needs your call: the second article is unpublished."
        _, needs_input, reason = poller.decide_run(False, committed, pushed, text)
        self.assertTrue(needs_input)
        self.assertIn("needs your call", reason)

    def test_clean_success_report_stays_done(self):
        self.commit()
        git(self.work, "push", "origin", "master:main")
        committed, pushed, _ = poller.git_publish_evidence(self.before)
        text = ("The article is live. It was committed as `fc48173` and pushed to `main`. "
                "Files changed: the new page, the index card, sitemap.xml and llms.txt.")
        self.assertEqual(poller.decide_run(False, committed, pushed, text)[:2], ("success", False))

    def test_errored_run_goes_to_needs_input(self):
        self.commit()
        git(self.work, "push", "origin", "master:main")
        self.assertEqual(self.classify(is_error=True), "error")


if __name__ == "__main__":
    unittest.main()
