"""CPU checks for exact support restoration; no provider or science execution."""
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch


PROVIDER = Path(__file__).resolve().parents[1] / "provider"


def load(name):
    spec = importlib.util.spec_from_file_location("test_" + name, PROVIDER / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load("prepare_job")
bootstrap = load("bootstrap")


class Restore(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="support-test-")
        self.directory = Path(self.temp.name)
        self.roots = []

    def tearDown(self):
        for root in self.roots:
            if root.exists():
                shutil.rmtree(root)
        self.temp.cleanup()

    def bundle(self, args=()):
        # Distinct data is an ordinary input variation, never an eligibility gate.
        contents = {"transfer.py": b"# shared transfer\n", "run_bundle.py": b"# portable wrapper\n",
                    "runtime-sources.json": json.dumps({"arbitrary": self.temp.name}).encode(),
                    "command.json": json.dumps(["/python", "-I", "/opt/isaac-task/run_bundle.py", *args]).encode()}
        restored, packed, manifest = prepare.pack_support(contents)
        self.roots.append(Path(manifest["root"]))
        return contents, restored, packed, manifest

    def save(self, packed, manifest):
        payload, metadata = self.directory / "payload.gz", self.directory / "payload.json"
        payload.write_bytes(packed)
        metadata.write_text(json.dumps(manifest))
        return metadata, payload

    def test_exact_bytes_private_modes_and_no_reuse(self):
        original, restored, packed, manifest = self.bundle()
        metadata, payload = self.save(packed, manifest)
        root, _ = bootstrap.restore(metadata, payload)
        self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
        for name, value in restored.items():
            self.assertEqual((root / name).read_bytes(), value)
            self.assertEqual((root / name).stat().st_uid, os.geteuid())
            self.assertEqual(stat.S_IMODE((root / name).stat().st_mode), 0o600)
            if name != "command.json":
                self.assertEqual(value, original[name])
        with self.assertRaises(FileExistsError):
            bootstrap.restore(metadata, payload)

    def test_deterministic_pack_and_ordinary_argv_variations(self):
        for args in (("--duration", "73", "--cameras", "false"),
                     ("--duration", "180", "--project", "different-scene.tar")):
            original, restored, packed, manifest = self.bundle(args)
            self.assertEqual(prepare.pack_support(original), (restored, packed, manifest))
            actual = json.loads(restored["command.json"])
            self.assertEqual(actual[:2], ["/python", "-I"])
            self.assertEqual(actual[2], manifest["root"] + "/run_bundle.py")
            self.assertEqual(actual[3:], list(args))

    def test_corruption_and_bad_member_hash_rejected_before_restore(self):
        _, _, packed, manifest = self.bundle()
        for bad_payload, bad_manifest in ((packed[:-1] + bytes([packed[-1] ^ 1]), manifest),
                                         (packed, {**manifest, "files": {**manifest["files"],
                                          "transfer.py": {**manifest["files"]["transfer.py"], "sha256": "0" * 64}}})):
            metadata, payload = self.save(bad_payload, bad_manifest)
            with self.assertRaises(ValueError):
                bootstrap.restore(metadata, payload)
            self.assertFalse(Path(manifest["root"]).exists())

    def test_traversal_and_symlink_members_rejected(self):
        _, restored, _, manifest = self.bundle()
        for name, link in (("../escape", False), ("transfer.py", True)):
            source = io.BytesIO()
            with tarfile.open(fileobj=source, mode="w:", format=tarfile.USTAR_FORMAT) as archive:
                for filename, value in sorted(restored.items()):
                    member = tarfile.TarInfo(name if filename == "transfer.py" else filename)
                    member.mode, member.size = 0o600, len(value)
                    if filename == "transfer.py" and link:
                        member.type, member.linkname, member.size = tarfile.SYMTYPE, "/outside", 0
                    archive.addfile(member, None if member.issym() else io.BytesIO(value))
            raw = source.getvalue(); packed = gzip.compress(raw, mtime=0)
            value = {**manifest, "compressed": {"sha256": hashlib.sha256(packed).hexdigest(), "size_bytes": len(packed)},
                     "archive": {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}}
            metadata, payload = self.save(packed, value)
            with self.assertRaises(ValueError):
                bootstrap.restore(metadata, payload)
            self.assertFalse(Path(manifest["root"]).exists())

    def test_launch_preserves_interpreter_and_verifies_command(self):
        _, _, packed, manifest = self.bundle()
        metadata, payload = self.save(packed, manifest)
        transfer = self.directory / "transfer.json"
        transfer.write_text(json.dumps({"command_sha256": manifest["files"]["command.json"]["sha256"]}))
        with patch.object(bootstrap.os, "execv") as execute:
            bootstrap.launch(metadata, payload, transfer)
        argv = execute.call_args.args[1]
        self.assertEqual(execute.call_args.args[0], bootstrap.sys.executable)
        self.assertEqual(argv, [bootstrap.sys.executable, "-I", manifest["root"] + "/transfer.py",
                               "--config", str(transfer.resolve()), "--command", manifest["root"] + "/command.json"])

    def test_bad_command_binding_never_executes(self):
        _, _, packed, manifest = self.bundle()
        metadata, payload = self.save(packed, manifest)
        transfer = self.directory / "transfer.json"
        transfer.write_text(json.dumps({"command_sha256": "0" * 64}))
        with patch.object(bootstrap.os, "execv") as execute:
            with self.assertRaises(ValueError):
                bootstrap.launch(metadata, payload, transfer)
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
