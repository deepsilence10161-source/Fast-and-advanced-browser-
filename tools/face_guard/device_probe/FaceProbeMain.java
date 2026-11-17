import android.graphics.Bitmap;
import android.graphics.BitmapFactory;

import org.chromium.chrome.browser.swiftra.faceguard.FaceGrayConverter;
import org.chromium.chrome.browser.swiftra.faceguard.FaceProbeBridge;

import java.io.File;
import java.util.Arrays;

/**
 * Runs the REAL FaceGrayConverter + PresenceFaceAnalyzer (framework android.media.FaceDetector) on still images,
 * on a real Android runtime via app_process. Camera is not involved. Prints `FACE_PROBE <image> rot=<r> faces=<n>`.
 * Usage: app_process / FaceProbeMain <dir-with-images>
 */
public final class FaceProbeMain {
    static final int WIDTH = 320;

    public static void main(String[] args) {
        File[] files = new File(args[0]).listFiles();
        Arrays.sort(files);
        for (File f : files) {
            String n = f.getName();
            if (!(n.endsWith(".jpg") || n.endsWith(".png"))) continue;
            Bitmap src = BitmapFactory.decodeFile(f.getPath());
            if (src == null) {
                System.out.println("FACE_PROBE " + n + " DECODE_FAILED");
                continue;
            }
            int h = Math.round(src.getHeight() * (WIDTH / (float) src.getWidth()));
            Bitmap scaled = Bitmap.createScaledBitmap(src, WIDTH, h, true);
            byte[] y = new byte[WIDTH * h];
            int[] px = new int[WIDTH * h];
            scaled.getPixels(px, 0, WIDTH, 0, 0, WIDTH, h);
            for (int i = 0; i < px.length; i++) {
                int c = px[i];
                y[i] = (byte) (((c >> 16 & 0xFF) * 299 + (c >> 8 & 0xFF) * 587 + (c & 0xFF) * 114) / 1000);
            }
            for (int rot : new int[] {0, 90, 180, 270}) {
                // Build the "sensor" frame that the converter must turn back into the upright image.
                byte[] sensor = rotateClockwise(y, WIDTH, h, (360 - rot) % 360);
                boolean swap = rot == 90 || rot == 270;
                int sw = swap ? h : WIDTH;
                int sh = swap ? WIDTH : h;
                FaceGrayConverter.Result r = FaceGrayConverter.toRgb565(sensor, sw, sh, sw, rot);
                System.out.println("FACE_PROBE " + n + " rot=" + rot + " faces=" + FaceProbeBridge.count(r));
            }
        }
        System.out.println("FACE_PROBE_DONE");
    }

    static byte[] rotateClockwise(byte[] s, int w, int h, int degrees) {
        if (degrees == 0) return s.clone();
        boolean swap = degrees == 90 || degrees == 270;
        int ow = swap ? h : w;
        int oh = swap ? w : h;
        byte[] o = new byte[ow * oh];
        for (int oy = 0; oy < oh; oy++) {
            for (int ox = 0; ox < ow; ox++) {
                int sx;
                int sy;
                if (degrees == 90) { sx = oy; sy = h - 1 - ox; }
                else if (degrees == 180) { sx = w - 1 - ox; sy = h - 1 - oy; }
                else { sx = w - 1 - oy; sy = ox; }
                o[oy * ow + ox] = s[sy * w + sx];
            }
        }
        return o;
    }
}
