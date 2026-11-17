package org.chromium.chrome.browser.swiftra.faceguard;

import android.app.Activity;

import org.chromium.chrome.browser.ChromeTabbedActivity;
import org.chromium.chrome.browser.compositor.layouts.LayoutManagerChrome;
import org.chromium.chrome.browser.layouts.LayoutType;

/** The ONLY Face Guard class that touches Chromium browser internals (keeps the patch surface small). */
final class FaceGuardChromeBridge {
    private FaceGuardChromeBridge() {}

    /** Opens the tab switcher (Hub layout in Chromium 155). Safe to call repeatedly or before layouts exist. */
    static void showTabSwitcher(Activity activity) {
        if (!(activity instanceof ChromeTabbedActivity)) return;
        try {
            LayoutManagerChrome layoutManager = ((ChromeTabbedActivity) activity).getLayoutManager();
            if (layoutManager.getActiveLayoutType() != LayoutType.HUB) {
                layoutManager.showLayout(LayoutType.HUB, /* animate= */ false);
            }
        } catch (RuntimeException e) {
            // Layouts not ready yet (very early startup): the opaque overlay still hides everything.
        }
    }
}
