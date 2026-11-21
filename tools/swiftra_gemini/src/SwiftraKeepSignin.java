package org.chromium.chrome.browser.browsing_data;

import org.chromium.base.ContextUtils;

import java.util.Arrays;

/**
 * Swiftra personal: keeps the Google web sign-in when browsing data is deleted.
 *
 * <p>Gemini chats are stored by Google in the signed-in account, so they are unaffected either way; this only decides
 * whether the browser is signed out of Google after "Delete browsing data". When on, google.com is passed to the
 * deletion as an excluded registrable domain: its cookies, site storage and cache entries are kept. History, other
 * sites and every other data type are deleted as before (the history backend ignores the domain filter).
 */
public final class SwiftraKeepSignin {
    public static final String PREF = "swiftra_keep_google_signin";
    public static final String DOMAIN = "google.com";

    private SwiftraKeepSignin() {}

    public static boolean isEnabled() {
        return ContextUtils.getAppSharedPreferences().getBoolean(PREF, true);
    }

    public static void setEnabled(boolean enabled) {
        ContextUtils.getAppSharedPreferences().edit().putBoolean(PREF, enabled).apply();
    }

    /** The domains to exclude from a deletion: the caller's list plus google.com when the switch is on. */
    public static String[] withKeptDomains(String[] excluded) {
        if (!isEnabled()) return excluded;
        if (excluded == null) return new String[] {DOMAIN};
        for (String d : excluded) {
            if (DOMAIN.equals(d)) return excluded;
        }
        String[] out = Arrays.copyOf(excluded, excluded.length + 1);
        out[excluded.length] = DOMAIN;
        return out;
    }
}
