package org.chromium.chrome.browser.swiftra.faceguard;

import android.app.Activity;
import android.app.KeyguardManager;
import android.content.Context;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.os.Build;
import android.os.CancellationSignal;

/** Device credential (PIN/pattern/password) check via the framework BiometricPrompt: no extra dependency. */
final class FaceGuardAuth {
    private FaceGuardAuth() {}

    static boolean hasDeviceCredential(Context context) {
        KeyguardManager km = (KeyguardManager) context.getSystemService(Context.KEYGUARD_SERVICE);
        return km != null && km.isDeviceSecure();
    }

    /** Runs onSuccess only after the platform confirms the device credential; otherwise onFailure (never both). */
    static void authenticate(Activity activity, Runnable onSuccess, Runnable onFailure) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R || !hasDeviceCredential(activity)) {
            onFailure.run();
            return;
        }
        try {
            BiometricPrompt prompt = new BiometricPrompt.Builder(activity)
                    .setTitle("Face Guard")
                    .setDescription("Confirm your device PIN, pattern or password")
                    .setAllowedAuthenticators(BiometricManager.Authenticators.DEVICE_CREDENTIAL)
                    .build();
            prompt.authenticate(new CancellationSignal(), activity.getMainExecutor(),
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
        } catch (RuntimeException e) {
            onFailure.run();
        }
    }
}
