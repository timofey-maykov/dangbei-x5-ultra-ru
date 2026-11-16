#!/usr/bin/env python3
"""Rebuild the local patch from a pinned original APK. Output is unsigned."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'patches/youtube-fix'
ORIGINAL_SHA256 = 'f450a094f1f7e8b8b7b8d707a2238b919542d2a925c484e6fbcf09ccf32b7a61'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--apktool', type=Path, required=True)
    parser.add_argument('--java', default='java')
    parser.add_argument('--javac', default='javac')
    parser.add_argument('--work', type=Path, default=ROOT / 'build/youtube-fix')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if hashlib.sha256(args.original.read_bytes()).hexdigest() != ORIGINAL_SHA256:
        parser.error('Expected the pinned YouTube TV 7.32.300 armeabi-v7a original APK')
    if args.work.exists():
        parser.error('Work directory must be new; choose a different --work directory')
    android = args.sdk / 'platforms/android-34/android.jar'
    d8 = args.sdk / 'build-tools/34.0.0/lib/d8.jar'
    for path in (android, d8, args.apktool):
        if not path.is_file():
            parser.error('Missing build tool: ' + str(path))
    work = args.work.resolve()
    decoded, classes, dex = work / 'decoded', work / 'classes', work / 'dex'
    classes.mkdir(parents=True)
    dex.mkdir()
    def run(*cmd):
        subprocess.run([str(arg) for arg in cmd], check=True)
    run(args.java, '-jar', args.apktool, 'd', args.original, '-o', decoded)
    run(sys.executable, SOURCE / 'patch.py', decoded)
    run(args.javac, '-source', '8', '-target', '8', '-classpath', android, '-d', classes,
        *sorted((SOURCE / 'src/local/ru').glob('*.java')), decoded / 'YouTubeAdBlockPayload.java')
    run(args.java, '-cp', d8, 'com.android.tools.r8.D8', '--min-api', '24', '--lib', android,
        '--output', dex, *sorted(classes.rglob('*.class')))
    if (decoded / 'smali_classes4').exists():
        raise RuntimeError('Unexpected original DEX layout')
    shutil.copyfile(dex / 'classes.dex', decoded / 'classes4.dex')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run(args.java, '-jar', args.apktool, 'b', decoded, '-o', args.output)
    print('Unsigned APK:', args.output)

if __name__ == '__main__':
    main()
