package local.ru;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import java.lang.reflect.Method;

/** Stock Dangbei DAST exceptions, restored on boot even without the RU launcher. */
public final class GoogleProcessGuard extends BroadcastReceiver {
    private static boolean protectedInProcess;
    public static synchronized boolean protect(Context context) {
        if (protectedInProcess) return true;
        try {
            Object dast = context.getSystemService("Dast");
            if (dast == null) throw new IllegalStateException("DAST unavailable");
            Method update = dast.getClass().getMethod("updateProcessWhite", String.class, boolean.class);
            for (String pkg : new String[]{"com.google.android.gms", "com.google.android.gsf"}) {
                context.getPackageManager().getApplicationInfo(pkg, 0);
                update.invoke(dast, pkg, true);
            }
            protectedInProcess = true;
            Log.w("YouTubeFix", "Google process protection applied");
            return true;
        } catch (Exception e) {
            Log.e("YouTubeFix", "Google process protection failed", e);
            return false;
        }
    }
    @Override public void onReceive(Context context, Intent intent) {
        String action = intent == null ? null : intent.getAction();
        if (Intent.ACTION_BOOT_COMPLETED.equals(action) || Intent.ACTION_LOCKED_BOOT_COMPLETED.equals(action)
                || Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)
                || (context.getPackageName() + ".PROTECT_GOOGLE").equals(action)) {
            setResultCode(protect(context) ? 1 : 0);
        }
    }
}
