import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import install
from scripts.build_standalone import unpack


class StandaloneTests(unittest.TestCase):
    def test_recovery_command_uses_executable_without_python(self):
        executable = str(Path('C:/Папка с пробелами/dangbei-setup.exe'))
        folder = Path('backup with spaces/копия')
        with patch.object(install.sys, 'frozen', True, create=True), \
                patch.object(install.sys, 'executable', executable):
            result = install.restore_command('192.0.2.1:5555', folder)
        args = [executable, '--device', '192.0.2.1:5555', 'restore', str(folder)]
        if os.name == 'nt':
            self.assertEqual(result, subprocess.list2cmdline(args))
        else:
            self.assertEqual(shlex.split(result), args)
        self.assertNotIn('install.py', result)

    def test_adb_does_not_inherit_frozen_python_libraries(self):
        with patch.object(install.sys, 'frozen', True, create=True), \
                patch.dict(os.environ, {'LD_LIBRARY_PATH': '/frozen', 'LD_LIBRARY_PATH_ORIG': '/system'}, clear=True):
            self.assertEqual(install.external_env(), {'LD_LIBRARY_PATH': '/system'})
            self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/frozen')

    def test_archive_cannot_escape_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            archive = folder / 'test.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('../outside', 'unexpected')
            with self.assertRaises(ValueError):
                unpack(archive, folder / 'extracted')
            self.assertFalse((folder / 'outside').exists())


if __name__ == '__main__':
    unittest.main()
