// Swiftra personal development build. Part of the opt-in Face Guard layer (docs/plans/face-guard.md).
package org.chromium.chrome.browser.tab_ui;

/**
 * Process-wide "Face Guard is locked" flag. It lives in the tab_ui module so TabContentManager (same module)
 * can refuse to hand out tab thumbnails while locked, without a dependency cycle on chrome/android.
 * Defence in depth only: the opaque lock overlay is what actually hides content.
 */
public final class FaceGuardLockState {
    private static volatile boolean sLocked;

    private FaceGuardLockState() {}

    public static boolean isLocked() {
        return sLocked;
    }

    public static void setLocked(boolean locked) {
        sLocked = locked;
    }
}
