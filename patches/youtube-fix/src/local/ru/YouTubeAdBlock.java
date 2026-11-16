package local.ru;

import android.util.Log;
import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import java.lang.ref.WeakReference;
import java.lang.reflect.Field;
import java.lang.reflect.Method;

/** Local adaptation of the navigation observer technique from FaroTV/ysamjo, GPL-3.0. */
public final class YouTubeAdBlock {
    private static Object contents;
    private static Field pointer;
    private static Method evaluate;
    private static Object observer;
    public static void schedule(Activity activity) {
        GoogleProcessGuard.protect(activity);
        Log.w("YouTubeFix", "Injector scheduled");
        final WeakReference<Activity> reference = new WeakReference<>(activity);
        final Handler handler = new Handler(Looper.getMainLooper());
        handler.postDelayed(new Runnable() {
            int count;
            public void run() {
                Activity owner = reference.get();
                if (owner == null || owner.isDestroyed() || owner.isFinishing()) return;
                try {
                    Object current = owner.getClass().getMethod("getActiveWebContents").invoke(owner);
                    if (current != null && current != contents) {
                        setContents(current);
                        Class<?> web = Class.forName("cobalt.org.chromium.content_public.browser.WebContents");
                        observer = Class.forName("dev.cobalt.shell.StartupGuardNavigationObserver")
                            .getConstructor(web).newInstance(current);
                    }
                    if (current != null) inject();
                } catch (Throwable e) { if (count < 3) Log.e("YouTubeFix", "Page unavailable", e); }
                if (++count < 120) handler.postDelayed(this, 250);
                else handler.postDelayed(this, 5000);
            }
        }, 100);
    }
    public static void setContents(Object value) {
        contents = value;
        pointer = null;
    }
    public static void inject() {
        try {
            if (contents == null) return;
            if (pointer == null) {
                for (Field f : contents.getClass().getDeclaredFields()) {
                    if (f.getType() == long.class) {
                        if (pointer != null) throw new IllegalStateException("Ambiguous native pointer");
                        pointer = f;
                    }
                }
                if (pointer == null) throw new IllegalStateException("No native pointer");
                pointer.setAccessible(true);
            }
            long address = pointer.getLong(contents);
            if (address == 0) return;
            if (evaluate == null) {
                evaluate = Class.forName("org.jni_zero.GEN_JNI").getDeclaredMethod(
                    "cobalt_org_chromium_content_browser_webcontents_WebContentsImpl_evaluateJavaScript",
                    long.class, Object.class, Object.class);
                evaluate.setAccessible(true);
            }
            evaluate.invoke(null, address, YouTubeAdBlockPayload.SCRIPT, null);
        } catch (Throwable e) {
            Log.e("YouTubeFix", "Filter injection failed", e);
        }
    }
    public static void title(String title) {
        if (title != null && title.startsWith("ytfix:")) Log.w("YouTubeFix", title);
    }
}
