"""Host JVM tests for the Face Guard decision core (tools/face_guard). Host result only: NOT Android PASS,
and nothing here measures camera, face-model accuracy, spoofing resistance or UI."""
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/face_guard"))
import host_probe as H  # noqa: E402

pytestmark = pytest.mark.skipif(not (shutil.which("javac") and shutil.which("java")), reason="JDK required")

MUTANTS = {
    "background_does_not_lock": ("if (!mForeground) return new Decision(true, Reason.BACKGROUND, false);",
                                 "if (!mForeground) return new Decision(false, Reason.BACKGROUND, false);"),
    "override_survives_background": ("        mOverride = false; // an override never survives backgrounding\n", ""),
    "nan_matches": ("return !Float.isNaN(similarity) && similarity >= threshold;", "return !(similarity < threshold);"),
    "non_monotonic_trusted": ("        if (o.atMs < mLastValidMs) return;                 // non-monotonic timestamp: ignore, never trust\n", ""),
    "corrupt_template_unlocks": ("if (mTemplate == Template.UNAVAILABLE) return new Decision(true,",
                                 "if (mTemplate == Template.UNAVAILABLE) return new Decision(false,"),
    "single_frame_unlock_allowed": ("MIN_UNLOCK_FRAMES = 2;", "MIN_UNLOCK_FRAMES = 0;"),
    "staleness_ignored": ("if (mLastValidMs < 0 || nowMs - mLastValidMs > mConfig.staleMs) {",
                          "if (mLastValidMs < 0) {"),
    "mixed_people_template_accepted": ("if (Float.isNaN(c) || c < minPairwise) return null;", "if (Float.isNaN(c)) return null;"),
    "anyone_may_disable": ("        return !d.locked && (d.reason == Reason.OWNER_PRESENT || d.reason == Reason.DEVICE_CREDENTIAL_OVERRIDE);",
                           "        return true;"),
    "absence_never_locks": ("nowMs - mLastOwnerMs <= mConfig.lockDelayMs", "nowMs - mLastOwnerMs <= 100000000L"),
}


def test_policy_host_probe_passes():
    rc, out = H.run()
    assert rc == 0 and "FACE_GUARD_POLICY_OK" in out, out


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_mutant_is_rejected(name):
    old, new = MUTANTS[name]
    src = H.SRC.read_text()
    assert src.count(old) == 1, f"mutation anchor drifted for {name}"
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "FaceGuardPolicy.java"
        p.write_text(src.replace(old, new))
        rc, out = H.run(p)
    assert rc != 0, f"mutant {name} survived the tests"
    assert "FACE_GUARD_POLICY_OK" not in out
