package org.chromium.chrome.browser.swiftra.faceguard;

/** Probe-only public door to the package-private PresenceFaceAnalyzer. Never shipped in the APK. */
public final class FaceProbeBridge {
    private FaceProbeBridge() {}

    public static int count(FaceGrayConverter.Result frame) {
        PresenceFaceAnalyzer a = new PresenceFaceAnalyzer();
        try {
            return a.countFaces(frame);
        } finally {
            a.release();
        }
    }
}
