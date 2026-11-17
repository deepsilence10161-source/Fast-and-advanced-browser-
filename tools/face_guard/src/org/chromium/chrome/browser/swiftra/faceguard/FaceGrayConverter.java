package org.chromium.chrome.browser.swiftra.faceguard;

/**
 * Pure luminance -> RGB565 gray conversion with clockwise rotation, so frames can be handed to
 * android.media.FaceDetector (which needs an upright RGB_565 bitmap of EVEN width). No Android dependency.
 */
public final class FaceGrayConverter {
    public static final class Result {
        public final short[] pixels;
        public final int width;
        public final int height;

        Result(short[] pixels, int width, int height) {
            this.pixels = pixels;
            this.width = width;
            this.height = height;
        }
    }

    private FaceGrayConverter() {}

    /**
     * @param y         luminance plane
     * @param rowStride bytes per source row (>= width)
     * @param rotation  clockwise degrees: 0, 90, 180 or 270
     */
    public static Result toRgb565(byte[] y, int width, int height, int rowStride, int rotation) {
        if (y == null || width <= 0 || height <= 0 || rowStride < width) {
            throw new IllegalArgumentException("bad frame geometry");
        }
        if (y.length < (long) (height - 1) * rowStride + width) {
            throw new IllegalArgumentException("luminance plane too small");
        }
        if (rotation != 0 && rotation != 90 && rotation != 180 && rotation != 270) {
            throw new IllegalArgumentException("rotation must be 0/90/180/270");
        }
        boolean swap = rotation == 90 || rotation == 270;
        int fullW = swap ? height : width;
        int outH = swap ? width : height;
        int outW = fullW & ~1;                       // FaceDetector requires an even width
        if (outW < 2 || outH < 1) throw new IllegalArgumentException("frame too small");
        short[] out = new short[outW * outH];
        for (int oy = 0; oy < outH; oy++) {
            for (int ox = 0; ox < outW; ox++) {
                int sx;
                int sy;
                switch (rotation) {
                    case 90:
                        sx = oy;
                        sy = height - 1 - ox;
                        break;
                    case 180:
                        sx = width - 1 - ox;
                        sy = height - 1 - oy;
                        break;
                    case 270:
                        sx = width - 1 - oy;
                        sy = ox;
                        break;
                    default:
                        sx = ox;
                        sy = oy;
                        break;
                }
                int g = y[sy * rowStride + sx] & 0xFF;
                out[oy * outW + ox] = (short) (((g >> 3) << 11) | ((g >> 2) << 5) | (g >> 3));
            }
        }
        return new Result(out, outW, outH);
    }

    /** Clockwise rotation that makes a FRONT camera frame upright (mirroring is irrelevant for detection). */
    public static int frontCameraRotation(int sensorOrientationDegrees, int displayRotationDegrees) {
        int r = (sensorOrientationDegrees + displayRotationDegrees) % 360;
        if (r < 0) r += 360;
        return (r / 90) * 90;
    }
}
