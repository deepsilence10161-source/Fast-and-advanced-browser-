package org.chromium.chrome.browser.swiftra.faceguard;

/**
 * Face Guard decision core. Pure Java: no Android, camera, model or Chromium dependency, so that the
 * lock/unlock rules can be unit-tested on a host JVM. It never touches images; it only sees per-frame
 * observations (how many faces, whether one matched the owner template).
 *
 * Contract (see docs/plans/face-guard.md):
 *  - Feature disabled        -> never locks, camera not needed.
 *  - Feature enabled         -> content stays LOCKED until the owner is seen for several consecutive clean frames.
 *  - FAIL CLOSED             -> missing/corrupt template, permission denied, camera failure, stale/no frames,
 *                               backgrounding and any non-owner face all lock. Nothing here deletes data.
 *  - Escape hatch            -> device credential override (until backgrounded) so the owner is never locked out.
 *  - Time is injected (monotonic ms) so behaviour is deterministic.
 */
public final class FaceGuardPolicy {
    public enum Reason {
        DISABLED, OWNER_PRESENT, WAITING_FOR_OWNER, OWNER_ABSENT, OTHER_FACE, NO_FRAMES,
        CAMERA_UNAVAILABLE, PERMISSION_DENIED, NOT_ENROLLED, TEMPLATE_UNAVAILABLE,
        BACKGROUND, DEVICE_CREDENTIAL_OVERRIDE
    }

    public enum Template { MISSING, UNAVAILABLE, OK }

    /** Edge-triggered UI action. LOCK = open the (masked) tab switcher once; UNLOCK = reveal once. */
    public enum Action { NONE, LOCK, UNLOCK }

    /** Hard bounds so a config can never weaken the guard beyond these limits. */
    public static final float MIN_MATCH_THRESHOLD = 0.55f;
    public static final float MAX_MATCH_THRESHOLD = 0.95f;
    public static final long MAX_LOCK_DELAY_MS = 10_000;
    public static final long MAX_STALE_MS = 5_000;
    public static final int MIN_UNLOCK_FRAMES = 2;

    public static final class Config {
        /** UNCALIBRATED default: must be tuned against the real embedding model before any claim of accuracy. */
        public final float matchThreshold;
        public final long lockDelayMs;     // owner may be briefly missing (blink/turn) before locking
        public final long staleMs;         // no valid frame for this long -> lock
        public final int unlockFrames;     // consecutive clean owner frames required to unlock
        public final long minUnlockMs;     // ...spanning at least this long
        public final int otherFaceFrames;  // consecutive frames with a non-owner face before locking
        public final boolean lockOnOtherFaces;

        public Config(float matchThreshold, long lockDelayMs, long staleMs, int unlockFrames,
                      long minUnlockMs, int otherFaceFrames, boolean lockOnOtherFaces) {
            if (!(matchThreshold >= MIN_MATCH_THRESHOLD && matchThreshold <= MAX_MATCH_THRESHOLD)) {
                throw new IllegalArgumentException("matchThreshold out of bounds");
            }
            if (lockDelayMs < 0 || lockDelayMs > MAX_LOCK_DELAY_MS) throw new IllegalArgumentException("lockDelayMs");
            if (staleMs <= 0 || staleMs > MAX_STALE_MS) throw new IllegalArgumentException("staleMs");
            if (unlockFrames < MIN_UNLOCK_FRAMES) throw new IllegalArgumentException("unlockFrames");
            if (minUnlockMs < 0) throw new IllegalArgumentException("minUnlockMs");
            if (otherFaceFrames < 1) throw new IllegalArgumentException("otherFaceFrames");
            this.matchThreshold = matchThreshold;
            this.lockDelayMs = lockDelayMs;
            this.staleMs = staleMs;
            this.unlockFrames = unlockFrames;
            this.minUnlockMs = minUnlockMs;
            this.otherFaceFrames = otherFaceFrames;
            this.lockOnOtherFaces = lockOnOtherFaces;
        }

        public static Config defaults() {
            return new Config(0.70f, 300, 1000, 3, 300, 2, true);
        }
    }

    public static final class Observation {
        public final long atMs;
        public final boolean valid;       // detector produced a usable result for this frame
        public final boolean ownerMatched;
        public final int otherFaces;      // faces that are NOT the owner

        public Observation(long atMs, boolean valid, boolean ownerMatched, int otherFaces) {
            this.atMs = atMs;
            this.valid = valid;
            this.ownerMatched = ownerMatched;
            this.otherFaces = Math.max(0, otherFaces);
        }
    }

    public static final class Decision {
        public final boolean locked;
        public final Reason reason;
        public final boolean cameraNeeded;

        Decision(boolean locked, Reason reason, boolean cameraNeeded) {
            this.locked = locked;
            this.reason = reason;
            this.cameraNeeded = cameraNeeded;
        }

        @Override
        public String toString() {
            return (locked ? "LOCKED:" : "UNLOCKED:") + reason + (cameraNeeded ? ":camera" : "");
        }
    }

    private final Config mConfig;
    private boolean mEnabled;
    private boolean mForeground;
    private boolean mPermissionGranted;
    private boolean mCameraFailed;
    private boolean mOverride;
    private Template mTemplate = Template.MISSING;

    private boolean mUnlocked;           // latched state: owner proven and not yet lost
    private long mLastValidMs = -1;
    private long mLastOwnerMs = -1;
    private int mOwnerRun;
    private long mOwnerRunStartMs = -1;
    private int mOtherRun;
    private boolean mLastLocked;         // for edge detection in poll()
    private long mEvalClockMs = Long.MIN_VALUE; // evaluate() time never goes backwards

    public FaceGuardPolicy(Config config) {
        if (config == null) throw new IllegalArgumentException("config");
        mConfig = config;
    }

    public Config config() {
        return mConfig;
    }

    // ---------------------------------------------------------------- inputs
    public void setEnabled(boolean enabled) {
        if (mEnabled != enabled) resetTracking();
        mEnabled = enabled;
    }

    public void setTemplate(Template t) {
        if (t == null) throw new IllegalArgumentException("template");
        if (mTemplate != t) resetTracking();
        mTemplate = t;
    }

    public void setPermissionGranted(boolean granted) {
        if (mPermissionGranted != granted) resetTracking();
        mPermissionGranted = granted;
        if (granted) mCameraFailed = false;
    }

    public void onCameraFailed() {
        mCameraFailed = true;
        resetTracking();
    }

    public void onCameraRecovered() {
        mCameraFailed = false;
    }

    public void onForeground() {
        mForeground = true;
        resetTracking();   // always re-verify the owner after coming back
    }

    public void onBackground() {
        mForeground = false;
        mOverride = false; // an override never survives backgrounding
        resetTracking();
    }

    /** Call only after the platform confirmed device credential (PIN/pattern/password) success. */
    public void onDeviceCredentialSuccess() {
        mOverride = true;
    }

    public void onObservation(Observation o) {
        if (o == null || !o.valid) return;                 // an unusable frame proves nothing
        if (o.atMs < mLastValidMs) return;                 // non-monotonic timestamp: ignore, never trust
        mLastValidMs = o.atMs;
        if (o.otherFaces > 0) mOtherRun++; else mOtherRun = 0;
        boolean clean = o.ownerMatched && o.otherFaces == 0;
        boolean ownerOnly = o.ownerMatched && (o.otherFaces == 0 || !mConfig.lockOnOtherFaces);
        if (ownerOnly) {
            if (mOwnerRun == 0) mOwnerRunStartMs = o.atMs;
            mOwnerRun++;
            mLastOwnerMs = o.atMs;
        } else {
            mOwnerRun = 0;
            mOwnerRunStartMs = -1;
        }
        if (!clean && mConfig.lockOnOtherFaces && o.otherFaces > 0 && mOtherRun >= mConfig.otherFaceFrames) {
            mUnlocked = false;
        }
    }

    // ---------------------------------------------------------------- decision
    public Decision evaluate(long nowMs) {
        if (nowMs < mEvalClockMs) nowMs = mEvalClockMs;   // a regressing clock must never unlock
        mEvalClockMs = nowMs;
        if (!mEnabled) return new Decision(false, Reason.DISABLED, false);
        if (!mForeground) return new Decision(true, Reason.BACKGROUND, false);
        if (mOverride) return new Decision(false, Reason.DEVICE_CREDENTIAL_OVERRIDE, false);
        if (mTemplate == Template.MISSING) return new Decision(true, Reason.NOT_ENROLLED, false);
        if (mTemplate == Template.UNAVAILABLE) return new Decision(true, Reason.TEMPLATE_UNAVAILABLE, false);
        if (!mPermissionGranted) return new Decision(true, Reason.PERMISSION_DENIED, false);
        if (mCameraFailed) return new Decision(true, Reason.CAMERA_UNAVAILABLE, true);

        if (mLastValidMs < 0 || nowMs - mLastValidMs > mConfig.staleMs) {
            mUnlocked = false;
            mOwnerRun = 0;
            mOwnerRunStartMs = -1;
            return new Decision(true, mLastValidMs < 0 ? Reason.WAITING_FOR_OWNER : Reason.NO_FRAMES, true);
        }
        if (mConfig.lockOnOtherFaces && mOtherRun >= mConfig.otherFaceFrames) {
            mUnlocked = false;
            mOwnerRun = 0;
            mOwnerRunStartMs = -1;
            return new Decision(true, Reason.OTHER_FACE, true);
        }
        if (mOwnerRun >= mConfig.unlockFrames && mOwnerRunStartMs >= 0
                && mLastValidMs - mOwnerRunStartMs >= mConfig.minUnlockMs) {
            mUnlocked = true;
        }
        if (mUnlocked) {
            if (mLastOwnerMs >= 0 && nowMs - mLastOwnerMs <= mConfig.lockDelayMs) {
                return new Decision(false, Reason.OWNER_PRESENT, true);
            }
            mUnlocked = false;
            mOwnerRun = 0;              // a fresh sustained run is required after any lock
            mOwnerRunStartMs = -1;
            return new Decision(true, Reason.OWNER_ABSENT, true);
        }
        return new Decision(true, mLastOwnerMs >= 0 ? Reason.OWNER_ABSENT : Reason.WAITING_FOR_OWNER, true);
    }

    /**
     * Edge-triggered result for the UI layer: LOCK exactly once when the state goes unlocked -> locked (open
     * the masked tab switcher immediately), UNLOCK exactly once on locked -> unlocked, otherwise NONE.
     * Call after every observation AND at nextDeadlineMs() so locking never waits for another frame.
     */
    public Action poll(long nowMs) {
        boolean locked = evaluate(nowMs).locked;
        if (locked == mLastLocked) return Action.NONE;
        mLastLocked = locked;
        return locked ? Action.LOCK : Action.UNLOCK;
    }

    /**
     * Earliest time (ms, same clock) at which evaluate() could flip from unlocked to locked purely because
     * time passed (owner missing too long, or frames stalled). -1 when no time-based lock is pending.
     */
    public long nextDeadlineMs() {
        if (!mEnabled || !mForeground || mOverride || !mUnlocked || mLastValidMs < 0 || mLastOwnerMs < 0) return -1;
        return Math.min(mLastOwnerMs + mConfig.lockDelayMs, mLastValidMs + mConfig.staleMs) + 1;
    }

    /** Turning the feature off (or re-enrolling) needs the owner proven right now or a device credential. */
    public boolean mayDisable(long nowMs) {
        if (!mEnabled) return true;
        Decision d = evaluate(nowMs);
        return !d.locked && (d.reason == Reason.OWNER_PRESENT || d.reason == Reason.DEVICE_CREDENTIAL_OVERRIDE);
    }

    private void resetTracking() {
        mUnlocked = false;
        mLastValidMs = -1;
        mLastOwnerMs = -1;
        mOwnerRun = 0;
        mOwnerRunStartMs = -1;
        mOtherRun = 0;
        mEvalClockMs = Long.MIN_VALUE;
    }

    // ---------------------------------------------------------------- embedding helpers
    /** Cosine similarity of two finite, same-length, non-zero vectors; NaN when the input is unusable. */
    public static float cosine(float[] a, float[] b) {
        if (a == null || b == null || a.length == 0 || a.length != b.length) return Float.NaN;
        double dot = 0, na = 0, nb = 0;
        for (int i = 0; i < a.length; i++) {
            if (Float.isNaN(a[i]) || Float.isInfinite(a[i]) || Float.isNaN(b[i]) || Float.isInfinite(b[i])) {
                return Float.NaN;
            }
            dot += (double) a[i] * b[i];
            na += (double) a[i] * a[i];
            nb += (double) b[i] * b[i];
        }
        if (na == 0 || nb == 0) return Float.NaN;
        return (float) (dot / (Math.sqrt(na) * Math.sqrt(nb)));
    }

    /** Fail closed: an unusable similarity (NaN) is never a match. */
    public static boolean isMatch(float similarity, float threshold) {
        return !Float.isNaN(similarity) && similarity >= threshold;
    }

    /**
     * Enrollment template = re-normalised mean of the samples, but only when every sample pair is consistent.
     * Returns null when there are too few samples or the samples look like different people/unusable data.
     */
    public static float[] buildTemplate(float[][] samples, int minSamples, float minPairwise) {
        if (samples == null || samples.length < minSamples || minSamples < 2) return null;
        int dim = samples[0] == null ? 0 : samples[0].length;
        if (dim == 0) return null;
        for (int i = 0; i < samples.length; i++) {
            for (int j = i + 1; j < samples.length; j++) {
                float c = cosine(samples[i], samples[j]);
                if (Float.isNaN(c) || c < minPairwise) return null;
            }
        }
        double[] mean = new double[dim];
        for (float[] s : samples) {
            double n = 0;
            for (float v : s) n += (double) v * v;
            n = Math.sqrt(n);
            for (int k = 0; k < dim; k++) mean[k] += s[k] / n;
        }
        double n = 0;
        for (double v : mean) n += v * v;
        n = Math.sqrt(n);
        if (n == 0) return null;
        float[] out = new float[dim];
        for (int k = 0; k < dim; k++) out[k] = (float) (mean[k] / n);
        return out;
    }
}
