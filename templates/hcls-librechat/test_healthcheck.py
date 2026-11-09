import errno
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location('workbench_health', Path(__file__).with_name('healthcheck.py'))
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class WorkspaceReadiness(unittest.TestCase):
    def response(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        return response

    def test_readable_workspace_passes_without_writes(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            'SCIENTIFIC_REQUIRE_PERSISTENT_STATE': 'true', 'SCIENTIFIC_WORKSPACE': root,
        }), patch.object(health, 'urlopen', return_value=self.response()):
            health.check()
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_disconnected_mount_fails_despite_healthy_api(self):
        with patch.dict(os.environ, {'SCIENTIFIC_REQUIRE_PERSISTENT_STATE': 'true'}), \
                patch.object(health, 'urlopen', return_value=self.response()), \
                patch.object(health.os, 'scandir', side_effect=OSError(errno.ENOTCONN, 'Transport endpoint is not connected')):
            with self.assertRaises(OSError) as result:
                health.check()
            self.assertEqual(result.exception.errno, errno.ENOTCONN)

    def test_api_failure_is_not_hidden_by_workspace(self):
        with patch.object(health, 'urlopen', side_effect=TimeoutError('API timed out')):
            with self.assertRaises(TimeoutError):
                health.check()


if __name__ == '__main__':
    unittest.main()
