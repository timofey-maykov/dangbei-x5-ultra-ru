from pathlib import Path
import re, json, argparse
parser = argparse.ArgumentParser()
parser.add_argument('decoded', type=Path)
parser.add_argument('--package', choices=['local.ru.youtube.tv', 'local.ru.youtube.tv.adtest'], default='local.ru.youtube.tv')
args = parser.parse_args()

root = args.decoded
source = Path(__file__).resolve().parent
def replace_method(path, signature, body):
    s = path.read_text()
    s, count = re.subn(r'\.method ' + re.escape(signature) + r'\n.*?\.end method',
        '.method ' + signature + '\n' + body + '\n.end method', s, flags=re.S)
    assert count == 1, (path, signature, count)
    path.write_text(s)

for area, sigs in {
    'dev/cobalt/media': [
        ('static isWidevineCryptoSchemeSupported()Z', False),
        ('static create(Ljava/lang/String;J)Ldev/cobalt/media/MediaDrmBridge;', True)],
    'cobalt/org/chromium/media': [
        ('private static isCryptoSchemeSupported([BLjava/lang/String;)Z', False),
        ('private static create([BLjava/lang/String;Ljava/lang/String;Ljava/lang/String;ZJJ)Lcobalt/org/chromium/media/MediaDrmBridge;', True)],
}.items():
    for sig, obj in sigs:
        replace_method(root/'smali_classes2'/area/'MediaDrmBridge.smali', sig,
                       '    .locals 1\n    const/4 v0, 0x0\n    ' + ('return-object' if obj else 'return') + ' v0')

p = root/'smali_classes2/don.smali'
s = p.read_text()
for region in ('0','4'):
    old = f'.catch Ljava/lang/SecurityException; {{:try_start_{region} .. :try_end_{region}}} :catch_2'
    assert s.count(old) == 1
    s = s.replace(old, old.replace(':catch_2', ':catch_1'))
p.write_text(s)

p = root/'smali_classes2/dev/cobalt/shell/StartupGuardNavigationObserver.smali'
s = p.read_text()
s = s.replace('    invoke-direct {p0}, Lbuh;-><init>()V',
    '    invoke-direct {p0}, Lbuh;-><init>()V\n    invoke-static {p1}, Llocal/ru/YouTubeAdBlock;->setContents(Ljava/lang/Object;)V')
call = '    invoke-virtual {p0, p1}, Lbuh;->observe(Lcobalt/org/chromium/content_public/browser/WebContents;)V'
assert s.count(call) == 3
# Preserve the constructor registration, remove just the two detach calls.
constructor_end = s.index('.end method')
s = s[:constructor_end] + s[constructor_end:].replace(call, '')
header = '.method public final didFinishNavigationInPrimaryMainFrame(Lcobalt/org/chromium/content_public/browser/NavigationHandle;)V\n    .locals 1'
assert header in s
s = s.replace(header, header + '\n    invoke-static {}, Llocal/ru/YouTubeAdBlock;->inject()V')
s += '''
.method public final primaryMainDocumentElementAvailable()V
    .locals 0
    invoke-static {}, Llocal/ru/YouTubeAdBlock;->inject()V
    return-void
.end method

.method public final titleWasSet(Ljava/lang/String;)V
    .locals 0
    invoke-static {p1}, Llocal/ru/YouTubeAdBlock;->title(Ljava/lang/String;)V
    return-void
.end method
'''
p.write_text(s)
p = root/'smali_classes2/dev/cobalt/coat/CobaltActivity.smali'
s = p.read_text()
old = '    invoke-super/range {p0 .. p1}, Ldev/cobalt/coat/BaseCobaltActivity;->onCreate(Landroid/os/Bundle;)V'
assert s.count(old) == 1
s = s.replace(old, old + '\n    invoke-static/range {p0 .. p0}, Llocal/ru/YouTubeAdBlock;->schedule(Landroid/app/Activity;)V')
p.write_text(s)
p = root/'AndroidManifest.xml'
s = p.read_text().replace('com.google.android.youtube.tv', args.package)
s = s.replace('</application>', '''<receiver android:name="local.ru.GoogleProcessGuard" android:exported="true" android:directBootAware="true"><intent-filter><action android:name="android.intent.action.LOCKED_BOOT_COMPLETED"/><action android:name="android.intent.action.BOOT_COMPLETED"/><action android:name="android.intent.action.MY_PACKAGE_REPLACED"/></intent-filter></receiver></application>''')
if 'android.permission.RECEIVE_BOOT_COMPLETED' not in s:
    s = s.replace('<application', '<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/><application', 1)
s = s.replace('android:extractNativeLibs="false"', 'android:extractNativeLibs="true"')
s = s.replace('android:label="@string/app_name"', 'android:label="YouTube Fix' + (' Test' if args.package.endswith('.adtest') else '') + '"')
p.write_text(s)

script = (source/'filter.js').read_text()
(root/'YouTubeAdBlockPayload.java').write_text(
    'package local.ru;\nfinal class YouTubeAdBlockPayload { static final String SCRIPT = ' +
    json.dumps(script, ensure_ascii=True) + '; }\n')
print('Patched YouTube TV 7.32.300')
