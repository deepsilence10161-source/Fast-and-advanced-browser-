package org.chromium.chrome.browser.swiftra.gemini;

import android.app.Activity;

import androidx.preference.Preference;
import androidx.preference.PreferenceFragmentCompat;
import androidx.preference.TwoStatePreference;

import org.chromium.chrome.browser.browsing_data.SwiftraKeepSignin;
import org.chromium.chrome.browser.tab.TabLaunchType;
import org.chromium.chrome.browser.tabmodel.document.ChromeAsyncTabLauncher;

/**
 * Swiftra personal: "Gemini chat" entry in Settings.
 *
 * <p>Gemini runs on gemini.google.com in an ordinary Swiftra tab, signed in with ONE Google account through the normal
 * web sign-in. The chats, their memory and their history are kept by Google in that account (Gemini Apps Activity),
 * not by Swiftra, so nothing here stores or reads chat content. The switch below keeps the Google web sign-in when
 * browsing data is deleted, so the account stays linked; the chats themselves are never touched by Delete browsing data.
 */
public final class SwiftraGemini {
    public static final String KEY_OPEN = "swiftra_gemini";
    public static final String KEY_ACTIVITY = "swiftra_gemini_activity";
    public static final String KEY_KEEP = "swiftra_gemini_keep_signin";
    public static final String GEMINI_URL = "https://gemini.google.com/app";
    public static final String ACTIVITY_URL = "https://myactivity.google.com/product/gemini";

    private SwiftraGemini() {}

    public static void setUp(PreferenceFragmentCompat fragment, Activity activity) {
        if (activity == null) return;
        Preference open = fragment.findPreference(KEY_OPEN);
        if (open != null) {
            open.setOnPreferenceClickListener(
                    p -> {
                        openInTab(activity, GEMINI_URL);
                        return true;
                    });
        }
        Preference history = fragment.findPreference(KEY_ACTIVITY);
        if (history != null) {
            history.setOnPreferenceClickListener(
                    p -> {
                        openInTab(activity, ACTIVITY_URL);
                        return true;
                    });
        }
        Preference keep = fragment.findPreference(KEY_KEEP);
        if (keep instanceof TwoStatePreference) {
            TwoStatePreference toggle = (TwoStatePreference) keep;
            toggle.setChecked(SwiftraKeepSignin.isEnabled());
            toggle.setOnPreferenceChangeListener(
                    (p, newValue) -> {
                        SwiftraKeepSignin.setEnabled(Boolean.TRUE.equals(newValue));
                        return true;
                    });
        }
    }

    /** Three-dot menu entry: a new normal tab with Gemini, the menu closes by itself. */
    public static void openGemini() {
        new ChromeAsyncTabLauncher(/* incognito= */ false).launchUrl(GEMINI_URL, TabLaunchType.FROM_CHROME_UI);
    }

    /** Opens the page in a new, normal (not incognito) tab and leaves Settings so the tab is what the user sees. */
    static void openInTab(Activity activity, String url) {
        new ChromeAsyncTabLauncher(/* incognito= */ false).launchUrl(url, TabLaunchType.FROM_CHROME_UI);
        activity.finish();
    }
}
