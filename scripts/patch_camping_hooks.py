"""Add CampingApps hooks to the decoded 2.4.2 launcher (apktool directory)."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
base = root / 'smali_classes6/com/strive/outdoors_home_business/ui/view/bottom'

def edit_method(path, signature, transform):
    text = path.read_text()
    start = text.index('.method ' + signature)
    end = text.index('.end method', start)
    original = text[start:end]
    changed = transform(original)
    path.write_text(text[:start] + changed + text[end:])

row = base / 'OutDoorBottomRecyclerView.smali'
item = base / 'OutDoorBottomItemView.smali'
if 'Llocal/ru/CampingApps;' in row.read_text():
    raise SystemExit('Camping hooks already installed')
edit_method(row, 'public final setNavItemList(Ljava/util/List;)V', lambda s: s.replace(
    '    .line 1\n',
    '    invoke-static {p0, p1}, Llocal/ru/CampingApps;->decorate(Landroid/view/View;Ljava/util/List;)Ljava/util/List;\n'
    '    move-result-object p1\n\n    .line 1\n', 1))
edit_method(item, 'public final X(Lcom/strive/outdoors_home_business/entity/OutDoorsNavItemVm;I)V', lambda s: s.replace(
    '    .line 1\n', '    invoke-static {p0}, Llocal/ru/CampingApps;->beforeBind(Landroid/view/View;)V\n\n    .line 1\n', 1).replace(
    '    return-void', '    invoke-static {p0}, Llocal/ru/CampingApps;->afterBind(Landroid/view/View;)V\n    return-void'))
edit_method(item, 'public onClick(Landroid/view/View;)V', lambda s: s.replace(
    '    .line 1\n',
    '    invoke-static {p0}, Llocal/ru/CampingApps;->click(Landroid/view/View;)Z\n'
    '    move-result v0\n    if-eqz v0, :ru_native_click\n    return-void\n    :ru_native_click\n\n    .line 1\n', 1))
edit_method(item, 'public onFocusChanged(ZILandroid/graphics/Rect;)V', lambda s: s.replace(
    '    return-void', '    invoke-virtual {p0}, Landroid/view/View;->invalidate()V\n    return-void'))
edit_method(row, 'public onDetachedFromWindow()V', lambda s: s.replace(
    '    return-void', '    invoke-static {p0}, Llocal/ru/CampingApps;->detached(Landroid/view/View;)V\n    return-void'))
item.write_text(item.read_text() + '\n.method public dispatchKeyEvent(Landroid/view/KeyEvent;)Z\n    .locals 1\n    invoke-static {p0, p1}, Llocal/ru/CampingApps;->key(Landroid/view/View;Landroid/view/KeyEvent;)Z\n    move-result v0\n    if-eqz v0, :ru_native_key\n    return v0\n    :ru_native_key\n    invoke-super {p0, p1}, Lcom/lerad/lerad_base_view/base/BFrameLayout;->dispatchKeyEvent(Landroid/view/KeyEvent;)Z\n    move-result v0\n    return v0\n.end method\n')
activity = next(root.glob('smali*/com/dangbei/leard/leradlauncher/ui/splash/SplashActivity.smali'))
edit_method(activity, 'public dispatchKeyEvent(Landroid/view/KeyEvent;)Z', lambda s: s.replace('    .line 1\n', '    invoke-static {p0, p1}, Llocal/ru/CampingApps;->activityKey(Landroid/app/Activity;Landroid/view/KeyEvent;)Z\n    move-result v0\n    if-eqz v0, :ru_native_activity_key\n    return v0\n    :ru_native_activity_key\n\n    .line 1\n', 1))

item.write_text(item.read_text() + '\n.method public dispatchKeyEventPreIme(Landroid/view/KeyEvent;)Z\n    .locals 1\n    invoke-static {p0, p1}, Llocal/ru/CampingApps;->key(Landroid/view/View;Landroid/view/KeyEvent;)Z\n    move-result v0\n    if-eqz v0, :ru_native_preime\n    return v0\n    :ru_native_preime\n    invoke-super {p0, p1}, Lcom/lerad/lerad_base_view/base/BFrameLayout;->dispatchKeyEventPreIme(Landroid/view/KeyEvent;)Z\n    move-result v0\n    return v0\n.end method\n')

scene = base.parent / 'bottom2/OutDoorTypeItemView.smali'
source = scene.read_text()
needle = '    invoke-virtual {v0, v1}, Landroid/widget/ImageView;->setImageResource(I)V'
assert source.count(needle) == 1
scene.write_text(source.replace(needle, needle + '\n    invoke-static {v0}, Llocal/ru/CampingApps;->themeBadge(Landroid/widget/ImageView;)V'))

print('Camping hooks installed')
