import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install as app


class FakeADB:
    """Stateful device double: fail on unexpected commands, retain actual APK bytes."""
    device = 'test-device'

    def __init__(self, manifest, payload, backup_root):
        self.manifest, self.payload, self.backup_root = manifest, payload, backup_root
        self.calls, self.mutations = [], []
        self.process_protection = set()
        self.fail_pull = False
        self.bad_pull = False
        self.fail_install = False
        self.home_value = app.STOCK_HOMES[0] + '/.Home'
        self.settings = {ns + '/' + key: None for ns, key in app.SETTINGS}
        self.settings.update({'secure/enabled_accessibility_services': 'existing/.Service',
                              'secure/accessibility_enabled': '1',
                              'secure/default_input_method': app.SOGOU,
                              'secure/enabled_input_methods': app.SOGOU,
                              'system/system_locales': 'zh-CN'})
        self.props = {'ro.product.model': 'DBX5 Ultra', 'ro.product.model_number': 'X5U6128',
                      'ro.product.device': 'mt5879', 'ro.build.version.sdk': '30',
                      'ro.build.version.incremental': '3764', 'ro.serialno': 'FAKE-SERIAL',
                      'ro.build.fingerprint': 'test/firmware', 'pm.dexopt.install': 'speed-profile'}
        self.packages, self.data = {}, {}
        for pkg in app.ORIGINALS:
            path = '/system/' + pkg + '.apk'
            self.data[path] = ('original:' + pkg).encode()
            self.packages[pkg] = {'installed': True, 'paths': [path],
                'version_code': manifest['compatibility']['native_versions'].get(pkg, 1),
                'enabled': 0, 'permissions': {}, 'appops': {}}
        self.tables = {t: ([{'typeID': '1', 'name': '设置'}] if 'settings' in t else
                          [{app.TABLES[t]: 'dblauncher://mineapp', 'modeID': '1', 'name': '我的应用'}])
                       for t in app.TABLES}

    def mutate(self, what):
        # Any first device write requires a completed backup whose files validate.
        backups = list(self.backup_root.glob('*/backup.json'))
        if not backups:
            raise AssertionError('Mutation before backup: ' + str(what))
        for file in backups:
            if json.loads(file.read_text(encoding='utf-8'))['complete']:
                app.validate_backup(file.parent, self.manifest, app.identity(self))
                break
        else:
            raise AssertionError('Mutation before verified backup: ' + str(what))
        self.mutations.append(what)

    def setting(self, ns, key):
        return self.settings.get(ns + '/' + key)

    def put(self, ns, key, value):
        self.mutate(('setting', ns, key, value))
        self.settings[ns + '/' + key] = value

    def package(self, pkg):
        return copy.deepcopy(self.packages.get(pkg, {'installed': False}))

    def home(self):
        return self.home_value

    def install(self, paths, downgrade=False):
        self.mutate(('install', [str(p) for p in paths]))
        if self.fail_install:
            raise app.Error('Simulated install failure')
        # Match release files, or the package directory in a restore backup.
        item = next((p for p in self.manifest['packages'] if p['file'] == paths[0].name), None)
        pkg = item['package'] if item else paths[0].parent.name
        info = self.packages.get(pkg, {'enabled': 0, 'permissions': {}, 'appops': {}})
        info.update(installed=True, version_code=item['version_code'] if item else 1, paths=[])
        for i, path in enumerate(paths):
            remote = '/data/' + pkg + '/' + str(i) + '.apk'
            self.data[remote] = path.read_bytes()
            info['paths'].append(remote)
        self.packages[pkg] = info

    def run(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == 'pull':
            if self.fail_pull:
                raise app.Error('Pull failed')
            Path(args[2]).write_bytes(b'corrupt' if self.bad_pull else self.data[args[1]])
            return '1 file pulled'
        if args[0] == 'uninstall':
            self.mutate(args)
            self.packages.pop(args[1], None)
            return 'Success'
        raise AssertionError(args)

    def shell(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == 'getprop':
            return self.props.get(args[1], '')
        if args[0] == 'sha256sum':
            return hashlib.sha256(self.data[args[1]]).hexdigest() + '  ' + args[1]
        if args[:2] == ('content', 'query'):
            if app.PROCESS_PROTECT_URI in args:
                return '\n'.join('Row: %d appPackageName=%s' % (i, pkg)
                                 for i, pkg in enumerate(sorted(self.process_protection))) or 'No result found.'
            table = args[args.index('--uri') + 1].split('/')[-1]
            return '\n'.join('Row: ' + str(i) + ' ' + ', '.join(k + '=' + v for k, v in row.items())
                             for i, row in enumerate(self.tables[table]))
        if args[:2] == ('dumpsys', 'accessibility'):
            return 'Bound services:{Service[label=Боковая панель на русском]}'
        if args[:2] == ('ime', 'list'):
            return '\n'.join([app.KEYBOARD, app.SOGOU, app.VOICE_IME])
        if args[0] == 'setprop':
            self.mutate(args)
            self.props[args[1]] = args[2]
        elif args[0] == 'content' and app.PROCESS_PROTECT_URI in args:
            self.mutate(args)
            if args[1] == 'insert':
                pkg = next(a.split(':', 2)[2] for a in args if a.startswith('appPackageName:s:'))
                self.process_protection.add(pkg)
            elif args[1] == 'delete':
                self.process_protection.discard(args[-1].split("'")[1])
            else:
                raise AssertionError(args)
        elif args[:2] == ('content', 'update'):
            self.mutate(args)
            table = args[args.index('--uri') + 1].split('/')[-1]
            name = args[args.index('--bind') + 1].split(':', 2)[2]
            for row in self.tables[table]:
                row['name'] = name
        elif args[:3] == ('cmd', 'package', 'set-home-activity'):
            self.mutate(args)
            self.home_value = args[-1]
        elif args[:3] == ('cmd', 'appops', 'set'):
            self.mutate(args)
            self.packages[args[-3]]['appops'][args[-2]] = args[-1]
        elif args[0] == 'pm':
            self.mutate(args)
            values = {'default-state': 0, 'enable': 1, 'disable': 2,
                      'disable-user': 3, 'disable-until-used': 4}
            self.packages[args[-1]]['enabled'] = values[args[1]]
        elif args[0] == 'ime':
            self.mutate(args)
            if args[1] == 'set':
                self.settings['secure/default_input_method'] = args[-1]
        elif args[0] == 'am' and args[1] in ['start', 'force-stop']:
            self.mutate(args)
        elif args[:2] == ('am', 'broadcast'):
            self.mutate(args)
            return 'Broadcast completed: result=1'
        else:
            raise AssertionError(args)
        return ''


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload, self.backups = self.root / 'apks', self.root / 'backups'
        self.payload.mkdir()
        self.manifest = json.loads((app.ROOT / 'manifest.json').read_text(encoding='utf-8'))
        for package in self.manifest['packages']:
            for asset in app.assets(package):
                path = self.payload / asset['file']
                path.write_bytes(('payload:' + path.name).encode())
                asset['sha256'], asset['bytes'] = app.digest(path), path.stat().st_size
        self.adb = FakeADB(self.manifest, self.payload, self.backups)
        self.addCleanup(patch.stopall)
        patch('builtins.print').start()
        patch('install.time.sleep', return_value=None).start()

    def install(self, **kwargs):
        return app.install(self.adb, self.manifest, self.payload, self.backups, **kwargs)

    def test_full_install_backup_first_and_restore(self):
        before = copy.deepcopy(self.adb.settings)
        tables = copy.deepcopy(self.adb.tables)
        folder = self.install(google=True)
        self.assertEqual(self.adb.home_value, app.HOME)
        self.assertEqual(self.adb.settings['secure/enabled_accessibility_services'],
                         'existing/.Service:' + app.REMOTE)
        self.assertTrue(self.adb.package('com.android.vending')['installed'])
        self.assertEqual(len(self.adb.package('com.android.vending')['paths']), 3)
        self.assertEqual(self.adb.package(app.STOCK_CAST)['enabled'], 3)
        self.assertTrue(self.adb.package(app.RUSSIAN_CAST)['installed'])
        app.restore(self.adb, self.manifest, folder)
        self.assertEqual(self.adb.settings, before)
        self.assertEqual(self.adb.tables, tables)
        self.assertFalse(self.adb.package('com.dangbei.launcher3')['installed'])
        self.assertFalse(self.adb.package('com.android.vending')['installed'])
        self.assertEqual(self.adb.package(app.STOCK_CAST)['enabled'], 0)
        self.assertFalse(self.adb.package(app.RUSSIAN_CAST)['installed'])

    def test_google_only_keeps_launcher_labels_and_ime(self):
        original = (self.adb.home_value, copy.deepcopy(self.adb.settings), copy.deepcopy(self.adb.tables))
        folder = self.install(google=True, ui=False, keyboard=False)
        self.assertEqual((self.adb.home_value, self.adb.settings, self.adb.tables), original)
        self.assertFalse(self.adb.package('com.dangbei.launcher3')['installed'])
        self.assertEqual(self.adb.package(app.STOCK_CAST)['enabled'], 0)
        self.assertFalse(self.adb.package(app.RUSSIAN_CAST)['installed'])
        app.restore(self.adb, self.manifest, folder)
        self.assertEqual((self.adb.home_value, self.adb.settings, self.adb.tables), original)

    def test_google_protection_backup_restore_preserves_other_entries(self):
        self.adb.process_protection = {'com.google.android.gms', 'example.player'}
        folder = self.install(google=True, ui=False, keyboard=False)
        self.assertEqual(self.adb.process_protection,
                         {'com.google.android.gms', 'com.google.android.gsf', 'example.player'})
        state = json.loads((folder / 'backup.json').read_text())
        self.assertEqual(state['google_process_protection'],
                         {'com.google.android.gms': True, 'com.google.android.gsf': False})
        self.adb.process_protection.add('example.added.later')
        app.restore(self.adb, self.manifest, folder)
        self.assertEqual(self.adb.process_protection,
                         {'com.google.android.gms', 'example.player', 'example.added.later'})

    def test_no_keyboard_keeps_user_choice(self):
        self.install(keyboard=False)
        self.assertEqual(self.adb.setting('secure', 'default_input_method'), app.SOGOU)
        self.assertFalse(self.adb.package(KEYBOARD_PACKAGE)['installed'])

    def test_youtube_only_backup_install_and_restore(self):
        original = copy.deepcopy(self.adb.settings)
        home = self.adb.home_value
        folder = self.install(youtube=True, ui=False, keyboard=False)
        self.assertEqual(self.adb.home_value, home)
        self.assertEqual(self.adb.setting('secure', 'default_input_method'), app.SOGOU)
        self.assertTrue(self.adb.package(app.YOUTUBE)['installed'])
        self.assertTrue(self.adb.package('com.google.android.gms')['installed'])
        self.assertFalse(self.adb.package('com.dangbei.launcher3')['installed'])
        self.assertEqual(self.adb.package(app.STOCK_YOUTUBE)['enabled'], 3)
        events = self.adb.mutations
        verify = next(i for i,c in enumerate(events) if c[:2] == ('am','broadcast'))
        disable = next(i for i,c in enumerate(events) if c[:2] == ('pm','disable-user') and c[-1] == app.STOCK_YOUTUBE)
        self.assertLess(verify, disable)
        app.restore(self.adb, self.manifest, folder)
        self.assertEqual(self.adb.settings, original)
        self.assertEqual(self.adb.package(app.STOCK_YOUTUBE)['enabled'], 0)
        self.assertFalse(self.adb.package(app.YOUTUBE)['installed'])

    def test_youtube_keeps_newer_google_services(self):
        self.install(google=True, ui=False, keyboard=False)
        pkg = 'com.google.android.gms'
        self.adb.packages[pkg]['version_code'] += 100
        mark = len(self.adb.mutations)
        folder = self.install(youtube=True, ui=False, keyboard=False)
        self.assertFalse(any(c[0] == 'install' and 'GooglePlayServices' in str(c)
                             for c in self.adb.mutations[mark:]))
        state = json.loads((folder / 'backup.json').read_text())
        self.assertEqual(state['packages'][pkg]['version_code'], self.adb.package(pkg)['version_code'])

    def test_default_install_does_not_add_youtube(self):
        self.install()
        self.assertFalse(self.adb.package(app.YOUTUBE)['installed'])
        self.assertEqual(self.adb.package(app.STOCK_YOUTUBE)['enabled'], 0)

    def test_youtube_guard_failure_keeps_stock_youtube_enabled(self):
        shell = self.adb.shell
        def failed_guard(*args, **kwargs):
            if args[:2] == ('am', 'broadcast'):
                return 'Broadcast completed: result=0'
            return shell(*args, **kwargs)
        self.adb.shell = failed_guard
        with self.assertRaises(app.Error):
            self.install(youtube=True, ui=False, keyboard=False)
        self.assertEqual(self.adb.package(app.STOCK_YOUTUBE)['enabled'], 0)

    def test_menu_all_and_youtube_only(self):
        import argparse
        for choice, command in [('3', 'install'), ('8', 'install-youtube')]:
            args = argparse.Namespace(device='test', backups=self.backups)
            with patch('builtins.input', return_value=choice):
                self.assertTrue(app.menu(args, self.manifest))
            self.assertEqual(args.command, command)
            self.assertTrue(args.google)
            self.assertTrue(args.youtube)

    def test_original_receiver_is_disabled_only_after_replacement_is_verified(self):
        original_install = self.adb.install

        def interrupted_install(paths, downgrade=False):
            if paths[0].name == 'Dangbei-Screencast-RU.apk':
                raise app.Error('Receiver install failed')
            return original_install(paths, downgrade)

        self.adb.install = interrupted_install
        with self.assertRaises(app.Error):
            self.install()
        self.assertEqual(self.adb.package(app.STOCK_CAST)['enabled'], 0)

    def test_failed_backup_blocks_all_mutations(self):
        self.adb.fail_pull = True
        with self.assertRaises(app.Error):
            self.install()
        self.assertEqual(self.adb.mutations, [])
        record = next(self.backups.glob('*/backup.json'))
        self.assertFalse(json.loads(record.read_text(encoding='utf-8'))['complete'])

    def test_corrupt_backup_pull_blocks_install(self):
        self.adb.bad_pull = True
        with self.assertRaises(app.Error):
            self.install()
        self.assertEqual(self.adb.mutations, [])

    def test_corrupt_payload_blocks_even_backup(self):
        (self.payload / self.manifest['packages'][0]['file']).write_bytes(b'wrong')
        with self.assertRaises(app.Error):
            self.install()
        self.assertFalse(self.backups.exists())
        self.assertEqual(self.adb.mutations, [])

    def test_other_model_or_firmware_is_rejected(self):
        for prop in ['ro.product.model_number', 'ro.build.version.incremental']:
            saved = self.adb.props[prop]
            self.adb.props[prop] = 'other'
            with self.assertRaises(app.Error):
                self.install()
            self.assertEqual(self.adb.mutations, [])
            self.adb.props[prop] = saved

    def test_restore_wrong_projector_or_corrupt_file_does_not_write(self):
        folder = self.install()
        count = len(self.adb.mutations)
        serial = self.adb.props['ro.serialno']
        self.adb.props['ro.serialno'] = 'ANOTHER'
        with self.assertRaises(app.Error):
            app.restore(self.adb, self.manifest, folder)
        self.adb.props['ro.serialno'] = serial
        next(folder.glob('packages/*/*.apk')).write_bytes(b'corrupt')
        with self.assertRaises(app.Error):
            app.restore(self.adb, self.manifest, folder)
        self.assertEqual(len(self.adb.mutations), count)

    def test_install_error_retains_backup_and_records_failure(self):
        self.adb.fail_install = True
        with self.assertRaises(app.Error):
            self.install()
        folder = next(self.backups.glob('*/backup.json')).parent
        self.assertTrue(json.loads((folder / 'backup.json').read_text(encoding='utf-8'))['complete'])
        self.assertEqual(json.loads((folder / 'install.json').read_text(encoding='utf-8'))['status'], 'failed')
        self.assertEqual(self.adb.props['pm.dexopt.install'], 'speed-profile')

    def test_reinstall_restore_never_uninstalls_existing_app(self):
        self.install()
        mark = len(self.adb.mutations)
        folder = self.install()
        self.assertFalse(any(c[0] == 'install' for c in self.adb.mutations[mark:]))
        mark = len(self.adb.mutations)
        app.restore(self.adb, self.manifest, folder)
        self.assertFalse(any(c[0] == 'uninstall' for c in self.adb.mutations[mark:]))

    def test_keyboard_is_selected_before_google_install_and_voice_ime_disabled(self):
        self.install(google=True)
        events = self.adb.mutations
        ime = next(i for i, c in enumerate(events) if c[:2] == ('ime', 'set'))
        google = next(i for i, c in enumerate(events) if c[0] == 'install' and 'GoogleServicesFramework' in str(c))
        self.assertLess(ime, google)
        self.assertTrue(any(c[:2] == ('ime', 'disable') and c[-1] == app.VOICE_IME for c in events))

    def test_multi_line_provider_icons_and_modes(self):
        text = ('Row: 0 packageName=, jumpUrl=dblauncher://mineapp, modeID=1, '
                'icon=BASE64\nMOREBASE64==\n, name=我的应用, sort=4\n'
                'Row: 1 packageName=, jumpUrl=dblauncher://mineapp, modeID=3, '
                'icon=NULL, name=Другие приложения, sort=4\n')
        rows = app.parse_rows(text, 'quick_app')
        self.assertEqual([r['modeID'] for r in rows], ['1', '3'])
        self.assertEqual(rows[0]['name'], '我的应用')

    def test_duplicate_provider_rows_rejected(self):
        with self.assertRaises(app.Error):
            app.parse_rows('Row: 0 typeID=1, name=a\nRow: 1 typeID=1, name=b', 'quick_settings')

    def test_adb_quotes_remote_shell_values(self):
        with patch('subprocess.run') as run:
            run.return_value.returncode, run.return_value.stdout = 0, b''
            app.ADB('adb', 'serial').shell('settings', 'put', 'system', 'key', "a' ; $(bad)")
            command = run.call_args.args[0]
            self.assertEqual(command[:4], ['adb', '-s', 'serial', 'shell'])
            import shlex
            self.assertEqual(shlex.split(command[4])[-1], "a' ; $(bad)")


KEYBOARD_PACKAGE = 'org.liskovsoft.androidtv.rukeyboard'

if __name__ == '__main__':
    unittest.main()
