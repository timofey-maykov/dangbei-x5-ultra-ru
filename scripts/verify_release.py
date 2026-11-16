"""Verify all native archives and their build commit before publication."""
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

folder = Path(sys.argv[1])
manifest = json.loads(Path('manifest.json').read_text(encoding='utf-8'))
version = manifest['version']
assert os.environ['RELEASE_TAG'] == 'v' + version
expected = {f'dangbei-x5-ultra-ru-{version}-{target}.zip' for target in
            ['windows-x64', 'macos-x64', 'macos-arm64', 'linux-x64']}
assert {p.name for p in folder.glob('*.zip')} == expected
checksums = []
for name in sorted(expected):
    path = folder / name
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    checksum = h.hexdigest()
    expected_sum = path.with_suffix('.zip.sha256').read_text().strip()
    assert expected_sum == checksum + '  ' + name, name
    checksums.append(expected_sum)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        prefix = path.stem + '/'
        metadata = json.loads(z.read(prefix + 'build-info.json'))
        assert metadata['commit'] == os.environ['RELEASE_COMMIT'], name
        assert name == f'dangbei-x5-ultra-ru-{version}-{metadata["target"]}.zip'
        assert json.loads(z.read(prefix + 'manifest.json')) == manifest, name
        for source in ['patches/youtube-fix/LICENSE', 'patches/youtube-fix/README.md',
                       'patches/youtube-fix/filter.js', 'patches/youtube-fix/patch.py',
                       'patches/youtube-fix/test-filter.cjs',
                       'patches/youtube-fix/src/local/ru/YouTubeAdBlock.java',
                       'patches/youtube-fix/src/local/ru/GoogleProcessGuard.java',
                       'scripts/build_youtube_fix.py']:
            assert z.read(prefix + source) == Path(source).read_bytes(), source
        for package in manifest['packages']:
            for asset in [package] + package.get('splits', []):
                entry = prefix + 'apks/' + asset['file']
                assert z.getinfo(entry).file_size == asset['bytes'], entry
                digest = hashlib.sha256()
                with z.open(entry) as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b''):
                        digest.update(chunk)
                assert digest.hexdigest() == asset['sha256'], entry
    print('Verified:', name)
(folder / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n', encoding='utf-8')
