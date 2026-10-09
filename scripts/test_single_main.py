import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SOURCE = Path(__file__).with_name("single_main.py")
spec = importlib.util.spec_from_file_location("single_main", SOURCE)
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="scientific-main-test-")
        self.base = Path(self.temp.name)
        self.repo = self.base / "source"
        self.repo.mkdir()
        workflow.git(self.repo, "init", "-b", "main")
        workflow.git(self.repo, "config", "user.name", "Workflow Test")
        workflow.git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / ".scientific-ai-workflow.json").write_text(json.dumps({"personal_repository": "rene-tech/test"}))
        (self.repo / "file.txt").write_text("initial\n")
        hooks = self.repo / ".githooks"
        scripts = self.repo / "scripts"
        hooks.mkdir()
        scripts.mkdir()
        shutil.copy2(SOURCE, scripts / "single_main.py")
        for name in ["pre-push", "reference-transaction"]:
            hook = hooks / name
            hook.write_text('#!/usr/bin/env python3\nfrom pathlib import Path\nimport runpy,sys\nsys.argv.insert(1,"hook-'+name+'")\nrunpy.run_path(str(Path(__file__).resolve().parents[1]/"scripts"/"single_main.py"),run_name="__main__")\n')
            hook.chmod(0o755)
        workflow.git(self.repo, "add", ".")
        workflow.git(self.repo, "commit", "-m", "initial")
        workflow.git(self.repo, "config", "scientificai.singlemain", "true")
        workflow.git(self.repo, "config", "core.hooksPath", str(hooks))
        self.initial = workflow.value(self.repo, "rev-parse", "main")

    def tearDown(self):
        self.temp.cleanup()

    def task(self):
        task = self.base / "task"
        workflow.git(self.repo, "worktree", "add", "--detach", str(task), "main")
        (task / "file.txt").write_text("task\n")
        workflow.git(task, "add", "file.txt")
        workflow.git(task, "commit", "-m", "task")
        sha = workflow.value(task, "rev-parse", "HEAD")
        evidence = self.base / "checks.json"
        evidence.write_text(json.dumps({"commit": sha, "checks": [{"command": "actual-test-command", "exit_code": 0}]}))
        return task, evidence, sha

    def test_git_itself_rejects_branch_creation_but_allows_remote_tracking_refs(self):
        result = workflow.git(self.repo, "branch", "agent/leak", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Persistent task branches are disabled", result.stderr)
        self.assertEqual(workflow.value(self.repo, "for-each-ref", "--format=%(refname)", "refs/heads"), "refs/heads/main")
        workflow.git(self.repo, "update-ref", "refs/remotes/test/archive", self.initial)

    def test_fast_forward_updates_main_files_and_preserves_detached_task(self):
        task, evidence, sha = self.task()
        self.assertEqual(workflow.integrate(self.repo, task, evidence, False), sha)
        self.assertEqual(workflow.value(self.repo, "rev-parse", "main"), sha)
        self.assertEqual((self.repo / "file.txt").read_text(), "task\n")
        self.assertNotEqual(workflow.git(task, "symbolic-ref", "-q", "HEAD", check=False).returncode, 0)
        self.assertEqual(workflow.value(self.repo, "for-each-ref", "--format=%(refname)", "refs/heads"), "refs/heads/main")

    def test_stale_main_cannot_be_overwritten(self):
        task, evidence, sha = self.task()
        (self.repo / "sibling.txt").write_text("sibling\n")
        workflow.git(self.repo, "add", "sibling.txt")
        workflow.git(self.repo, "commit", "-m", "sibling")
        current = workflow.value(self.repo, "rev-parse", "main")
        with self.assertRaisesRegex(ValueError, "Main moved"):
            workflow.integrate(self.repo, task, evidence, False)
        self.assertEqual(workflow.value(self.repo, "rev-parse", "main"), current)
        self.assertEqual((self.repo / "file.txt").read_text(), "initial\n")

    def test_dirty_task_and_stale_evidence_cannot_modify_main(self):
        task, evidence, sha = self.task()
        (task / "keep.txt").write_text("dirty\n")
        with self.assertRaisesRegex(ValueError, "dirty files"):
            workflow.integrate(self.repo, task, evidence, False)
        (task / "keep.txt").unlink()
        evidence.write_text(json.dumps({"commit": self.initial, "checks": [{"command": "test", "exit_code": 0}]}))
        with self.assertRaisesRegex(ValueError, "exact commit"):
            workflow.integrate(self.repo, task, evidence, False)
        self.assertEqual(workflow.value(self.repo, "rev-parse", "main"), self.initial)

    def test_push_guards_reject_upstream_task_branches_and_main_deletion(self):
        task, evidence, sha = self.task()
        workflow.integrate(self.repo, task, evidence, False)
        url = "https://github.com/rene-tech/test.git"
        workflow.pre_push(self.repo, url, [f"refs/heads/main {sha} refs/heads/main {self.initial}"])
        for target_url, row in [
            ("https://github.com/nebius/test.git", f"refs/heads/main {sha} refs/heads/main {self.initial}"),
            (url, f"HEAD {sha} refs/heads/agent/leak {'0'*40}"),
            (url, f"(delete) {'0'*40} refs/heads/main {sha}"),
            (url, f"HEAD {self.initial} refs/heads/main {sha}"),
        ]:
            with self.assertRaises(ValueError):
                workflow.pre_push(self.repo, target_url, [row])

    def test_a_second_integrator_cannot_acquire_the_main_lock(self):
        task, evidence, sha = self.task()
        with (workflow.common(self.repo) / "scientificai-main.lock").open("a+") as lock:
            workflow.fcntl.flock(lock, workflow.fcntl.LOCK_EX | workflow.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                workflow.integrate(self.repo, task, evidence, False)
        self.assertEqual(workflow.value(self.repo, "rev-parse", "main"), self.initial)


if __name__ == "__main__":
    unittest.main()
