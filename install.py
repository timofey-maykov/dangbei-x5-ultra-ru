#!/usr/bin/env python3
"""Dangbei X5 Ultra RU: install only after a verified, device-specific backup."""
import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
HOME = 'com.dangbei.launcher3/com.dangbei.leard.leradlauncher.ui.splash.SplashActivity'
REMOTE = 'local.dangbei.sidebar.ru/local.ru.RemoteService'
KEYBOARD = 'org.liskovsoft.androidtv.rukeyboard/com.liskovsoft.leankeyboard.ime.LeanbackImeService'
SOGOU = 'com.sohu.inputmethod.sogou.tv/.SogouIME'
VOICE_IME = ('com.google.android.googlequicksearchbox/'
             'com.google.android.voicesearch.ime.VoiceInputMethodService')
STOCK_HOMES = ['com.dangbei.leard.leradlauncher', 'com.dangbei.tvlauncher',
               'com.dangbei.launcher.companion']
ORIGINALS = STOCK_HOMES + ['com.dangbei.leard.settings', 'com.dangbei.systemui',
                          'com.dangbei.colormaster', 'com.sohu.inputmethod.sogou.tv']
SETTINGS = [('global', 'hidden_api_policy'), ('system', 'system_locales'),
            ('system', 'settings_theme_type'), ('secure', 'default_input_method'),
            ('secure', 'enabled_input_methods'), ('secure', 'selected_input_method_subtype'),
            ('secure', 'enabled_accessibility_services'), ('secure', 'accessibility_enabled')]
PERMISSIONS = ['android.permission.' + x for x in (
    'WRITE_SECURE_SETTINGS', 'READ_EXTERNAL_STORAGE', 'WRITE_EXTERNAL_STORAGE',
    'ACCESS_COARSE_LOCATION', 'ACCESS_FINE_LOCATION')]
OPS = {
    'local.dangbei.settings.writer': ['WRITE_SETTINGS'],
    'local.dangbei.settings.ru': ['WRITE_SETTINGS'],
    'local.dangbei.colormaster.ru': ['WRITE_SETTINGS', 'SYSTEM_ALERT_WINDOW'],
    'com.dangbei.launcher3': ['WRITE_SETTINGS'],
    'local.dangbei.sidebar.ru': ['SYSTEM_ALERT_WINDOW'],
}
URI = 'content://com.android.systemui.QuickCentre.data/'
TABLES = {'quick_settings': 'typeID', 'quick_settings_common': 'typeID',
          'quick_app': 'jumpUrl', 'quick_app_common': 'packageName'}
LABELS = {1: 'Настройки', 12: 'Автофокус', 13: 'Фокус', 17: 'Геометрия',
          18: 'Два окна', 20: 'Детализация', 21: 'Цвет (ИИ)', 23: 'Видео 4K',
          3: 'Цветовой режим', 24: 'Мастер изображения', 15: 'Режим 3D',
          10: 'Яркость', 7: 'Bluetooth', 9: 'Сеть', 14: 'Очистка памяти',
          11: 'Входы', 2: 'Плавность', 6: 'Файлы', 16: 'Поиск пульта',
          8: 'Автокоррекция', 4: 'Звук', 19: 'Игровой режим', 22: 'Filmmaker'}


class Error(RuntimeError):
    pass


def external_env():
    env = os.environ.copy()
    if getattr(sys, 'frozen', False):
        for key in ('LD_LIBRARY_PATH', 'LIBPATH'):
            original = env.pop(key + '_ORIG', None)
            if original is None:
                env.pop(key, None)
            else:
                env[key] = original
    return env


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save_json(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def parse_rows(text, table):
    """The vendor ignores --projection. Only retain columns we modify."""
    rows = []
    if text.strip() == 'No result found.':
        return []
    parts = re.split(r'(?m)^Row: \d+ ', text)
    if parts[0].strip() or len(parts) < 2:
        raise Error('Не удалось прочитать таблицу ' + table)
    for line in parts[1:]:
        fields = {}
        for part in re.split(r', (?=[A-Za-z_]\w*=)', line.strip()):
            key, sep, value = part.partition('=')
            if not sep or key in fields:
                raise Error('Неоднозначная строка в ' + table)
            fields[key] = value
        key = TABLES[table]
        if key not in fields or 'name' not in fields:
            raise Error('В таблице ' + table + ' нет нужных столбцов')
        if key == 'typeID':
            if not fields[key].isdigit():
                raise Error('Некорректный typeID')
            if int(fields[key]) not in LABELS:
                continue
        elif fields[key] != 'dblauncher://mineapp':
            continue
        row = {key: fields[key], 'name': fields['name']}
        if key != 'typeID':
            if not fields.get('modeID', '').isdigit():
                raise Error('Нет modeID в ' + table)
            row['modeID'] = fields['modeID']
        rows.append(row)
    keys = [(r[TABLES[table]], r.get('modeID')) for r in rows]
    if len(keys) != len(set(keys)):
        raise Error('Повторяющиеся записи в ' + table)
    return rows


class ADB:
    def __init__(self, executable, device):
        self.executable = executable
        self.device = device

    def run(self, *args, timeout=90, check=True, select=True):
        command = [self.executable] + (['-s', self.device] if select else []) + list(args)
        try:
            p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=timeout, env=external_env())
        except subprocess.TimeoutExpired:
            raise Error('ADB не ответил вовремя: ' + ' '.join(args[:3])) from None
        text = p.stdout.decode('utf-8', 'replace').strip()
        if check and (p.returncode or re.search(
                r'(?im)^(?:Error(?:\b|:)|Failure\b|Exception\b|Security exception|java\.lang\.)', text)):
            raise Error(text or 'ADB завершился с ошибкой')
        return text

    def shell(self, *args, **kwargs):
        # adb joins arguments into a remote shell command, so quote them there.
        return self.run('shell', shlex.join(str(a) for a in args), **kwargs)

    def connect(self):
        if ':' in self.device:
            self.run('connect', self.device, select=False, timeout=25)
        if self.run('get-state') != 'device':
            raise Error('Проектор не подключён. Проверьте адрес и разрешение отладки на экране.')
        if self.shell('am', 'get-current-user') != '0':
            raise Error('Нужен основной пользователь Android (user 0).')

    def setting(self, ns, key):
        # Preserve absence separately from a literal string "null".
        values = dict(line.split('=', 1) for line in self.shell(
            'settings', '--user', '0', 'list', ns).splitlines() if '=' in line)
        return values.get(key)

    def put(self, ns, key, value):
        if value is None:
            self.shell('settings', '--user', '0', 'delete', ns, key)
        else:
            self.shell('settings', '--user', '0', 'put', ns, key, value)
        if self.setting(ns, key) != value:
            raise Error('Настройка не сохранилась: ' + ns + '/' + key)

    def package(self, pkg):
        paths = self.shell('pm', 'path', '--user', '0', pkg, check=False)
        paths = [s.removeprefix('package:') for s in paths.splitlines() if s.startswith('package:')]
        if not paths:
            return {'installed': False}
        dump = self.shell('dumpsys', 'package', pkg)
        version = re.search(r'versionCode=(\d+)', dump)
        enabled = re.search(r'User 0:.*?enabled=(\d+)', dump)
        if not version or not enabled:
            raise Error('Не удалось прочитать состояние ' + pkg)
        permissions = {}
        for permission in PERMISSIONS:
            granted = re.search(re.escape(permission) + r': granted=(true|false)', dump)
            if granted:
                permissions[permission] = granted[1] == 'true'
            elif permission in dump:
                permissions[permission] = False
        ops = {}
        for op in OPS.get(pkg, []):
            output = self.shell('cmd', 'appops', 'get', '--user', '0', pkg, op)
            mode = re.search(r'\b' + op + r': (\w+)', output)
            ops[op] = mode[1] if mode else 'default'
        return {'installed': True, 'paths': paths, 'version_code': int(version[1]),
                'enabled': int(enabled[1]), 'permissions': permissions, 'appops': ops}

    def home(self):
        text = self.shell('cmd', 'package', 'resolve-activity', '--brief', '--user', '0',
                          '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME')
        for line in reversed(text.splitlines()):
            if re.fullmatch(r'[\w.]+/[\w.$]+', line):
                return line
        raise Error('Не удалось определить текущий главный экран.')

    def install(self, paths, downgrade=False):
        command = ['install-multiple' if len(paths) > 1 else 'install', '--no-incremental', '-r']
        if downgrade:
            command.append('-d')
        output = self.run(*command, *(str(p) for p in paths), timeout=600)
        if 'Success' not in output:
            raise Error('Установка не подтверждена: ' + output)


def identity(adb):
    props = {'model': 'ro.product.model', 'model_number': 'ro.product.model_number',
             'device': 'ro.product.device', 'sdk': 'ro.build.version.sdk',
             'incremental': 'ro.build.version.incremental', 'serial': 'ro.serialno',
             'fingerprint': 'ro.build.fingerprint'}
    values = {k: adb.shell('getprop', v) for k, v in props.items()}
    if not values['serial'] or values['serial'].lower() == 'unknown':
        raise Error('Не удалось прочитать серийный номер: бэкап нельзя привязать к проектору.')
    return values


def preflight(adb, manifest):
    device = identity(adb)
    expected = manifest['compatibility']
    for key in ['model', 'model_number', 'device', 'sdk', 'incremental']:
        if device[key] != expected[key]:
            raise Error(f'Несовместимый проектор: {key}={device[key]!r}, нужен {expected[key]!r}. '
                        'На проекторе ничего не менялось.')
    for pkg, code in expected['native_versions'].items():
        current = adb.package(pkg)
        if not current['installed'] or current['version_code'] != code:
            raise Error('Версия штатного приложения не проверена: ' + pkg)
    print(f"Проектор: {device['model']}, {device['model_number']}, сборка {device['incremental']}")
    return device


def selected_packages(manifest, keyboard=True, google=False, ui=True):
    return [p for p in manifest['packages'] if
            (google if p.get('google') else ui and (keyboard or not p.get('keyboard')))]


def assets(package):
    return [package] + package.get('splits', [])


def check_payload(manifest, folder, keyboard=True, google=False, ui=True):
    for package in selected_packages(manifest, keyboard, google, ui):
        for item in assets(package):
            path = folder / item['file']
            if not path.is_file() or path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
                raise Error(f"Нет проверенного файла {path}. Распакуйте полный архив релиза или выполните download.")


def download(manifest, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for item in [asset for p in manifest['packages'] for asset in assets(p)]:
        path = folder / item['file']
        if path.is_file() and digest(path) == item['sha256']:
            print('Уже скачан: ' + path.name)
            continue
        tag = manifest.get('apk_release', 'v' + manifest['version'])
        url = f"https://github.com/{manifest['repository']}/releases/download/{tag}/{item['file']}"
        print('Скачиваю ' + path.name, flush=True)
        part = path.with_suffix('.part')
        try:
            context = None
            if getattr(sys, 'frozen', False):
                import certifi
                context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(url, timeout=60, context=context) as response, part.open('wb') as f:
                shutil.copyfileobj(response, f)
            if part.stat().st_size != item['bytes'] or digest(part) != item['sha256']:
                raise Error('Не совпала контрольная сумма ' + path.name)
            part.replace(path)
        finally:
            part.unlink(missing_ok=True)


def backup(adb, manifest, root, keyboard=True, google=False, ui=True):
    device = preflight(adb, manifest)
    selected = selected_packages(manifest, keyboard, google, ui)
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < 1024 ** 3:
        raise Error('Для бэкапа нужен хотя бы 1 ГБ свободного места на компьютере.')
    name = dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    folder = root / name
    folder.mkdir(mode=0o700)
    state = {'format': 1, 'complete': False, 'device': device, 'version': manifest['version'],
             'created_at': dt.datetime.now().astimezone().isoformat(), 'home': adb.home(),
             'selected': [p['package'] for p in selected], 'ui': ui, 'google': google,
             'settings': {}, 'packages': {},
             'tables': {}, 'files': {}, 'dexopt': adb.shell('getprop', 'pm.dexopt.install')}
    save_json(folder / 'backup.json', state)
    print('Бэкап: ' + str(folder.resolve()), flush=True)
    try:
        for ns, key in SETTINGS:
            state['settings'][ns + '/' + key] = adb.setting(ns, key)
        for pkg in dict.fromkeys(ORIGINALS + state['selected']):
            info = adb.package(pkg)
            state['packages'][pkg] = info
            if not info['installed']:
                continue
            info['files'] = []
            target = folder / 'packages' / pkg
            target.mkdir(parents=True)
            print('  Сохраняю ' + pkg, flush=True)
            for i, remote in enumerate(info['paths']):
                dest = target / (str(i) + '.apk')
                adb.run('pull', remote, str(dest), timeout=300)
                remote_hash = adb.shell('sha256sum', remote).split()[0]
                actual = digest(dest)
                if actual != remote_hash:
                    raise Error('Бэкап APK повреждён: ' + pkg)
                relative = dest.relative_to(folder).as_posix()
                state['files'][relative] = actual
                info['files'].append(relative)
        for table in TABLES:
            raw = adb.shell('content', 'query', '--uri', URI + table)
            state['tables'][table] = parse_rows(raw, table)
        if not state['tables']['quick_settings']:
            raise Error('Не найдены подписи боковой панели.')
        state['complete'] = True
        save_json(folder / 'backup.json', state)
        validate_backup(folder, manifest, device)
    except BaseException:
        state['complete'] = False
        save_json(folder / 'backup.json', state)
        raise
    print('Бэкап готов и проверен. До этого момента проектор не менялся.', flush=True)
    return folder, state


def validate_backup(folder, manifest, device):
    state = json.loads((folder / 'backup.json').read_text(encoding='utf-8'))
    if state.get('format') != 1 or state.get('complete') is not True:
        raise Error('Бэкап не завершён. Восстановление остановлено.')
    for key in ['serial', 'model_number', 'fingerprint']:
        if state['device'].get(key) != device.get(key):
            raise Error('Бэкап от другого проектора или прошивки: ' + key)
    allowed = set(ORIGINALS) | {p['package'] for p in manifest['packages']}
    target_packages = {p['package'] for p in manifest['packages']}
    if (not set(state['packages']).issubset(allowed)
            or not set(state['selected']).issubset(target_packages)
            or not set(state['selected']).issubset(state['packages'])
            or not set(STOCK_HOMES).issubset(state['packages'])):
        raise Error('В бэкапе неизвестные приложения.')
    if set(state['settings']) != {ns + '/' + key for ns, key in SETTINGS}:
        raise Error('В бэкапе не хватает настроек.')
    if not re.fullmatch(r'[\w.]+/[\w.$]+', state['home']):
        raise Error('Некорректный главный экран в бэкапе.')
    for relative, sha in state['files'].items():
        path = folder / relative
        if not path.resolve().is_relative_to(folder.resolve()) or not path.is_file() or digest(path) != sha:
            raise Error('Не прошёл проверку файл бэкапа: ' + relative)
    for pkg, info in state['packages'].items():
        if info['installed'] and (not info.get('files') or any(f not in state['files'] for f in info['files'])):
            raise Error('В бэкапе нет APK: ' + pkg)
    if set(state['tables']) != set(TABLES):
        raise Error('В бэкапе не хватает подписей панели.')
    return state


def update_label(adb, table, row, name):
    key = TABLES[table]
    value = row[key]
    if key == 'typeID':
        if not value.isdigit():
            raise Error('Некорректный typeID в бэкапе')
        where = key + '=' + value
    else:
        if value != 'dblauncher://mineapp':
            raise Error('Неизвестное приложение в таблице панели')
        if not row.get('modeID', '').isdigit():
            raise Error('Некорректный modeID')
        where = key + "='dblauncher://mineapp' AND modeID=" + row['modeID']
    bind = 'name:n:' if name == 'NULL' else 'name:s:' + name
    adb.shell('content', 'update', '--uri', URI + table, '--bind', bind, '--where', where)
    rows = parse_rows(adb.shell('content', 'query', '--uri', URI + table, '--where', where), table)
    if not any(r[key] == value and r.get('modeID') == row.get('modeID') and r['name'] == name for r in rows):
        raise Error('Подпись не сохранилась: ' + table + '/' + value)


def set_enabled(adb, pkg, value):
    commands = {0: 'default-state', 1: 'enable', 2: 'disable', 3: 'disable-user', 4: 'disable-until-used'}
    if value not in commands:
        raise Error('Неизвестное состояние приложения: ' + str(value))
    adb.shell('pm', commands[value], '--user', '0', pkg)


def merge_service(previous):
    services = [s for s in (previous or '').split(':') if s and s != 'null']
    return ':'.join(dict.fromkeys(services + [REMOTE]))


def configure_keyboard(adb):
    adb.shell('ime', 'enable', '--user', '0', KEYBOARD)
    adb.shell('ime', 'set', '--user', '0', KEYBOARD)
    available = adb.shell('ime', 'list', '-s', '-a').splitlines()
    for ime in [SOGOU, VOICE_IME]:
        if ime in available:
            adb.shell('ime', 'disable', '--user', '0', ime)
    if adb.setting('secure', 'default_input_method') != KEYBOARD:
        raise Error('Не удалось выбрать LeanKeyboard.')


def install(adb, manifest, payload, backup_root, keyboard=True, google=False, ui=True):
    check_payload(manifest, payload, keyboard, google, ui)
    preflight(adb, manifest)
    for item in selected_packages(manifest, keyboard, google, ui):
        current = adb.package(item['package'])
        if current['installed'] and current['version_code'] > item['version_code']:
            raise Error('Уже установлена более новая версия: ' + item['package'])
    folder, state = backup(adb, manifest, backup_root, keyboard, google, ui)
    journal = {'status': 'installing', 'steps': []}

    def step(message):
        journal['steps'].append(message)
        save_json(folder / 'install.json', journal)
        print(message, flush=True)

    try:
        step('Устанавливаю приложения')
        adb.shell('setprop', 'pm.dexopt.install', 'verify')
        for item in selected_packages(manifest, keyboard, google, ui):
            step('  ' + item['file'])
            current = adb.package(item['package'])
            expected_hashes = {asset['sha256'] for asset in assets(item)}
            same = (current['installed'] and len(current['paths']) == len(assets(item)) and
                    {adb.shell('sha256sum', p).split()[0] for p in current['paths']} == expected_hashes)
            if same:
                print('    Уже стоит эта сборка, переустановка не нужна.', flush=True)
            else:
                adb.install([payload / asset['file'] for asset in assets(item)])
            if item.get('keyboard'):
                configure_keyboard(adb)
            current = adb.package(item['package'])
            if not current['installed'] or len(current['paths']) != len(assets(item)):
                raise Error('Не удалось проверить установленный APK')
            installed_hashes = {adb.shell('sha256sum', path).split()[0] for path in current['paths']}
            if installed_hashes != {asset['sha256'] for asset in assets(item)}:
                raise Error('Установленный APK не совпадает с релизом: ' + item['package'])
            set_enabled(adb, item['package'], 1)
        step('Настраиваю разрешения')
        for item in selected_packages(manifest, keyboard, google, ui):
            pkg = item['package']
            info = adb.package(pkg)
            for perm, granted in info['permissions'].items():
                if not granted:
                    adb.shell('pm', 'grant', '--user', '0', pkg, perm)
            for op in OPS.get(pkg, []):
                adb.shell('cmd', 'appops', 'set', '--user', '0', pkg, op, 'allow')
        if ui:
            adb.put('global', 'hidden_api_policy', '1')
            adb.put('system', 'settings_theme_type', '1')
            adb.put('system', 'system_locales', 'ru-RU')
            step('Перевожу подписи боковой панели')
            for table, rows in state['tables'].items():
                for row in rows:
                    name = LABELS[int(row['typeID'])] if 'typeID' in row else 'Приложения'
                    update_label(adb, table, row, name)
        if keyboard and ui:
            step('Включаю LeanKeyboard')
            configure_keyboard(adb)
        if ui:
            step('Переключаю главный экран')
            adb.shell('cmd', 'package', 'set-home-activity', '--user', '0', HOME)
            if adb.home().split('/')[0] != HOME.split('/')[0]:
                raise Error('Главный экран не переключился. Штатный лаунчер оставлен включённым.')
            adb.shell('am', 'start', '--user', '0', '-n', HOME)
            for pkg in STOCK_HOMES:
                if state['packages'][pkg]['installed']:
                    set_enabled(adb, pkg, 3)
            step('Подключаю боковую кнопку пульта')
            services = merge_service(state['settings']['secure/enabled_accessibility_services'])
            adb.put('secure', 'enabled_accessibility_services', services)
            adb.put('secure', 'accessibility_enabled', '1')
            for _ in range(10):
                if re.search(r'Bound services:\{[^\n]*Боковая панель', adb.shell('dumpsys', 'accessibility')):
                    break
                time.sleep(1)
            else:
                raise Error('Служба боковой кнопки не подключилась. Бэкап сохранён.')
        else:
            # Even Google-only installs can reset these on the vendor ROM.
            for key in ['enabled_accessibility_services', 'accessibility_enabled',
                        'enabled_input_methods', 'default_input_method', 'selected_input_method_subtype']:
                adb.put('secure', key, state['settings']['secure/' + key])
        if keyboard and ui and adb.setting('secure', 'default_input_method') != KEYBOARD:
            raise Error('Прошивка сменила клавиатуру. Смотрите раздел «Клавиатура» в README.')
        journal['status'] = 'complete'
        save_json(folder / 'install.json', journal)
    except BaseException as exc:
        journal['status'] = 'failed'
        journal['error'] = str(exc)
        save_json(folder / 'install.json', journal)
        print('\nУстановка остановлена. Бэкап: ' + str(folder.resolve()), file=sys.stderr)
        print('Восстановление: python install.py --device ' + adb.device +
              ' restore "' + str(folder.resolve()) + '"', file=sys.stderr)
        raise
    finally:
        try:
            adb.shell('setprop', 'pm.dexopt.install', state['dexopt'])
        except Error as exc:
            print('Не удалось вернуть pm.dexopt.install: ' + str(exc), file=sys.stderr)
    print('\nГотово. Бэкап: ' + str(folder.resolve()))
    print('Перезагрузите проектор обычным способом. Проверьте боковую кнопку и раскладки клавиатуры.')
    if google:
        print('После перезагрузки откройте Google Play и войдите в свой аккаунт.')
    return folder


def restore(adb, manifest, folder):
    # Check *all* files and identity before any mutation, including home/IME changes.
    state = validate_backup(folder, manifest, identity(adb))
    print('Восстанавливаю бэкап ' + str(folder.resolve()), flush=True)
    journal = {'status': 'restoring'}
    save_json(folder / 'restore.json', journal)
    try:
        for pkg in state['selected']:
            info = state['packages'][pkg]
            if info['installed']:
                print('  Возвращаю APK ' + pkg, flush=True)
                adb.install([folder / f for f in info['files']], downgrade=True)
        # Make the old home available before removing any newly installed launcher.
        home_pkg = state['home'].split('/')[0]
        if not adb.package(home_pkg)['installed']:
            raise Error('Старый главный экран отсутствует. Автоматическое удаление отменено.')
        if state.get('ui', True):
            set_enabled(adb, home_pkg, 1)
            adb.shell('cmd', 'package', 'set-home-activity', '--user', '0', state['home'])
            adb.shell('am', 'start', '--user', '0', '-n', state['home'])
            for table, rows in state['tables'].items():
                for row in rows:
                    update_label(adb, table, row, row['name'])
        old_ime = state['settings']['secure/default_input_method']
        if old_ime:
            adb.shell('ime', 'enable', '--user', '0', old_ime)
            adb.shell('ime', 'set', '--user', '0', old_ime)
        for pkg in reversed(state['selected']):
            info = state['packages'][pkg]
            if not info['installed']:
                if adb.package(pkg)['installed']:
                    result = adb.run('uninstall', pkg)
                    if 'Success' not in result:
                        raise Error('Не удалось удалить ' + pkg)
                continue
            for op, mode in info['appops'].items():
                adb.shell('cmd', 'appops', 'set', '--user', '0', pkg, op, mode)
            now = adb.package(pkg)['permissions']
            for permission, granted in info['permissions'].items():
                if now.get(permission) != granted:
                    adb.shell('pm', 'grant' if granted else 'revoke', '--user', '0', pkg, permission)
        for pkg in (set(STOCK_HOMES) if state.get('ui', True) else set()) | set(state['selected']):
            info = state['packages'][pkg]
            if info['installed']:
                set_enabled(adb, pkg, info['enabled'])
        # Last: Android may alter these while packages and IMEs are changed.
        for ns, key in SETTINGS:
            if state.get('ui', True) or ns == 'secure':
                adb.put(ns, key, state['settings'][ns + '/' + key])
        adb.shell('setprop', 'pm.dexopt.install', state['dexopt'])
        if state.get('ui', True) and adb.home().split('/')[0] != home_pkg:
            raise Error('Не удалось вернуть главный экран')
        journal['status'] = 'complete'
        save_json(folder / 'restore.json', journal)
    except BaseException as exc:
        journal.update(status='failed', error=str(exc))
        save_json(folder / 'restore.json', journal)
        raise
    print('Приложения и изменённые настройки восстановлены. Перезагрузите проектор.')


@contextlib.contextmanager
def lock(root, serial):
    root.mkdir(parents=True, exist_ok=True)
    path = root / ('.lock-' + hashlib.sha256(serial.encode()).hexdigest()[:16])
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise Error(f'Уже есть блокировка {path}. Если другой запуск завершён, удалите этот файл.') from None
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def menu(args, manifest):
    print('\nDangbei X5 Ultra: русский интерфейс и Google\n')
    print('  1. Русификация и клавиатура')
    print('  2. Только сервисы Google и Play Маркет')
    print('  3. Всё сразу: русификация, клавиатура и Google')
    print('  4. Только бэкап, ничего не менять')
    print('  5. Восстановить из бэкапа')
    print('  6. Проверить совместимость')
    print('  7. Скачать файлы релиза')
    print('  0. Выход\n')
    choice = input('Что делаем? ').strip()
    if choice == '0':
        return False
    actions = {'1': 'install', '2': 'install-google', '3': 'install', '4': 'backup',
               '5': 'restore', '6': 'check', '7': 'download'}
    if choice not in actions:
        raise Error('Введите номер от 0 до 7.')
    args.command = actions[choice]
    args.google = choice in {'2', '3', '4'}
    args.no_keyboard = False
    if choice == '5':
        folders = sorted(args.backups.glob('*/backup.json'), reverse=True)
        folders = [p.parent for p in folders if json.loads(p.read_text(encoding='utf-8')).get('complete')]
        for i, folder in enumerate(folders, 1):
            print(f'  {i}. {folder.name}')
        answer = input('Номер бэкапа или полный путь к его папке: ').strip().strip('"')
        if answer.isdigit() and 1 <= int(answer) <= len(folders):
            args.backup = folders[int(answer) - 1]
        else:
            args.backup = Path(answer)
    if args.command != 'download' and not args.device:
        args.device = input('IP проектора (например, 192.168.1.100:5555) или USB-серийный номер: ').strip()
        if re.fullmatch(r'\d{1,3}(?:\.\d{1,3}){3}', args.device):
            args.device += ':5555'
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description='Русификация Dangbei X5 Ultra с бэкапом перед установкой')
    parser.add_argument('--device', help='IP:порт или серийный номер из adb devices')
    default_adb = ROOT / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')
    parser.add_argument('--adb', default=str(default_adb) if default_adb.is_file() else 'adb',
                        help='Путь к adb/adb.exe')
    parser.add_argument('--apks', type=Path, default=ROOT / 'apks')
    parser.add_argument('--backups', type=Path, default=ROOT / 'backups')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('download', help='Скачать APK релиза и проверить SHA-256')
    sub.add_parser('self-test', help='Проверить комплект на компьютере, без подключения к проектору')
    sub.add_parser('check', help='Проверить проектор, ничего не устанавливать')
    for name in ['backup', 'install']:
        p = sub.add_parser(name)
        p.add_argument('--no-keyboard', action='store_true', help='Сохранить текущую клавиатуру')
        p.add_argument('--google', action='store_true', help='Также установить/сохранить сервисы Google')
    sub.add_parser('install-google', help='Только Google, без смены интерфейса')
    sub.add_parser('restore').add_argument('backup', type=Path)
    args = parser.parse_args(argv)
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    if args.command == 'self-test':
        check_payload(manifest, args.apks, google=True)
        print(ADB(args.adb, '').run('version', select=False))
        print('Комплект проверен: все APK и ADB на месте. Проектор не менялся.')
        return
    if args.command is None:
        if not menu(args, manifest):
            return
    if args.command == 'download':
        download(manifest, args.apks)
        return
    if not args.device:
        parser.error('Укажите --device. Скрипт не выбирает случайный Android-девайс.')
    if not shutil.which(args.adb):
        raise Error('Не найден adb. Установите Android Platform Tools или укажите --adb.')
    adb = ADB(args.adb, args.device)
    adb.connect()
    with lock(args.backups, args.device):
        if args.command == 'check':
            preflight(adb, manifest)
            print('Проверка пройдена. Ничего не установлено.')
        elif args.command == 'backup':
            backup(adb, manifest, args.backups, not args.no_keyboard, args.google)
        elif args.command == 'install':
            install(adb, manifest, args.apks, args.backups, not args.no_keyboard, args.google)
        elif args.command == 'install-google':
            install(adb, manifest, args.apks, args.backups, keyboard=False, google=True, ui=False)
        else:
            restore(adb, manifest, args.backup)


def run_cli():
    try:
        main()
        return 0
    except (Error, OSError, ValueError, KeyError) as exc:
        print('Ошибка: ' + str(exc), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('\nОстановлено. Если установка началась, используйте сохранённый бэкап.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(run_cli())
