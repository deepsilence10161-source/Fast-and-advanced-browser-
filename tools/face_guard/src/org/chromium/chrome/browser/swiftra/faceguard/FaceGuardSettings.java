package org.chromium.chrome.browser.swiftra.faceguard;

import android.Manifest;
import android.app.Activity;

import androidx.preference.Preference;
import androidx.preference.PreferenceFragmentCompat;
import androidx.preference.TwoStatePreference;

/** Wires the "Face Guard" switch in Settings > Privacy and security. Off by default. */
public final class FaceGuardSettings {
    public static final String KEY = "swiftra_face_guard";

    private FaceGuardSettings() {}

    public static void setUp(PreferenceFragmentCompat fragment, Activity activity) {
        Preference p = fragment.findPreference(KEY);
        if (!(p instanceof TwoStatePreference) || activity == null) return;
        TwoStatePreference toggle = (TwoStatePreference) p;
        toggle.setChecked(FaceGuardController.isEnabled(activity));
        toggle.setOnPreferenceChangeListener((pref, newValue) -> {
            boolean on = Boolean.TRUE.equals(newValue);
            if (on) {
                FaceGuardController.setEnabled(activity, true);
                if (!FaceGuardController.hasCameraPermission(activity)) {
                    activity.requestPermissions(new String[] {Manifest.permission.CAMERA},
                            FaceGuardController.REQUEST_CAMERA);
                }
                return true;
            }
            // Turning the guard OFF needs the device credential whenever the device has one.
            if (!FaceGuardAuth.hasDeviceCredential(activity)) {
                FaceGuardController.setEnabled(activity, false);
                return true;
            }
            boolean started = FaceGuardAuth.authenticate(activity, () -> {
                FaceGuardController.setEnabled(activity, false);
                toggle.setChecked(false);
            }, () -> { });
            if (!started) {
                // No way to verify the owner on this device: refusing would make the switch impossible to turn off.
                FaceGuardController.setEnabled(activity, false);
                return true;
            }
            return false;   // stays ON until the credential is confirmed
        });
    }
}
