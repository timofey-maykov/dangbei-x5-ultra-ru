package local.ru;

import android.accessibilityservice.AccessibilityService;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.TextView;
import java.util.List;
import java.util.ArrayList;
import android.view.accessibility.AccessibilityEvent;

/** Russian labels for the vendor's recent-app window. Never takes input focus. */
public final class RecentHints implements Runnable {
    private static RecentHints current;
    private final AccessibilityService service;
    private final WindowManager windows;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView hints, name, notice;
    private final Runnable clearNotice = new Runnable() { public void run() { remove(notice); notice=null; } };
    private final Rect hintsBounds = new Rect(), nameBounds = new Rect();
    private boolean disposed;

    private RecentHints(AccessibilityService service) {
        this.service = service;
        windows = (WindowManager) service.getSystemService(AccessibilityService.WINDOW_SERVICE);
    }

    public static void update(AccessibilityService service) {
        if (current == null || current.service != service) {
            if (current != null) current.dispose();
            current = new RecentHints(service);
        }
        current.handler.removeCallbacks(current);
        current.handler.post(current);
    }

    public static void event(AccessibilityService service, AccessibilityEvent event) {
        update(service);
        if(event.getEventType()!=AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED ||
                !"com.dangbei.systemui".contentEquals(event.getPackageName()==null?"":event.getPackageName())) return;
        String translated=null;
        for(CharSequence text:event.getText()) {
            if("当前无后台应用运行".contentEquals(text)) translated="Нет открытых приложений";
            if("已清理至最佳状态".contentEquals(text)) translated="Приложения закрыты";
        }
        if(translated==null) return;
        current.handler.removeCallbacks(current.clearNotice);
        current.clearNotice.run();
        float scale=service.getResources().getDisplayMetrics().widthPixels/1920f;
        Rect r=new Rect((int)(640*scale),(int)(874*scale),(int)(1280*scale),(int)(990*scale));
        current.notice=current.label(translated,r,30*scale,0xff303746);
        current.handler.postDelayed(current.clearNotice,2400);
    }

    public static void close(AccessibilityService service) {
        if (current != null && current.service == service) {
            current.dispose();
            current = null;
        }
    }

    private void dispose() {
        disposed = true;
        handler.removeCallbacks(this);
        handler.removeCallbacks(clearNotice);
        clearNotice.run();
        hide();
    }

    private void remove(TextView view) {
        if (view != null) {
            try { windows.removeViewImmediate(view); }
            catch (IllegalArgumentException ignored) { }
        }
    }

    private void hide() {
        remove(hints); remove(name);
        hints = null; name = null;
        hintsBounds.setEmpty(); nameBounds.setEmpty();
    }

    private TextView label(String text, Rect bounds, float size, int background) {
        TextView view = new TextView(service);
        view.setText(text);
        view.setTextColor(Color.WHITE);
        view.setTextSize(TypedValue.COMPLEX_UNIT_PX, size);
        view.setGravity(Gravity.CENTER);
        view.setSingleLine(true);
        view.setEllipsize(TextUtils.TruncateAt.END);
        view.setImportantForAccessibility(TextView.IMPORTANT_FOR_ACCESSIBILITY_NO);
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(background);
        shape.setCornerRadius(size / 2);
        view.setBackground(shape);
        windows.addView(view, params(bounds));
        return view;
    }

    private static WindowManager.LayoutParams params(Rect bounds) {
        WindowManager.LayoutParams p = new WindowManager.LayoutParams(
            bounds.width(), bounds.height(), WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE |
            WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE |
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT);
        p.gravity = Gravity.TOP | Gravity.LEFT;
        p.x = bounds.left; p.y = bounds.top;
        p.setTitle("Русские подсказки последних приложений");
        return p;
    }

    private static Rect bounds(List<AccessibilityNodeInfo> nodes) {
        Rect out = null;
        for (AccessibilityNodeInfo node : nodes) {
            if (out == null && node.isVisibleToUser()) {
                out = new Rect(); node.getBoundsInScreen(out);
            }
            node.recycle();
        }
        return out;
    }

    private static String translatedName(String original) {
        if ("全部清理".equals(original)) return "Закрыть всё";
        if ("氛围".equals(original)) return "Заставка";
        if ("设置".equals(original)) return "Настройки";
        if ("当贝投屏".equals(original)) return "Трансляция";
        if ("当贝市场".equals(original)) return "Магазин Dangbei";
        if ("当贝播放器".equals(original)) return "Плеер Dangbei";
        if ("文件管理".equals(original)) return "Файлы";
        if ("云相册".equals(original) || "当贝云相册".equals(original)) return "Фото";
        return null;
    }

    @Override public void run() {
        if (disposed) return;
        AccessibilityNodeInfo root = service.getRootInActiveWindow();
        boolean visible = false;
        try {
            if (root == null || !"com.dangbei.systemui".contentEquals(
                    root.getPackageName() == null ? "" : root.getPackageName())) {
                hide(); return;
            }
            Rect open = bounds(root.findAccessibilityNodeInfosByText("打开应用"));
            Rect close = bounds(root.findAccessibilityNodeInfosByText("关闭应用"));
            if (open == null || close == null) { hide(); return; }
            visible = true;
            float scale = service.getResources().getDisplayMetrics().widthPixels / 1920f;
            int middle = (open.left + close.right) / 2;
            Rect position = new Rect(middle - (int)(300 * scale), open.top - (int)(12 * scale),
                                     middle + (int)(300 * scale), open.bottom + (int)(12 * scale));
            if (hints == null) {
                hints = label("OK — Открыть      ↑ — Закрыть", position, 28 * scale, 0xff202c38);
                hintsBounds.set(position);
            } else if (!hintsBounds.equals(position)) {
                windows.updateViewLayout(hints, params(position)); hintsBounds.set(position);
            }
            List<AccessibilityNodeInfo> names = new ArrayList<>(root.findAccessibilityNodeInfosByViewId(
                    "com.dangbei.systemui:id/app_name"));
            names.addAll(root.findAccessibilityNodeInfosByViewId("com.dangbei.systemui:id/close_name"));
            Rect titlePosition = null;
            String title = null;
            for (AccessibilityNodeInfo node : names) {
                String translated = translatedName(String.valueOf(node.getText()));
                if (title == null && translated != null && node.isVisibleToUser()) {
                    title = translated; titlePosition = new Rect();
                    node.getBoundsInScreen(titlePosition);
                }
                node.recycle();
            }
            String help = "Закрыть всё".equals(title) ? "OK — Закрыть всё" : "OK — Открыть      ↑ — Закрыть";
            if (!help.contentEquals(hints.getText())) hints.setText(help);
            if (title == null) { remove(name); name = null; nameBounds.setEmpty(); }
            else if (name == null) {
                name = label(title, titlePosition, 30 * scale, 0xff6b7080);
                nameBounds.set(titlePosition);
            } else {
                if (!title.contentEquals(name.getText())) name.setText(title);
                if (!nameBounds.equals(titlePosition)) {
                    windows.updateViewLayout(name, params(titlePosition)); nameBounds.set(titlePosition);
                }
            }
        } catch (RuntimeException e) {
            hide();
            android.util.Log.w("RU-RecentHints", "Could not update recent-app labels", e);
        } finally {
            if (root != null) root.recycle();
            if (visible && !disposed) handler.postDelayed(this, 300);
        }
    }
}
