"""CPU tests of the real RSL child boundary; no simulator or policy is run."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BOOT = load("child_bootstrap_test", HERE / "child_bootstrap.py")
BRIDGE = load("child_bridge_test", HERE / "bridge.py")


class KitArguments(unittest.TestCase):
    def test_non_owned_arguments_and_spaces_preserved(self):
        args = ["trainer", "--enable", "my.extension", "--/custom/path=a b", "agent.seed=983"]
        self.assertEqual(BOOT.portable_arguments(args, "/work/my private kit"),
                         [*args, "--portable-root", "/work/my private kit"])
        self.assertEqual(len(args), 5)

    def test_equivalent_owned_roots_collapse_without_changing_other_values(self):
        args = ["eval", "--portable-root=/work/kit", "--other", "x", "--portable-root", "/work/kit"]
        self.assertEqual(BOOT.portable_arguments(args, "/work/kit"),
                         ["eval", "--other", "x", "--portable-root", "/work/kit"])

    def test_conflicting_roots_are_actionable(self):
        for args in (["--portable-root=/shared"], ["--portable-root", "/shared"], ["--portable-root="]):
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, "conflicts"):
                BOOT.portable_arguments(args, "/work/owned")

    def test_missing_root_argument_is_actionable(self):
        for args in (["--portable-root"], ["--portable-root", "--enable"]):
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, "requires"):
                BOOT.portable_arguments(args, "/work/owned")

    def test_late_launcher_hook_observes_resolved_custom_kit_args(self):
        observed = []

        class Launcher:
            def _create_app(self):
                observed.append(list(sys.argv))
                return "upstream-return"

        original = Launcher._create_app
        with tempfile.TemporaryDirectory() as temporary, patch.object(sys, "argv", ["trainer"]):
            receipt = Path(temporary) / "startup.jsonl"
            BOOT.install_kit_root(Launcher, temporary, receipt)
            sys.argv += ["--enable", "authored.extension"]
            self.assertEqual(Launcher()._create_app(), "upstream-return")
            self.assertEqual(observed, [["trainer", "--enable", "authored.extension", "--portable-root", temporary]])
            self.assertIs(Launcher._create_app.__wrapped__, original)
            self.assertEqual(json.loads(receipt.read_text())["kit_argv"], observed[0])

    def test_conflict_never_calls_simulator(self):
        class Launcher:
            def _create_app(self):
                raise AssertionError("A conflicting root reached the simulator")

        with tempfile.TemporaryDirectory() as temporary, patch.object(sys, "argv", ["eval", "--portable-root=/foreign"]):
            receipt = Path(temporary) / "startup.jsonl"
            BOOT.install_kit_root(Launcher, temporary, receipt)
            with self.assertRaisesRegex(ValueError, "conflicts"):
                Launcher()._create_app()
            self.assertFalse(receipt.exists())


class ScopedBackend(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = []
        self.original = SimpleNamespace(call=lambda *a, **kw: self.calls.append((a, kw)) or 17)
        self.request = {"output_dir": str(self.root), "sdk_root": str(self.root),
                        "input_dir": str(self.root), "python_paths": []}
        self.processes = BRIDGE.PortableRslProcesses(self.original, self.request)
        self.env = {"ISAAC_HEALTHCARE_KIT_ROOT": str(self.root / "kit")}

    def test_original_interpreter_science_args_environment_and_exit_preserved(self):
        command = ["/independent/env/bin/python", "trainer.py", "--num_envs", "8", "agent.seed=712", "a=b c"]
        self.assertEqual(self.processes.call(command, cwd=self.root, env=self.env), 17)
        (actual,), kwargs = self.calls[0]
        self.assertEqual(actual[0], command[0])
        self.assertEqual(actual[actual.index("--") + 1:], command[1:])
        self.assertIs(kwargs["env"], self.env)
        self.assertEqual(kwargs["cwd"], self.root)
        context = json.loads((self.root / "training-child-context-0001.json").read_bytes())
        self.assertEqual(context["upstream_argv"], command)

    def test_shell_empty_and_missing_private_root_fail_before_process(self):
        for command, kwargs in [(["python", "task.py"], {"shell": True, "env": self.env}),
                                ([], {"env": self.env}), (["python", "task.py"], {"env": {}})]:
            with self.subTest(command=command, kwargs=kwargs), self.assertRaises(ValueError):
                self.processes.call(command, **kwargs)
        self.assertEqual(self.calls, [])

    def test_scoped_cli_does_not_modify_module_globals_or_subprocess(self):
        namespace = {"subprocess": self.original}
        exec("def launch(command, env):\n return subprocess.call(command, env=env)\n", namespace)
        backend = SimpleNamespace(subprocess=self.original, launch=namespace["launch"])
        load_backend = lambda name: backend
        cli_globals = {"load_backend": load_backend}
        exec("def launch(name, command, env):\n return load_backend(name).launch(command, env)\n", cli_globals)
        command = [sys.executable, "-m", "authored.evaluator", "--episodes", "2"]
        self.assertEqual(BRIDGE.portable_rl_call(cli_globals["launch"], backend, self.request,
                                               "rsl_rl", command, self.env), 17)
        self.assertIs(namespace["subprocess"], self.original)
        self.assertIs(cli_globals["load_backend"], load_backend)
        self.assertIs(backend.launch, namespace["launch"])
        self.assertIsNot(subprocess.call, self.original.call)
        self.assertEqual(BRIDGE.portable_rl_call(cli_globals["launch"], backend, self.request,
                                               "external", command, self.env), 17)
        self.assertEqual(self.calls[-1][0][0], command)


@unittest.skipUnless(importlib.util.find_spec("isaac_healthcare_runtime"), "requires installed portable Arena CPU environment")
class ActualChildProcesses(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        if destination := os.environ.get("I4H_CPU_PROBE_EVIDENCE"):
            self.addCleanup(shutil.copytree, self.root, Path(destination) / self._testMethodName)
        self.env = {**os.environ, "ISAAC_HEALTHCARE_KIT_ROOT": str(self.root / "private kit"), "HEADLESS": "1"}
        self.request = {"output_dir": str(self.root), "sdk_root": "/opt/i4h", "input_dir": str(self.root),
                        "python_paths": [str(self.root)]}

    def call(self, target):
        with (self.root / "child.log").open("w") as log:
            result = BRIDGE.PortableRslProcesses(subprocess, self.request).call(
                [sys.executable, *target], env=self.env, cwd="/opt/i4h", stdout=log, stderr=subprocess.STDOUT)
        return result

    def test_actual_script_imports_local_assets_and_preserves_exit(self):
        probe = self.root / "independent_probe.py"
        probe.write_text("""import json, os, sys
from pathlib import Path
from i4h_arena.assets import constants
from isaaclab.app import AppLauncher
assert constants.PANDA_USD.startswith('/opt/i4h-assets/')
assert Path(constants.PANDA_USD).is_file()
assert constants.FRANKA_PANDA_HAND_USD.startswith('/opt/i4h-assets/')
assert Path(constants.FRANKA_PANDA_HAND_USD).is_file()
assert AppLauncher._create_app._i4h_portable_root == os.environ['ISAAC_HEALTHCARE_KIT_ROOT']
assert sys.argv[1:] == ['--non-owned', 'two words', 'agent.seed=712']
print(json.dumps({'assets_local':True,'kit_hook_ready':True,'scientific_execution':False}))
raise SystemExit(23)
""")
        self.assertEqual(self.call([str(probe), "--non-owned", "two words", "agent.seed=712"]), 23,
                         (self.root / "child.log").read_text())
        receipt = json.loads((self.root / "training-child-startup-0001.jsonl").read_text())
        self.assertEqual(receipt["phase"], "bootstrap_prepared")
        self.assertIn("PANDA_USD", receipt["localized_constants"])

    def test_actual_upstream_training_help_reaches_owning_parser(self):
        script = "/opt/i4h/third_party/IsaacLab-ffff603/scripts/reinforcement_learning/rsl_rl/train.py"
        self.assertEqual(self.call([script, "--help"]), 0, (self.root / "child.log").read_text())
        self.assertIn("--max_iterations", (self.root / "child.log").read_text())
        self.assertIn("bootstrap_prepared", (self.root / "training-child-startup-0001.jsonl").read_text())

    def test_actual_upstream_evaluation_export_help_reaches_module_parser(self):
        self.assertEqual(self.call(["-m", "i4h_rl.rsl_rl_eval", "--help"]), 0,
                         (self.root / "child.log").read_text())
        text = (self.root / "child.log").read_text()
        self.assertIn("--export-policy", text)
        self.assertIn("--checkpoint", text)


if __name__ == "__main__":
    unittest.main()
