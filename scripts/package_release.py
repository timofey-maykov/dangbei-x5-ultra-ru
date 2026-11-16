#!/usr/bin/env python3
"""Build a release from an explicit file list; never walk the work directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['install.py', 'manifest.json', 'README.md', 'LICENSE', 'start.sh', 'start.bat',
         'docs/testing.md', 'docs/third-party.md', 'docs/LeanKeyboard-LICENSE.txt']
FILES += ['patches/youtube-fix/LICENSE', 'patches/youtube-fix/README.md', 'patches/youtube-fix/filter.js', 'patches/youtube-fix/patch.py', 'patches/youtube-fix/test-filter.cjs', 'patches/youtube-fix/src/local/ru/YouTubeAdBlock.java', 'patches/youtube-fix/src/local/ru/GoogleProcessGuard.java', 'scripts/build_youtube_fix.py']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apk-dir', required=True, type=Path)
    p.add_argument('--output', default=ROOT / 'dist', type=Path)
    args = p.parse_args()
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=True)
    assets = [f for pkg in manifest['packages'] for f in [pkg] + pkg.get('splits', [])]
    for item in assets:
        name = item['file']
        if Path(name).name != name:
            raise ValueError('APK filename must not include a directory')
        source = args.apk_dir / name
        if source.stat().st_size != item['bytes'] or sha(source) != item['sha256']:
            raise ValueError('APK verification failed: ' + name)
        shutil.copyfile(source, args.output / name)
    prefix = 'dangbei-x5-ultra-ru-' + manifest['version']
    archive = args.output / (prefix + '.zip')
    sums = ''.join(item['sha256'] + '  ' + item['file'] + '\n' for item in assets)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as z:
        for name in FILES:
            z.write(ROOT / name, prefix + '/' + name)
        for item in assets:
            z.write(args.output / item['file'], prefix + '/apks/' + item['file'])
        z.writestr(prefix + '/apks/SHA256SUMS', sums)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all('/backup' not in name and '/tools/' not in name for name in z.namelist())
    (args.output / 'SHA256SUMS').write_text(sums + sha(archive) + '  ' + archive.name + '\n', encoding='utf-8')
    print(archive)
    print('Files: ' + str(len(assets)) + ' APKs; ZIP entries checked')


if __name__ == '__main__':
    main()
