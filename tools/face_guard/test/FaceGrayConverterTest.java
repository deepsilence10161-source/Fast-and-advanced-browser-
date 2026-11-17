import org.chromium.chrome.browser.swiftra.faceguard.FaceGrayConverter;

public final class FaceGrayConverterTest {
    static int n = 0;
    static void check(boolean ok, String what) {
        n++;
        if (!ok) { System.out.println("FAIL: " + what); System.exit(1); }
    }
    static short g(int v) { return (short) (((v >> 3) << 11) | ((v >> 2) << 5) | (v >> 3)); }

    public static void main(String[] a) {
        // 4 wide x 2 high, rowStride 6 (two padding bytes per row that must never be read as pixels)
        byte[] y = new byte[]{
            10, 20, 30, 40, 99, 99,
            50, 60, 70, 80, 99, 99};
        FaceGrayConverter.Result r0 = FaceGrayConverter.toRgb565(y, 4, 2, 6, 0);
        check(r0.width == 4 && r0.height == 2, "rot0 dims");
        short[] e0 = {g(10), g(20), g(30), g(40), g(50), g(60), g(70), g(80)};
        check(java.util.Arrays.equals(r0.pixels, e0), "rot0 pixels (stride padding skipped)");

        FaceGrayConverter.Result r90 = FaceGrayConverter.toRgb565(y, 4, 2, 6, 90);   // out 2x4
        check(r90.width == 2 && r90.height == 4, "rot90 dims");
        // clockwise 90: first output row = left column read bottom->top = 50,10
        short[] e90 = {g(50), g(10), g(60), g(20), g(70), g(30), g(80), g(40)};
        check(java.util.Arrays.equals(r90.pixels, e90), "rot90 pixels");

        FaceGrayConverter.Result r180 = FaceGrayConverter.toRgb565(y, 4, 2, 6, 180);
        short[] e180 = {g(80), g(70), g(60), g(50), g(40), g(30), g(20), g(10)};
        check(java.util.Arrays.equals(r180.pixels, e180), "rot180 pixels");

        FaceGrayConverter.Result r270 = FaceGrayConverter.toRgb565(y, 4, 2, 6, 270);  // out 2x4
        check(r270.width == 2 && r270.height == 4, "rot270 dims");
        // counter-clockwise 90: first output row = right column read top->bottom = 40,80
        short[] e270 = {g(40), g(80), g(30), g(70), g(20), g(60), g(10), g(50)};
        check(java.util.Arrays.equals(r270.pixels, e270), "rot270 pixels");

        // odd width is cropped to even (FaceDetector requirement)
        byte[] odd = new byte[5 * 2];
        for (int i = 0; i < odd.length; i++) odd[i] = (byte) (i * 10);
        FaceGrayConverter.Result ro = FaceGrayConverter.toRgb565(odd, 5, 2, 5, 0);
        check(ro.width == 4 && ro.height == 2 && ro.pixels.length == 8, "odd width cropped to even");
        FaceGrayConverter.Result ro90 = FaceGrayConverter.toRgb565(odd, 5, 2, 5, 90);  // out would be 2 wide x 5 high
        check(ro90.width == 2 && ro90.height == 5, "rotated dims stay even in width");

        // gray encoding bounds
        byte[] ext = {0, (byte) 255, (byte) 128, 64};
        FaceGrayConverter.Result re = FaceGrayConverter.toRgb565(ext, 4, 1, 4, 0);
        check(re.pixels[0] == 0 && re.pixels[1] == (short) 0xFFFF, "black and white extremes");
        check(re.pixels[2] == g(128) && re.pixels[3] == g(64), "mid greys");

        // invalid input is rejected, never silently converted
        int threw = 0;
        try { FaceGrayConverter.toRgb565(y, 4, 2, 3, 0); } catch (IllegalArgumentException e) { threw++; }
        try { FaceGrayConverter.toRgb565(new byte[3], 4, 2, 6, 0); } catch (IllegalArgumentException e) { threw++; }
        try { FaceGrayConverter.toRgb565(y, 4, 2, 6, 45); } catch (IllegalArgumentException e) { threw++; }
        try { FaceGrayConverter.toRgb565(null, 4, 2, 6, 0); } catch (IllegalArgumentException e) { threw++; }
        try { FaceGrayConverter.toRgb565(new byte[1], 1, 1, 1, 0); } catch (IllegalArgumentException e) { threw++; }
        check(threw == 5, "five invalid inputs rejected");

        // front camera rotation
        check(FaceGrayConverter.frontCameraRotation(270, 0) == 270, "portrait front camera");
        check(FaceGrayConverter.frontCameraRotation(270, 90) == 0, "landscape wraps to 0");
        check(FaceGrayConverter.frontCameraRotation(90, 270) == 0, "wrap 360");
        check(FaceGrayConverter.frontCameraRotation(270, 180) == 90, "reverse portrait");

        System.out.println("FACE_GRAY_CONVERTER_OK assertions=" + n);
    }
}
