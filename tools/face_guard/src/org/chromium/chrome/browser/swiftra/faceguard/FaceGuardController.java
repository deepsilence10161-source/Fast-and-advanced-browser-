package org.chromium.chrome.browser.swiftra.faceguard;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.view.ViewGroup;

import org.chromium.chrome.browser.tab_ui.FaceGuardLockState;

/**
 * Face Guard glue (PRESENCE MODE): while enabled and the browser is in the foreground, the front camera must keep
 * seeing a face or the browser is covered by an opaque lock screen and the tab switcher is opened behind it.
 * All decisions come from FaceGuardPolicy (host-tested). Off by default. Never deletes any data.
 */
public final class FaceGuardController implements FaceCameraSource.Listener, FaceGuardOverlay.Actions {
    private static final String PREFS = "swiftra_face_guard";
    private static final String KEY_ENABLED = "enabled";
    static final int REQUEST_CAMERA = 0x4647;
    private static final long CAMERA_RETRY_MS = 3000;

    private static FaceGuardController sInstance;

    private final Handler mMain = new Handler(Looper.getMainLooper());
    private final FaceGuardPolicy mPolicy = new FaceGuardPolicy(FaceGuardPolicy.Config.defaults());
    private final Runnable mTick = this::render;
    private final Runnable mRetryCamera = this::retryCamera;
    private Activity mActivity;
    private FaceCameraSource mCamera;
    private FaceGuardOverlay mOverlay;
    private boolean mForeground;
    private boolean mCameraFailed;
    private boolean mCredentialPromptBroken;

    private FaceGuardController() {}

    // ------------------------------------------------------------------ static API
    public static boolean isEnabled(Context context) {
        return prefs(context).getBoolean(KEY_ENABLED, false);
    }

    public static void setEnabled(Context context, boolean enabled) {
        prefs(context).edit().putBoolean(KEY_ENABLED, enabled).apply();
        if (sInstance != null) sInstance.mMain.post(sInstance::refreshFromSettings);
    }

    public static boolean hasCameraPermission(Context context) {
        return context.checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED;
    }

    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static void onActivityResumed(Activity activity) {
        if (sInstance == null) sInstance = new FaceGuardController();
        sInstance.resume(activity);
    }

    public static void onActivityPaused(Activity activity) {
        if (sInstance != null) sInstance.pause(activity);
    }

    public static void onActivityDestroyed(Activity activity) {
        if (sInstance != null) sInstance.destroy(activity);
    }

    // ------------------------------------------------------------------ lifecycle
    private void resume(Activity activity) {
        mActivity = activity;
        mForeground = true;
        mCameraFailed = false;
        mCredentialPromptBroken = false;
        applySettingsAndState();
        if (mPolicy.evaluate(SystemClock.elapsedRealtime()).locked) {
            // Warm resume does not produce a lock "edge", so always (re)open the switcher while locked.
            mMain.post(() -> FaceGuardChromeBridge.showTabSwitcher(mActivity));
            mMain.postDelayed(() -> {
                if (mForeground && FaceGuardLockState.isLocked()) FaceGuardChromeBridge.showTabSwitcher(mActivity);
            }, 400);
        }
    }

    private void pause(Activity activity) {
        if (mActivity != activity) return;
        mForeground = false;
        mPolicy.onBackground();
        stopCamera();
        mMain.removeCallbacks(mRetryCamera);
        render();   // keeps/creates the overlay so the content is already covered when the app returns
    }

    private void destroy(Activity activity) {
        if (mActivity != activity) return;
        mMain.removeCallbacksAndMessages(null);
        stopCamera();
        removeOverlay();
        FaceGuardLockState.setLocked(false);
        mActivity = null;
        mForeground = false;
    }

    private void refreshFromSettings() {
        if (mActivity != null && mForeground) applySettingsAndState();
    }

    private void applySettingsAndState() {
        Activity a = mActivity;
        boolean enabled = isEnabled(a);
        mPolicy.setEnabled(enabled);
        mPolicy.setTemplate(FaceGuardPolicy.Template.OK);   // presence mode has no enrolled template
        mPolicy.setPermissionGranted(hasCameraPermission(a));
        if (mForeground) mPolicy.onForeground();
        if (enabled && mForeground && hasCameraPermission(a)) startCamera(); else stopCamera();
        render();
    }

    // ------------------------------------------------------------------ camera
    private void startCamera() {
        if (mCamera != null) return;
        mCamera = new FaceCameraSource(mActivity, this);
        mCamera.start();
    }

    private void stopCamera() {
        if (mCamera != null) mCamera.stop();
        mCamera = null;
    }

    private void retryCamera() {
        if (!mForeground || mActivity == null || !isEnabled(mActivity) || !hasCameraPermission(mActivity)) return;
        stopCamera();
        startCamera();
    }

    @Override
    public void onFrame(long atMs, boolean valid, int faces) {
        mMain.post(() -> {
            if (!mForeground) return;
            if (valid && mCameraFailed) {
                mCameraFailed = false;
                mPolicy.onCameraRecovered();
            }
            // PRESENCE: one visible face counts as "present"; any additional face is an "other face".
            mPolicy.onObservation(new FaceGuardPolicy.Observation(atMs, valid, faces >= 1, Math.max(0, faces - 1)));
            render();
        });
    }

    @Override
    public void onCameraFailed() {
        mMain.post(() -> {
            if (!mForeground) return;
            mCameraFailed = true;
            mPolicy.onCameraFailed();
            render();
            mMain.removeCallbacks(mRetryCamera);
            mMain.postDelayed(mRetryCamera, CAMERA_RETRY_MS);
        });
    }

    // ------------------------------------------------------------------ decision -> UI
    private void render() {
        if (mActivity == null) return;
        long now = SystemClock.elapsedRealtime();
        FaceGuardPolicy.Decision d = mPolicy.evaluate(now);
        FaceGuardPolicy.Action action = mPolicy.poll(now);
        FaceGuardLockState.setLocked(d.locked);
        if (d.locked) {
            showOverlay(d.reason);
            if (action == FaceGuardPolicy.Action.LOCK && mForeground) {
                FaceGuardChromeBridge.showTabSwitcher(mActivity);
            }
        } else {
            removeOverlay();
        }
        mMain.removeCallbacks(mTick);
        long deadline = mPolicy.nextDeadlineMs();
        if (deadline >= 0) mMain.postDelayed(mTick, Math.max(0, deadline - now));
    }

    private void showOverlay(FaceGuardPolicy.Reason reason) {
        ViewGroup content = mActivity.findViewById(android.R.id.content);
        if (content == null) return;
        if (mOverlay == null || mOverlay.getParent() != content) {
            removeOverlay();
            mOverlay = new FaceGuardOverlay(mActivity, this);
            content.addView(mOverlay, new ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        }
        mOverlay.bringToFront();
        mOverlay.show(reason, FaceGuardAuth.hasDeviceCredential(mActivity) && !mCredentialPromptBroken);
    }

    private void removeOverlay() {
        if (mOverlay != null && mOverlay.getParent() instanceof ViewGroup) {
            ((ViewGroup) mOverlay.getParent()).removeView(mOverlay);
        }
        mOverlay = null;
    }

    // ------------------------------------------------------------------ overlay actions
    @Override
    public void onUnlockWithDeviceCredential() {
        if (mActivity == null) return;
        boolean started = FaceGuardAuth.authenticate(mActivity, () -> {
            mPolicy.onDeviceCredentialSuccess();
            render();
        }, () -> { });
        if (!started) {
            // The platform could not show its credential prompt: never trap the owner behind the lock screen.
            mCredentialPromptBroken = true;
            render();
        }
    }

    @Override
    public void onGrantCamera() {
        if (mActivity != null) mActivity.requestPermissions(new String[] {Manifest.permission.CAMERA}, REQUEST_CAMERA);
    }

    @Override
    public void onOpenAppSettings() {
        if (mActivity == null) return;
        Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.fromParts("package", mActivity.getPackageName(), null));
        mActivity.startActivity(i);
    }

    @Override
    public void onTurnOff() {
        if (mActivity == null) return;
        // The overlay only offers this when the device has no credential, i.e. no stronger proof exists.
        setEnabled(mActivity, false);
    }
}
