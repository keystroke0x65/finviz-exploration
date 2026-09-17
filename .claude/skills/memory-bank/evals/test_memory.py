"""Unit tests for scripts/. Run: python3 -m unittest evals/test_memory.py  (from the skill root)."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import memory  # noqa: E402
from lib.store import FileStore  # noqa: E402


class Bank(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.bank = self.tmp / "memory-bank"
        self.run_cli("init", str(self.tmp))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = memory.main(["--bank", str(self.bank), *argv] if argv[0] != "init" else list(argv))
        return code, buf.getvalue()

    def apply(self, batch, *flags):
        p = self.tmp / "ops.json"
        p.write_text(json.dumps(batch))
        return self.run_cli("apply", str(p), *flags)

    def text(self, rel):
        return (self.bank / rel).read_text()

    def seed(self):
        return self.apply({"operations": [
            {"op": "ADD_ROOT", "file": "experience/deploy.md", "section": "Lessons", "ref": "r",
             "content": "Run database migrations before deploying the web app to avoid schema drift errors", "labels": ["deploy"]},
            {"op": "ADD_DELTA", "parent": "@r", "when": "preview deployments",
             "content": "point migrations at the branch database created for the preview, not main"},
        ]})


class TestOps(Bank):
    def test_init_creates_structure(self):
        for rel in ["index.md", "active-context.md", "progress.md", "context/decisions.md", ".state.json"]:
            self.assertTrue((self.bank / rel).exists(), rel)

    def test_add_root_and_delta(self):
        code, out = self.seed()
        self.assertEqual(code, 0, out)
        t = self.text("experience/deploy.md")
        self.assertIn("[deploy-0001] root", t)
        self.assertIn('  - [deploy-0001.1] delta', t)

    def test_atomic_batch_on_error(self):
        code, out = self.apply({"operations": [
            {"op": "ADD_ROOT", "file": "experience/x-files.md", "section": "Lessons", "content": "a valid lesson about caching layers"},
            {"op": "ADD_DELTA", "parent": "nope-0001", "when": "w", "content": "this parent does not exist anywhere"},
        ]})
        self.assertEqual(code, 1)
        self.assertFalse((self.bank / "experience/x-files.md").exists())

    def test_duplicate_rejected(self):
        self.seed()
        code, out = self.apply({"operations": [{"op": "ADD_ROOT", "file": "experience/deploy.md", "section": "Lessons",
                                                "content": "Run database migrations before deploying the web app to avoid schema drift"}]})
        self.assertEqual(code, 1)
        self.assertIn("near-duplicate", out)

    def test_secret_rejected(self):
        code, out = self.apply({"operations": [{"op": "ADD_ROOT", "file": "context/tech-stack.md", "section": "Dev environment",
                                                "content": "DATABASE_URL=postgres://admin:hunter2secret@db.example.com/app"}]})
        self.assertEqual(code, 1)
        self.assertIn("secret", out)

    def test_feedback_update_supersede_delete(self):
        self.seed()
        code, out = self.apply({"feedback": [{"id": "deploy-0001", "tag": "helpful"}], "operations": [
            {"op": "UPDATE", "id": "deploy-0001.1", "when": "Vercel preview deployments", "reason": "narrower condition"},
            {"op": "ADD_ROOT", "file": "context/decisions.md", "section": "Decisions", "ref": "d",
             "content": "Chose Drizzle over Prisma because edge runtime support matters for Neon"},
        ]})
        self.assertEqual(code, 0, out)
        self.assertIn("h=1", self.text("experience/deploy.md"))
        code, out = self.apply({"operations": [
            {"op": "SUPERSEDE", "id": "dec-0001", "reason": "switched ORM",
             "content": "Chose Prisma Accelerate over Drizzle because the team standardised on Prisma"}]})
        self.assertEqual(code, 0, out)
        self.assertIn("supersedes=dec-0001", self.text("context/decisions.md"))
        self.assertIn("dec-0001", self.text("history/archive.md"))
        code, out = self.apply({"operations": [{"op": "DELETE", "id": "deploy-0001", "reason": "no longer deploy this way"}]})
        self.assertEqual(code, 0, out)
        self.assertNotIn("deploy-0001", self.text("experience/deploy.md"))
        self.assertIn("deploy-0001.1", self.text("history/archive.md"))

    def test_ids_never_reused_after_delete(self):
        self.seed()
        self.apply({"operations": [{"op": "DELETE", "id": "deploy-0001", "reason": "test"}]})
        self.apply({"operations": [{"op": "ADD_ROOT", "file": "experience/deploy.md", "section": "Lessons",
                                    "content": "Tag releases in git before triggering the production deploy"}]})
        self.assertIn("deploy-0002", self.text("experience/deploy.md"))

    def test_promote_and_consolidate(self):
        self.seed()
        for _ in range(3):
            self.apply({"feedback": [{"id": "deploy-0001.1", "tag": "helpful"}]})
        code, out = self.run_cli("consolidate")
        self.assertIn("deploy-0001.1", out)
        code, out = self.apply({"operations": [{"op": "PROMOTE", "id": "deploy-0001.1",
                                                "content": "For preview deployments, run migrations against the preview branch database before deploying"}]})
        self.assertEqual(code, 0, out)
        t = self.text("experience/deploy.md")
        self.assertIn("from=deploy-0001.1", t)
        self.assertNotIn("[deploy-0001.1]", t)

    def test_harmful_excluded_from_find(self):
        self.seed()
        for _ in range(2):
            self.apply({"feedback": [{"id": "deploy-0001.1", "tag": "harmful"}]})
        code, out = self.run_cli("find", "preview", "migrations")
        self.assertNotIn("deploy-0001.1", out)
        code, out = self.run_cli("find", "preview", "migrations", "--include-harmful")
        self.assertIn("deploy-0001.1", out)

    def test_rollback(self):
        self.seed()
        before = self.text("experience/deploy.md")
        self.apply({"operations": [{"op": "DELETE", "id": "deploy-0001", "reason": "oops"}]})
        code, out = self.run_cli("rollback")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.text("experience/deploy.md"), before)

    def test_validate_catches_hand_edits(self):
        self.seed()
        p = self.bank / "experience/deploy.md"
        p.write_text(p.read_text() + "- [deploy-0009.4] delta h=0 x=0 when=\"x\" :: orphan written by hand\n- [broken line\n")
        code, out = self.run_cli("validate")
        self.assertEqual(code, 1)
        self.assertIn("orphan", out)

    def test_dry_run_writes_nothing(self):
        code, out = self.apply({"operations": [{"op": "ADD_ROOT", "file": "progress.md", "section": "Next",
                                                "content": "Add rate limiting to the public share endpoint"}]}, "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertNotIn("prog-0001", self.text("progress.md"))


if __name__ == "__main__":
    unittest.main()
