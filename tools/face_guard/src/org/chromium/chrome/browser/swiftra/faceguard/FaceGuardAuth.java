package org.chromium.chrome.browser.swiftra.faceguard;

import android.app.Activity;
import android.app.KeyguardManager;
import android.content.Context;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.os.Build;
import android.os.CancellationSignal;

/**
 * Owner check via the framework BiometricPrompt: no extra dependency. Since Android 11 the prompt accepts the OWNER'S
 * enrolled biometric (the phone's own fingerprint / face unlock, with the vendor's liveness) OR the device PIN, pattern
 * or password. That is the identity step Face Guard itself cannot do: the camera path only sees that a face is present.
 */
final class FaceGuardAuth {
    private FaceGuardAuth() {}

    static boolean hasDeviceCredential(Context context) {
        KeyguardManager km = (KeyguardManager) context.getSystemService(Context.KEYGUARD_SERVICE);
        return km != null && km.isDeviceSecure();
    }

    /**
     * Shows the platform credential prompt. onSuccess runs only after the platform confirms the credential; onFailure
     * runs on error/cancel. Returns false (and runs neither) when the prompt could not even be started, so the caller
     * can offer a non-credential way out instead of locking the owner out.
     */
    @SuppressWarnings("deprecation")
    static boolean authenticate(Activity activity, Runnable onSuccess, Runnable onFailure) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q || !hasDeviceCredential(activity)) return false;
        try {
            BiometricPrompt.Builder builder = new BiometricPrompt.Builder(activity)
                    .setTitle("Face Guard")
                    .setDescription("Confirm with your fingerprint, face or device PIN");
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                // Weak-class biometrics (what most phones' face unlock is) or the device credential; the credential is always there,
                // so a device without an enrolled biometric behaves exactly as before.
                builder.setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK
                        | BiometricManager.Authenticators.DEVICE_CREDENTIAL);
            } else {
                builder.setDeviceCredentialAllowed(true);   // Android 10: the only way to ask for the device credential
            }
            builder.build().authenticate(new CancellationSignal(), activity.getMainExecutor(),
                    new BiometricPrompt.AuthenticationCallback() {
                        @Override
                        public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result) {
                            onSuccess.run();
                        }

                        @Override
                        public void onAuthenticationError(int errorCode, CharSequence errString) {
                            onFailure.run();
                        }
                    });
            return true;
        } catch (RuntimeException e) {
            return false;
        }
    }
}
