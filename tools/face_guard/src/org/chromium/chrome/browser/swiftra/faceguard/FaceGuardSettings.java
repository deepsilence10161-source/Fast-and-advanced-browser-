package org.chromium.chrome.browser.swiftra.faceguard;

import android.Manifest;
import android.app.Activity;

import android.widget.Toast;

import androidx.preference.Preference;
import androidx.preference.PreferenceFragmentCompat;
import androidx.preference.PreferenceGroup;
import androidx.preference.SwitchPreferenceCompat;
import androidx.preference.TwoStatePreference;

/** Wires the "Face Guard" switch in Settings > Privacy and security. Off by default. */
public final class FaceGuardSettings {
    public static final String KEY = "swiftra_face_guard";
    public static final String KEY_OWNER_ONLY = "swiftra_face_guard_owner_only";

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
        addOwnerOnlySwitch(fragment, activity, toggle);
    }

    /** Second switch, built in code (no XML edit): owner-only mode skips the camera and uses BiometricPrompt only. */
    private static void addOwnerOnlySwitch(PreferenceFragmentCompat fragment, Activity activity, Preference anchor) {
        PreferenceGroup parent = anchor.getParent();
        if (parent == null || fragment.findPreference(KEY_OWNER_ONLY) != null) return;
        SwitchPreferenceCompat owner = new SwitchPreferenceCompat(activity);
        owner.setKey(KEY_OWNER_ONLY);
        owner.setPersistent(false);
        owner.setIconSpaceReserved(false);
        owner.setTitle("Face Guard: owner unlock only");
        owner.setSummary("Skips the camera. Only your fingerprint, face unlock or device PIN opens the browser. "
                + "Needs a device PIN, pattern or password.");
        owner.setChecked(FaceGuardController.isOwnerOnly(activity));
        owner.setOnPreferenceChangeListener((pref, newValue) -> {
            if (Boolean.TRUE.equals(newValue)) {
                if (!FaceGuardAuth.hasDeviceCredential(activity)) {
                    Toast.makeText(activity, "Set a device PIN, pattern or password first.", Toast.LENGTH_LONG).show();
                    return false;   // never switch on a mode that could lock the owner out
                }
                FaceGuardController.setOwnerOnly(activity, true);
                return true;
            }
            // Going back to the weaker mode needs the owner check whenever the device has one.
            if (!FaceGuardAuth.hasDeviceCredential(activity)) {
                FaceGuardController.setOwnerOnly(activity, false);
                return true;
            }
            boolean started = FaceGuardAuth.authenticate(activity, () -> {
                FaceGuardController.setOwnerOnly(activity, false);
                owner.setChecked(false);
            }, () -> { });
            if (!started) {
                FaceGuardController.setOwnerOnly(activity, false);
                return true;
            }
            return false;
        });
        parent.addPreference(owner);
    }
}
