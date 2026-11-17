package com.swiftra.cliphelper;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.ImageFormat;
import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraDevice;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.params.OutputConfiguration;
import android.hardware.camera2.params.SessionConfiguration;
import android.media.FaceDetector;
import android.media.Image;
import android.media.ImageReader;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.nio.ShortBuffer;
import java.util.Collections;

/** CI-only: grabs a frame from the emulated FRONT camera, runs FaceDetector at 4 rotations, saves the raw Y plane (PGM). */
final class CamDiag {
    private static final String TAG = "CLIPHELPER";
    private final Context mCtx;
    private final Runnable mDone;
    private int mCount;
    private boolean mFinished;

    CamDiag(Context ctx, Runnable done) {
        mCtx = ctx;
        mDone = done;
    }

    void start() {
        final HandlerThread th = new HandlerThread("camdiag");
        th.start();
        final Handler h = new Handler(th.getLooper());
        try {
            CameraManager m = (CameraManager) mCtx.getSystemService(Context.CAMERA_SERVICE);
            String id = null;
            int so = -1;
            for (String c : m.getCameraIdList()) {
                CameraCharacteristics cc = m.getCameraCharacteristics(c);
                Integer f = cc.get(CameraCharacteristics.LENS_FACING);
                Log.i(TAG, "CAMDIAG camera id=" + c + " facing=" + f + " sensor=" + cc.get(CameraCharacteristics.SENSOR_ORIENTATION));
                if (f != null && f == CameraCharacteristics.LENS_FACING_FRONT && id == null) {
                    id = c;
                    so = cc.get(CameraCharacteristics.SENSOR_ORIENTATION);
                }
            }
            if (id == null) {
                Log.i(TAG, "CAMDIAG no_front_camera");
                finish();
                return;
            }
            final ImageReader r = ImageReader.newInstance(640, 480, ImageFormat.YUV_420_888, 2);
            r.setOnImageAvailableListener(rd -> {
                Image img = rd.acquireLatestImage();
                if (img == null) return;
                try {
                    if (++mCount == 15 && !mFinished) analyse(img);
                } finally {
                    img.close();
                }
            }, h);
            m.openCamera(id, new CameraDevice.StateCallback() {
                @Override public void onOpened(CameraDevice cam) {
                    try {
                        cam.createCaptureSession(new SessionConfiguration(SessionConfiguration.SESSION_REGULAR,
                                Collections.singletonList(new OutputConfiguration(r.getSurface())), x -> h.post(x),
                                new CameraCaptureSession.StateCallback() {
                                    @Override public void onConfigured(CameraCaptureSession s) {
                                        try {
                                            CaptureRequest.Builder b = cam.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
                                            b.addTarget(r.getSurface());
                                            s.setRepeatingRequest(b.build(), null, h);
                                        } catch (Exception e) {
                                            Log.i(TAG, "CAMDIAG request_failed " + e);
                                            finish();
                                        }
                                    }
                                    @Override public void onConfigureFailed(CameraCaptureSession s) {
                                        Log.i(TAG, "CAMDIAG configure_failed");
                                        finish();
                                    }
                                }));
                    } catch (Exception e) {
                        Log.i(TAG, "CAMDIAG session_failed " + e);
                        finish();
                    }
                }
                @Override public void onDisconnected(CameraDevice cam) { finish(); }
                @Override public void onError(CameraDevice cam, int e) { Log.i(TAG, "CAMDIAG open_error " + e); finish(); }
            }, h);
            h.postDelayed(this::finish, 25000);
        } catch (Exception e) {
            Log.i(TAG, "CAMDIAG failed " + e);
            finish();
        }
    }

    private void analyse(Image img) {
        mFinished = true;
        Image.Plane p = img.getPlanes()[0];
        ByteBuffer buf = p.getBuffer();
        byte[] y = new byte[buf.remaining()];
        buf.get(y);
        int w = img.getWidth(), h = img.getHeight(), stride = p.getRowStride();
        long sum = 0;
        for (int i = 0; i < h; i++) for (int j = 0; j < w; j++) sum += y[i * stride + j] & 0xFF;
        Log.i(TAG, "CAMDIAG frame " + w + "x" + h + " stride=" + stride + " meanY=" + (sum / (w * h)));
        try (FileOutputStream o = new FileOutputStream(new File(mCtx.getExternalFilesDir(null), "frame.pgm"))) {
            o.write(("P5\n" + w + " " + h + "\n255\n").getBytes());
            for (int i = 0; i < h; i++) o.write(y, i * stride, w);
        } catch (Exception e) {
            Log.i(TAG, "CAMDIAG save_failed " + e);
        }
        for (int rot : new int[] {0, 90, 180, 270}) {
            boolean swap = rot == 90 || rot == 270;
            int ow = (swap ? h : w) & ~1, oh = swap ? w : h;
            short[] out = new short[ow * oh];
            for (int oy = 0; oy < oh; oy++) {
                for (int ox = 0; ox < ow; ox++) {
                    int sx, sy;
                    if (rot == 90) { sx = oy; sy = h - 1 - ox; }
                    else if (rot == 180) { sx = w - 1 - ox; sy = h - 1 - oy; }
                    else if (rot == 270) { sx = w - 1 - oy; sy = ox; }
                    else { sx = ox; sy = oy; }
                    int g = y[sy * stride + sx] & 0xFF;
                    out[oy * ow + ox] = (short) (((g >> 3) << 11) | ((g >> 2) << 5) | (g >> 3));
                }
            }
            Bitmap bm = Bitmap.createBitmap(ow, oh, Bitmap.Config.RGB_565);
            bm.copyPixelsFromBuffer(ShortBuffer.wrap(out));
            FaceDetector.Face[] faces = new FaceDetector.Face[3];
            int n = new FaceDetector(ow, oh, 3).findFaces(bm, faces);
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < n; i++) sb.append(String.format(" [conf=%.2f eyes=%.1f]", faces[i].confidence(), faces[i].eyesDistance()));
            Log.i(TAG, "CAMDIAG rot=" + rot + " size=" + ow + "x" + oh + " found=" + n + sb);
            bm.recycle();
        }
        finish();
    }

    private synchronized void finish() {
        mFinished = true;
        Log.i(TAG, "CAMDIAG done");
        mDone.run();
    }
}
