"""Focused proc permission guards; actual process proof is retained separately."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from i4h_interactive import isolation


class ProcRuntimeGuards(unittest.TestCase):
    def test_standard_readonly_controls_are_required_individually(self):
        controls = tuple("/proc/" + name for name in ("bus", "fs", "irq", "sys", "sysrq-trigger"))
        for unsafe in controls:
            with self.subTest(unsafe=unsafe):
                def statvfs(path, unsafe=unsafe):
                    self.assertIn(str(path), controls)
                    return SimpleNamespace(f_flag=0 if str(path) == unsafe else os.ST_RDONLY)

                with patch.object(isolation.os, "statvfs", side_effect=statvfs):
                    with self.assertRaisesRegex(RuntimeError, unsafe):
                        isolation.proc_runtime_write_rule()

    def test_proc_rule_has_no_general_write_or_device_flag(self):
        with patch.object(isolation.os, "statvfs", return_value=SimpleNamespace(f_flag=os.ST_RDONLY)):
            self.assertEqual(isolation.proc_runtime_write_rule(), {"path": "/proc", "proc_runtime_write": True})

    def test_both_controller_and_child_rule_builder_contains_one_precise_proc_rule(self):
        with patch.object(isolation.os, "statvfs", return_value=SimpleNamespace(f_flag=os.ST_RDONLY)):
            rules = isolation.runtime_rules([])
        self.assertEqual([rule for rule in rules if rule.get("proc_runtime_write")],
                         [{"path": "/proc", "proc_runtime_write": True}])
        self.assertFalse(any(rule.get("write") or rule.get("device") for rule in rules))

    def test_nonproc_path_cannot_request_proc_permissions(self):
        with self.assertRaisesRegex(ValueError, "exact procfs root"):
            isolation.restrict([{"path": "/tmp", "proc_runtime_write": True}])

    def test_proc_permissions_cannot_be_combined_with_broader_rule_types(self):
        for flag in ("write", "directory_only", "device"):
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, "exact procfs root"):
                isolation.restrict([{"path": "/proc", "proc_runtime_write": True, flag: True}])

    def test_mount_guard_is_rechecked_before_rule_application(self):
        with patch.object(isolation.os, "statvfs", return_value=SimpleNamespace(f_flag=0)):
            with self.assertRaisesRegex(RuntimeError, "global proc control mount"):
                isolation.restrict([{"path": "/proc", "proc_runtime_write": True}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
