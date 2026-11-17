package org.chromium.chrome.browser.swiftra.faceguard;

import android.content.Context;
import android.graphics.ImageFormat;
import android.hardware.camera2.CameraAccessException;
import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraDevice;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.params.OutputConfiguration;
import android.hardware.camera2.params.SessionConfiguration;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.media.Image;
import android.media.ImageReader;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.SystemClock;
import android.util.Size;
import android.view.Surface;
import android.view.WindowManager;

import java.nio.ByteBuffer;
import java.util.Collections;

/**
 * Front camera frames -> face counts, entirely in memory. Frames are never written to disk, logged or sent anywhere.
 * Any camera problem is reported through onCameraFailed() so the policy can fail closed.
 */
final class FaceCameraSource {
    interface Listener {
        /** Called on the camera thread. valid=false means the frame could not be analysed. */
        void onFrame(long atMs, boolean valid, int faces);

        void onCameraFailed();
    }

    private static final int TARGET_W = 480;   // smaller faces (a second person) are not detected below ~480 px
    private static final long MIN_FRAME_INTERVAL_MS = 80;

    private final Context mContext;
    private final Listener mListener;
    private final PresenceFaceAnalyzer mAnalyzer = new PresenceFaceAnalyzer();
    private HandlerThread mThread;
    private Handler mHandler;
    private CameraDevice mCamera;
    private CameraCaptureSession mSession;
    private ImageReader mReader;
    private int mSensorOrientation;
    private long mLastFrameMs;
    private volatile boolean mRunning;

    FaceCameraSource(Context context, Listener listener) {
        mContext = context.getApplicationContext();
        mListener = listener;
    }

    synchronized void start() {
        if (mRunning) return;
        mRunning = true;
        mThread = new HandlerThread("SwiftraFaceGuardCamera");
        mThread.start();
        mHandler = new Handler(mThread.getLooper());
        mHandler.post(this::open);
    }

    synchronized void stop() {
        if (!mRunning) return;
        mRunning = false;
        final HandlerThread thread = mThread;
        mHandler.post(
                () -> {
                    closeQuietly();
                    mAnalyzer.release();
                    thread.quitSafely();
                });
        mThread = null;
        mHandler = null;
    }

    private void fail() {
        if (mRunning) mListener.onCameraFailed();
    }

    private void open() {
        if (!mRunning) return;
        try {
            CameraManager manager = (CameraManager) mContext.getSystemService(Context.CAMERA_SERVICE);
            String id = null;
            CameraCharacteristics chars = null;
            for (String candidate : manager.getCameraIdList()) {
                CameraCharacteristics c = manager.getCameraCharacteristics(candidate);
                Integer facing = c.get(CameraCharacteristics.LENS_FACING);
                if (facing != null && facing == CameraCharacteristics.LENS_FACING_FRONT) {
                    id = candidate;
                    chars = c;
                    break;
                }
            }
            if (id == null || chars == null) {
                fail();
                return;
            }
            Integer so = chars.get(CameraCharacteristics.SENSOR_ORIENTATION);
            mSensorOrientation = so == null ? 270 : so;
            StreamConfigurationMap map = chars.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
            if (map == null) {
                fail();
                return;
            }
            Size size = chooseSize(map.getOutputSizes(ImageFormat.YUV_420_888));
            if (size == null) {
                fail();
                return;
            }
            mReader = ImageReader.newInstance(size.getWidth(), size.getHeight(), ImageFormat.YUV_420_888, 2);
            mReader.setOnImageAvailableListener(this::onImage, mHandler);
            manager.openCamera(id, new CameraDevice.StateCallback() {
                @Override
                public void onOpened(CameraDevice camera) {
                    mCamera = camera;
                    if (!mRunning) {
                        closeQuietly();
                        return;
                    }
                    startSession(camera);
                }

                @Override
                public void onDisconnected(CameraDevice camera) {
                    closeQuietly();
                    fail();
                }

                @Override
                public void onError(CameraDevice camera, int error) {
                    closeQuietly();
                    fail();
                }
            }, mHandler);
        } catch (CameraAccessException | SecurityException | IllegalArgumentException | IllegalStateException e) {
            closeQuietly();
            fail();
        }
    }

    private void startSession(CameraDevice camera) {
        try {
            Surface surface = mReader.getSurface();
            SessionConfiguration config = new SessionConfiguration(
                    SessionConfiguration.SESSION_REGULAR,
                    Collections.singletonList(new OutputConfiguration(surface)),
                    r -> {
                        Handler h = mHandler;
                        if (h != null) h.post(r);
                    },
                    new CameraCaptureSession.StateCallback() {
                        @Override
                        public void onConfigured(CameraCaptureSession session) {
                            mSession = session;
                            if (!mRunning) {
                                closeQuietly();
                                return;
                            }
                            try {
                                CaptureRequest.Builder b = camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
                                b.addTarget(surface);
                                b.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE);
                                session.setRepeatingRequest(b.build(), null, mHandler);
                            } catch (CameraAccessException | IllegalStateException e) {
                                closeQuietly();
                                fail();
                            }
                        }

                        @Override
                        public void onConfigureFailed(CameraCaptureSession session) {
                            closeQuietly();
                            fail();
                        }
                    });
            camera.createCaptureSession(config);
        } catch (CameraAccessException | IllegalStateException | IllegalArgumentException e) {
            closeQuietly();
            fail();
        }
    }

    static Size chooseSize(Size[] sizes) {
        if (sizes == null || sizes.length == 0) return null;
        Size best = null;
        for (Size s : sizes) {
            if (s.getWidth() < TARGET_W) continue;
            if (best == null || s.getWidth() * s.getHeight() < best.getWidth() * best.getHeight()) best = s;
        }
        if (best != null) return best;
        for (Size s : sizes) {
            if (best == null || s.getWidth() * s.getHeight() > best.getWidth() * best.getHeight()) best = s;
        }
        return best;
    }

    @SuppressWarnings("deprecation")
    private int displayRotationDegrees() {
        WindowManager wm = (WindowManager) mContext.getSystemService(Context.WINDOW_SERVICE);
        int r = wm.getDefaultDisplay().getRotation();
        return r == Surface.ROTATION_90 ? 90 : r == Surface.ROTATION_180 ? 180 : r == Surface.ROTATION_270 ? 270 : 0;
    }

    private void onImage(ImageReader reader) {
        Image image = null;
        long now = SystemClock.elapsedRealtime();
        try {
            image = reader.acquireLatestImage();
            if (image == null || !mRunning) return;
            if (now - mLastFrameMs < MIN_FRAME_INTERVAL_MS) return;
            mLastFrameMs = now;
            Image.Plane plane = image.getPlanes()[0];
            ByteBuffer buf = plane.getBuffer();
            byte[] y = new byte[buf.remaining()];
            buf.get(y);
            int rotation = FaceGrayConverter.frontCameraRotation(mSensorOrientation, displayRotationDegrees());
            FaceGrayConverter.Result gray =
                    FaceGrayConverter.toRgb565(y, image.getWidth(), image.getHeight(), plane.getRowStride(), rotation);
            mListener.onFrame(now, true, mAnalyzer.countFaces(gray));
        } catch (RuntimeException e) {
            mListener.onFrame(now, false, 0);   // an unusable frame proves nothing; the policy ignores it
        } finally {
            if (image != null) image.close();
        }
    }

    private void closeQuietly() {
        try {
            if (mSession != null) mSession.close();
        } catch (RuntimeException ignored) {
            // closing is best effort
        }
        try {
            if (mCamera != null) mCamera.close();
        } catch (RuntimeException ignored) {
            // closing is best effort
        }
        if (mReader != null) mReader.close();
        mSession = null;
        mCamera = null;
        mReader = null;
    }
}
