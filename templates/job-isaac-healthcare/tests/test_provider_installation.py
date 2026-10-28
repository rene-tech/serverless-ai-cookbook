"""Exact source/dependency checks must precede provider scientific execution."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROVIDER = Path(__file__).resolve().parents[1] / "provider/run_bundle.py"
SPEC = importlib.util.spec_from_file_location("provider_bundle_tests", PROVIDER)
BUNDLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE)


class InstallationChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.source = self.root / "owned.py"
        self.source.write_text("# installed execution source\n")
        self.contract = {"schema": "isaac-healthcare-runtime-source-contract/v1",
                         "portable_image": "example.invalid/isaac@sha256:" + "a" * 64,
                         "files": {str(self.source): {"owner": "installed-test-source",
                             "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()}}}
        self.store()
        (self.root / "distributions.json").write_text(json.dumps({"distributions": {"owned-dependency": {"version": "2.3"}}}))
        self.sources = patch.object(BUNDLE, "CODE", self.root)
        self.sources.start()
        self.addCleanup(self.sources.stop)
        self.packages = patch.object(BUNDLE.importlib.metadata, "distributions",
                                     return_value=[SimpleNamespace(metadata={"Name": "owned_dependency"}, version="2.3")])
        self.packages.start()
        self.addCleanup(self.packages.stop)
        self.verify = patch.object(BUNDLE.subprocess, "run")
        self.runtime = self.verify.start()
        self.addCleanup(self.verify.stop)

    def store(self):
        (self.root / "runtime-sources.json").write_text(json.dumps(self.contract))

    def test_exact_sources_and_versions_emit_reusable_receipt(self):
        result = BUNDLE.verify_installation(self.output)
        self.assertEqual(result["source_check"], "passed")
        self.assertEqual(result["files_verified"], 1)
        self.assertEqual(result["distribution_count"], 1)
        self.assertEqual(result, json.loads((self.output / "installed-source-check.json").read_bytes()))
        self.runtime.assert_called_once_with([BUNDLE.PYTHON, "-I", "/opt/isaac-healthcare/scripts/verify_runtime.py"], check=True)

    def test_changed_runtime_source_fails_before_runtime_or_science(self):
        self.source.write_text("# unexpected replacement\n")
        with self.assertRaisesRegex(RuntimeError, "Installed runtime source differs"):
            BUNDLE.verify_installation(self.output)
        self.runtime.assert_not_called()
        self.assertFalse((self.output / "installed-source-check.json").exists())

    def test_missing_runtime_source_does_not_become_optional(self):
        self.source.unlink()
        with self.assertRaisesRegex(RuntimeError, "Required runtime source is unavailable"):
            BUNDLE.verify_installation(self.output)
        self.runtime.assert_not_called()

    def test_source_ownership_is_required(self):
        self.contract["files"][str(self.source)]["owner"] = ""
        self.store()
        with self.assertRaisesRegex(RuntimeError, "declared owner"):
            BUNDLE.verify_installation(self.output)
        self.runtime.assert_not_called()

    def test_relative_source_is_rejected(self):
        self.contract["files"] = {"owned.py": {"owner": "source", "sha256": "a" * 64}}
        self.store()
        with self.assertRaisesRegex(RuntimeError, "absolute path"):
            BUNDLE.verify_installation(self.output)
        self.runtime.assert_not_called()

    def test_dependency_version_drift_is_not_ignored(self):
        (self.root / "distributions.json").write_text(json.dumps({"distributions": {"owned-dependency": {"version": "2.4"}}}))
        with self.assertRaisesRegex(RuntimeError, "package versions differ"):
            BUNDLE.verify_installation(self.output)
        self.runtime.assert_not_called()

    def test_failing_runtime_verifier_never_emits_success(self):
        self.runtime.side_effect = subprocess.CalledProcessError(1, "verify_runtime.py")
        with self.assertRaises(subprocess.CalledProcessError):
            BUNDLE.verify_installation(self.output)
        self.assertFalse((self.output / "installed-source-check.json").exists())

    def test_ordinary_path_calls_verifier_before_parsing_input(self):
        with patch.dict(BUNDLE.os.environ, ISAAC_PROVIDER_INPUT=str(self.root / "missing-input"),
                        ISAAC_PROVIDER_OUTPUT=str(self.output)):
            with patch.object(BUNDLE, "verify_installation", side_effect=RuntimeError("source guard first")) as verify:
                with self.assertRaisesRegex(RuntimeError, "source guard first"):
                    BUNDLE.run()
                verify.assert_called_once_with(self.output)


if __name__ == "__main__":
    unittest.main()
