import org.chromium.chrome.browser.swiftra.faceguard.FaceGuardPolicy;
import org.chromium.chrome.browser.swiftra.faceguard.FaceGuardPolicy.*;

public final class FaceGuardPolicyTest {
    static int n = 0;
    static void check(boolean ok, String what) {
        n++;
        if (!ok) { System.out.println("FAIL: " + what); System.exit(1); }
    }
    static FaceGuardPolicy ready() {
        FaceGuardPolicy p = new FaceGuardPolicy(Config.defaults());
        p.setEnabled(true); p.setTemplate(Template.OK); p.setPermissionGranted(true); p.onForeground();
        return p;
    }
    static void owner(FaceGuardPolicy p, long from, long to) {
        for (long t = from; t <= to; t += 100) p.onObservation(new Observation(t, true, true, 0));
    }
    static boolean locked(FaceGuardPolicy p, long t) { return p.evaluate(t).locked; }
    static Reason why(FaceGuardPolicy p, long t) { return p.evaluate(t).reason; }

    public static void main(String[] a) {
        // disabled: never locks, camera off
        FaceGuardPolicy d = new FaceGuardPolicy(Config.defaults());
        check(!d.evaluate(0).locked && d.evaluate(0).reason == Reason.DISABLED && !d.evaluate(0).cameraNeeded, "disabled never locks");
        d.setTemplate(Template.MISSING); d.setPermissionGranted(false);
        check(!d.evaluate(5).locked, "disabled ignores template/permission");

        // enabled but nothing observed yet: locked, camera needed
        FaceGuardPolicy p = ready();
        check(locked(p, 0) && why(p, 0) == Reason.WAITING_FOR_OWNER && p.evaluate(0).cameraNeeded, "locked until owner seen");
        // a single frame is not enough
        p.onObservation(new Observation(100, true, true, 0));
        check(locked(p, 100), "one frame does not unlock");
        // 3 clean frames spanning >=400ms unlock
        owner(p, 200, 600);
        check(!locked(p, 600) && why(p, 600) == Reason.OWNER_PRESENT, "sustained owner unlocks");
        // burst of frames inside <400ms does not unlock
        FaceGuardPolicy b = ready();
        b.onObservation(new Observation(0, true, true, 0)); b.onObservation(new Observation(50, true, true, 0));
        b.onObservation(new Observation(100, true, true, 0)); b.onObservation(new Observation(150, true, true, 0));
        check(locked(b, 150), "burst shorter than minUnlockMs stays locked");

        // brief absence tolerated, long absence locks (last owner frame at 600, lockDelay 1500)
        p.onObservation(new Observation(1900, true, false, 0));
        check(!locked(p, 2000) && why(p, 2000) == Reason.OWNER_PRESENT, "absence of 1400ms is tolerated");
        check(locked(p, 2200) && why(p, 2200) == Reason.OWNER_ABSENT, "absence of 1600ms locks");
        // after locking, returning owner needs a fresh sustained run
        p.onObservation(new Observation(3000, true, true, 0));
        check(locked(p, 3000), "one owner frame after lock does not unlock");
        owner(p, 3100, 3500);
        check(!locked(p, 3500), "sustained owner unlocks again");

        // other face: strict lock after otherFaceFrames, even with owner present
        FaceGuardPolicy o = ready(); owner(o, 0, 500);
        check(!locked(o, 500), "unlocked baseline");
        o.onObservation(new Observation(600, true, true, 1));
        check(!locked(o, 600), "one frame with another face is tolerated");
        o.onObservation(new Observation(700, true, true, 1));
        check(locked(o, 700) && why(o, 700) == Reason.OTHER_FACE, "two frames with another face lock");
        owner(o, 800, 1300);
        check(!locked(o, 1300), "other face gone + sustained owner unlocks");
        // non-owner alone
        FaceGuardPolicy s = ready();
        for (long t = 0; t <= 1000; t += 100) s.onObservation(new Observation(t, true, false, 1));
        check(locked(s, 1000), "stranger alone never unlocks");

        // lockOnOtherFaces=false: another face does not lock
        FaceGuardPolicy r = new FaceGuardPolicy(new Config(0.70f, 1500, 2000, 3, 400, 2, false));
        r.setEnabled(true); r.setTemplate(Template.OK); r.setPermissionGranted(true); r.onForeground();
        for (long t = 0; t <= 600; t += 100) r.onObservation(new Observation(t, true, true, 1));
        check(!locked(r, 600), "relaxed mode ignores bystanders");

        // stale frames lock
        FaceGuardPolicy st = ready(); owner(st, 0, 500);
        check(!locked(st, 1000), "fresh");
        check(locked(st, 500 + 2001) && why(st, 2501) == Reason.NO_FRAMES, "no frames for >staleMs locks");

        // invalid frames and non-monotonic timestamps are not trusted
        FaceGuardPolicy iv = ready();
        for (long t = 0; t <= 800; t += 100) iv.onObservation(new Observation(t, false, true, 0));
        check(locked(iv, 800), "invalid frames never unlock");
        FaceGuardPolicy nm = ready(); owner(nm, 1000, 1500);
        check(!locked(nm, 1500), "baseline");
        for (long t = 0; t <= 900; t += 100) nm.onObservation(new Observation(t, true, false, 5));
        check(!locked(nm, 1500), "old timestamps ignored (cannot be used to lock or unlock)");

        // fail-closed inputs
        FaceGuardPolicy f = ready(); owner(f, 0, 500);
        f.setTemplate(Template.UNAVAILABLE);
        check(locked(f, 500) && why(f, 500) == Reason.TEMPLATE_UNAVAILABLE && !f.evaluate(500).cameraNeeded, "corrupt template locks, no camera");
        f.setTemplate(Template.MISSING);
        check(why(f, 500) == Reason.NOT_ENROLLED, "missing template locks");
        f.setTemplate(Template.OK); owner(f, 600, 1100);
        check(!locked(f, 1100), "restored template + owner unlocks");
        f.setPermissionGranted(false);
        check(locked(f, 1100) && why(f, 1100) == Reason.PERMISSION_DENIED, "permission denied locks");
        f.setPermissionGranted(true); owner(f, 1200, 1700);
        check(!locked(f, 1700), "permission back + owner unlocks");
        f.onCameraFailed();
        check(locked(f, 1700) && why(f, 1700) == Reason.CAMERA_UNAVAILABLE && f.evaluate(1700).cameraNeeded, "camera failure locks and retries");
        f.onCameraRecovered(); owner(f, 1800, 2300);
        check(!locked(f, 2300), "camera recovered");

        // background: locks, camera off, requires re-verification
        f.onBackground();
        check(locked(f, 2400) && why(f, 2400) == Reason.BACKGROUND && !f.evaluate(2400).cameraNeeded, "background locks");
        f.onForeground();
        check(locked(f, 2500), "returning to foreground starts locked");
        owner(f, 2600, 3100);
        check(!locked(f, 3100), "owner re-verified after foreground");

        // device credential override: unlocks, dies on background
        FaceGuardPolicy c = ready();
        check(locked(c, 0), "locked before override");
        c.onDeviceCredentialSuccess();
        check(!locked(c, 0) && why(c, 0) == Reason.DEVICE_CREDENTIAL_OVERRIDE && !c.evaluate(0).cameraNeeded, "credential override unlocks");
        c.onBackground(); c.onForeground();
        check(locked(c, 10), "override does not survive background");

        // disabling requires owner proof or credential
        FaceGuardPolicy m = ready();
        check(!m.mayDisable(0), "locked guard cannot be disabled by anyone present");
        owner(m, 0, 500);
        check(m.mayDisable(500), "owner may disable");
        m.onObservation(new Observation(600, true, true, 1)); m.onObservation(new Observation(700, true, true, 1));
        check(!m.mayDisable(700), "stranger in frame cannot disable");
        FaceGuardPolicy m2 = ready(); m2.onDeviceCredentialSuccess();
        check(m2.mayDisable(0), "credential may disable");
        m2.setEnabled(false);
        check(m2.mayDisable(0), "already disabled");

        // config bounds
        boolean threw = false;
        try { new Config(0.30f, 1500, 2000, 3, 400, 2, true); } catch (IllegalArgumentException e) { threw = true; }
        check(threw, "threshold below floor rejected");
        threw = false; try { new Config(0.70f, 60_000, 2000, 3, 400, 2, true); } catch (IllegalArgumentException e) { threw = true; }
        check(threw, "lock delay cap enforced");
        threw = false; try { new Config(0.70f, 1500, 2000, 1, 400, 2, true); } catch (IllegalArgumentException e) { threw = true; }
        check(threw, "single-frame unlock rejected");
        threw = false; try { new Config(Float.NaN, 1500, 2000, 3, 400, 2, true); } catch (IllegalArgumentException e) { threw = true; }
        check(threw, "NaN threshold rejected");

        // embeddings
        float[] x = {1, 0, 0}, y = {0, 1, 0}, z = {2, 0, 0};
        check(Math.abs(FaceGuardPolicy.cosine(x, z) - 1f) < 1e-6, "cosine parallel");
        check(Math.abs(FaceGuardPolicy.cosine(x, y)) < 1e-6, "cosine orthogonal");
        check(Float.isNaN(FaceGuardPolicy.cosine(x, new float[]{1, 0})), "length mismatch is NaN");
        check(Float.isNaN(FaceGuardPolicy.cosine(x, new float[]{0, 0, 0})), "zero vector is NaN");
        check(Float.isNaN(FaceGuardPolicy.cosine(x, new float[]{Float.NaN, 0, 1})), "NaN input is NaN");
        check(!FaceGuardPolicy.isMatch(Float.NaN, 0.7f), "NaN never matches");
        check(FaceGuardPolicy.isMatch(0.7f, 0.7f) && !FaceGuardPolicy.isMatch(0.699f, 0.7f), "threshold boundary inclusive");

        float[][] good = {{1, 0.1f, 0}, {1, 0.05f, 0.02f}, {0.98f, 0.12f, 0}, {1, 0, 0.05f}, {1.02f, 0.08f, 0}};
        float[] tpl = FaceGuardPolicy.buildTemplate(good, 5, 0.9f);
        check(tpl != null && Math.abs(FaceGuardPolicy.cosine(tpl, good[0]) - 1f) < 0.05f, "template from consistent samples");
        double norm = 0; for (float v : tpl) norm += v * v;
        check(Math.abs(norm - 1.0) < 1e-5, "template is unit length");
        float[][] mixed = {good[0], good[1], good[2], good[3], {0, 1, 0}};
        check(FaceGuardPolicy.buildTemplate(mixed, 5, 0.9f) == null, "samples from different people rejected");
        check(FaceGuardPolicy.buildTemplate(new float[][]{good[0], good[1]}, 5, 0.9f) == null, "too few samples rejected");
        check(FaceGuardPolicy.buildTemplate(new float[][]{good[0], good[1], good[2], good[3], new float[]{0, 0, 0}}, 5, 0.9f) == null, "zero sample rejected");

        System.out.println("FACE_GUARD_POLICY_OK assertions=" + n);
    }
}
