package org.chromium.chrome.browser.swiftra.faceguard;

import android.graphics.Bitmap;
import android.media.FaceDetector;

import java.nio.ShortBuffer;

/**
 * PRESENCE ONLY: counts frontal faces with the framework android.media.FaceDetector (no Play services, no model
 * file, no network). It does NOT identify whose face it is. Identity needs an embedding model (docs/plans/face-guard.md).
 */
final class PresenceFaceAnalyzer {
    static final int MAX_FACES = 3;
    /** Framework-documented FaceDetector.CONFIDENCE_THRESHOLD. */
    static final float MIN_CONFIDENCE = 0.4f;

    private FaceDetector mDetector;
    private Bitmap mBitmap;
    private int mWidth;
    private int mHeight;

    /** @return number of confident, reasonably large faces in the (already upright) gray frame. */
    int countFaces(FaceGrayConverter.Result frame) {
        if (mDetector == null || mWidth != frame.width || mHeight != frame.height) {
            release();
            mDetector = new FaceDetector(frame.width, frame.height, MAX_FACES);
            mBitmap = Bitmap.createBitmap(frame.width, frame.height, Bitmap.Config.RGB_565);
            mWidth = frame.width;
            mHeight = frame.height;
        }
        mBitmap.copyPixelsFromBuffer(ShortBuffer.wrap(frame.pixels));
        FaceDetector.Face[] faces = new FaceDetector.Face[MAX_FACES];
        int found = mDetector.findFaces(mBitmap, faces);
        float minEyes = Math.max(4f, frame.width * 0.05f);
        int count = 0;
        for (int i = 0; i < found && i < faces.length; i++) {
            FaceDetector.Face f = faces[i];
            if (f != null && f.confidence() >= MIN_CONFIDENCE && f.eyesDistance() >= minEyes) count++;
        }
        return count;
    }

    void release() {
        if (mBitmap != null) mBitmap.recycle();
        mBitmap = null;
        mDetector = null;
    }
}
