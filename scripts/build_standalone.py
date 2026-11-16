#!/usr/bin/env python3
"""Build and smoke-test a complete native release; requires Python only on CI."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import install

PUBLIC_FILES = ['manifest.json', 'README.md', 'LICENSE', 'start.bat', 'start.sh',
                'start.command', 'docs/testing.md', 'docs/third-party.md',
                'docs/LeanKeyboard-LICENSE.txt']
PUBLIC_FILES += ['patches/youtube-fix/LICENSE', 'patches/youtube-fix/README.md', 'patches/youtube-fix/filter.js', 'patches/youtube-fix/patch.py', 'patches/youtube-fix/test-filter.cjs', 'patches/youtube-fix/src/local/ru/YouTubeAdBlock.java', 'patches/youtube-fix/src/local/ru/GoogleProcessGuard.java', 'scripts/build_youtube_fix.py']


def unpack(archive, destination):
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            path = destination / member.filename
            if not path.resolve().is_relative_to(destination.resolve()):
                raise ValueError('Unsafe archive path: ' + member.filename)
            z.extract(member, destination)
            if not member.is_dir() and os.name != 'nt':
                path.chmod((member.external_attr >> 16) & 0o777 or 0o644)


def smoke_test(folder):
    """Run actual frozen binaries from a different cwd with no Python/ADB on PATH."""
    exe = folder / ('dangbei-setup.exe' if os.name == 'nt' else 'dangbei-setup')
    env = os.environ.copy()
    env['PATH'] = ''
    env.pop('PYTHONHOME', None)
    env.pop('PYTHONPATH', None)
    with tempfile.TemporaryDirectory() as cwd:
        for args, stdin, expected in [([], '0\n', 'Русификация'),
                                       (['self-test'], '', 'Комплект проверен')]:
            result = subprocess.run([str(exe), *args], input=stdin, capture_output=True,
                                    encoding='utf-8', env=env, cwd=cwd, timeout=120)
            if result.returncode or expected not in result.stdout:
                raise RuntimeError('Standalone smoke test failed:\n' + result.stdout + result.stderr)
            if not args and 'YouTube Fix' not in result.stdout:
                raise RuntimeError('YouTube Fix missing from standalone menu')
            print(result.stdout)
        # Exercise the exact start file offered to users as well as the binary.
        wrapper_env = env.copy()
        if os.name == 'nt':
            system_root = Path(os.environ['SystemRoot'])
            wrapper_env['PATH'] = str(system_root / 'System32') + ';' + str(system_root)
            wrapper = [str(system_root / 'System32/cmd.exe'), '/d', '/c', str(folder / 'start.bat')]
        else:
            wrapper_env['PATH'] = '/usr/bin:/bin'
            wrapper = ['/bin/bash', str(folder / ('start.command' if sys.platform == 'darwin' else 'start.sh'))]
        result = subprocess.run(wrapper, input='0\n', capture_output=True, encoding='utf-8',
                                env=wrapper_env, cwd=cwd, timeout=120)
        if result.returncode or 'Русификация' not in result.stdout:
            raise RuntimeError('Start file failed:\n' + result.stdout + result.stderr)
        # A damaged payload must fail the same preflight in a frozen release.
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        apk = folder / 'apks' / manifest['packages'][0]['file']
        saved = apk.with_suffix('.saved')
        apk.rename(saved)
        try:
            result = subprocess.run([str(exe), 'self-test'], capture_output=True,
                                    encoding='utf-8', env=env, cwd=cwd, timeout=120)
            if result.returncode != 1 or 'Нет проверенного файла' not in result.stderr:
                raise RuntimeError('Missing APK was not rejected')
        finally:
            saved.rename(apk)


def build(args):
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    system = platform.system().lower()
    arch = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}[platform.machine().lower()]
    target = {'darwin': 'macos', 'windows': 'windows', 'linux': 'linux'}[system] + '-' + arch
    if args.target != target:
        raise ValueError(f'Expected native {args.target}, running {target}')
    build_root = ROOT / 'build' / target
    build_root.mkdir(parents=True, exist_ok=True)
    payload = args.apk_dir.resolve()
    if not args.offline:
        install.download(manifest, payload)
    install.check_payload(manifest, payload, google=True, youtube=True)
    tools = json.loads((ROOT / 'scripts/platform-tools.json').read_text())[system]
    tools_zip = build_root / 'platform-tools.zip'
    if not tools_zip.is_file() or install.digest(tools_zip) != tools['sha256']:
        with urllib.request.urlopen(tools['url'], timeout=60) as response, tools_zip.open('wb') as out:
            shutil.copyfileobj(response, out)
    if install.digest(tools_zip) != tools['sha256']:
        raise ValueError('Platform Tools checksum mismatch')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
                    '--console', '--name', 'dangbei-setup', '--distpath', str(build_root / 'binary'),
                    '--workpath', str(build_root / 'pyinstaller'), '--specpath', str(build_root),
                    str(ROOT / 'launcher.py')], cwd=ROOT, check=True)
    prefix = 'dangbei-x5-ultra-ru-' + manifest['version'] + '-' + target
    stage = build_root / prefix
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    for name in PUBLIC_FILES:
        if system != 'windows' and name == 'start.bat':
            continue
        if system != 'darwin' and name == 'start.command':
            continue
        if system == 'windows' and name == 'start.sh':
            continue
        dst = stage / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dst)
    exe_name = 'dangbei-setup.exe' if system == 'windows' else 'dangbei-setup'
    shutil.copy2(build_root / 'binary' / exe_name, stage / exe_name)
    unpack(tools_zip, stage)
    (stage / 'apks').mkdir()
    for package in manifest['packages']:
        for asset in install.assets(package):
            shutil.copy2(payload / asset['file'], stage / 'apks' / asset['file'])
    # Keep the Python license alongside the native executable.
    version = platform.python_version()
    with urllib.request.urlopen(f'https://raw.githubusercontent.com/python/cpython/v{version}/LICENSE', timeout=30) as response:
        (stage / 'docs/Python-LICENSE.txt').write_bytes(response.read())
    import PyInstaller
    from importlib.metadata import distribution
    dist = distribution('pyinstaller')
    for file in dist.files:
        if str(file).endswith('COPYING.txt'):
            shutil.copyfile(dist.locate_file(file), stage / 'docs/PyInstaller-LICENSE.txt')
            break
    else:
        raise RuntimeError('PyInstaller license not found')
    metadata = {'target': target, 'python': version, 'pyinstaller': PyInstaller.__version__,
                'platform_tools': tools, 'commit': subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    (stage / 'build-info.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    for name in ['start.sh', 'start.command']:
        if (stage / name).exists():
            (stage / name).chmod(0o755)
    sums = ''.join(install.digest(p) + '  ' + p.relative_to(stage).as_posix() + '\n'
                   for p in sorted(stage.rglob('*')) if p.is_file())
    (stage / 'SHA256SUMS').write_text(sums, encoding='utf-8')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / (prefix + '.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                z.write(path, prefix + '/' + path.relative_to(stage).as_posix())
    # Test the distributed archive, including Unicode/spaces in its path.
    with tempfile.TemporaryDirectory(prefix='Dangbei Проверка ') as temp:
        extracted = Path(temp)
        unpack(archive, extracted)
        smoke_test(extracted / prefix)
    archive.with_suffix('.zip.sha256').write_text(install.digest(archive) + '  ' + archive.name + '\n')
    print('Release archive verified: ' + str(archive))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--target', required=True)
    p.add_argument('--apk-dir', type=Path, default=ROOT / 'apks')
    p.add_argument('--output', type=Path, default=ROOT / 'dist')
    p.add_argument('--offline', action='store_true', help='Use already verified APKs')
    build(p.parse_args())
