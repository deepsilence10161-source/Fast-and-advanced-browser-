package org.chromium.chrome.browser.swiftra.faceguard;

import android.app.Activity;

import org.chromium.chrome.browser.ChromeTabbedActivity;
import org.chromium.chrome.browser.compositor.layouts.LayoutManagerChrome;
import org.chromium.chrome.browser.layouts.LayoutType;
import org.chromium.chrome.browser.tabmodel.TabModel;
import org.chromium.chrome.browser.tabmodel.TabModelSelector;

/** The ONLY Face Guard class that touches Chromium browser internals (keeps the patch surface small). */
final class FaceGuardChromeBridge {
    private FaceGuardChromeBridge() {}

    /** Opens the tab switcher (Hub layout in Chromium 155). Safe to call repeatedly or before layouts exist. */
    static void showTabSwitcher(Activity activity) {
        if (!(activity instanceof ChromeTabbedActivity)) return;
        try {
            ChromeTabbedActivity tabbed = (ChromeTabbedActivity) activity;
            // Opening the Hub before the tab state is restored and a tab is selected crashes the tab list (activePosition -1,
            // seen on a real device run). Until then the opaque overlay alone hides the page; the caller retries.
            TabModelSelector selector = tabbed.getTabModelSelector();
            if (selector == null || !selector.isTabStateInitialized()) return;
            TabModel model = selector.getCurrentModel();
            if (model == null || model.getCount() == 0 || model.index() < 0) return;
            LayoutManagerChrome layoutManager = tabbed.getLayoutManager();
            if (layoutManager.getActiveLayoutType() != LayoutType.HUB) {
                layoutManager.showLayout(LayoutType.HUB, /* animate= */ false);
            }
        } catch (RuntimeException e) {
            // Layouts not ready yet (very early startup): the opaque overlay still hides everything.
        }
    }
}
