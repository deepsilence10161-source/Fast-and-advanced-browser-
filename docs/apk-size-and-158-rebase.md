# APK size and the Chromium 158 rebase (20 Nov 2026)

## Why the APK is ~367 MB (arm64) / ~380 MB (x64)  — MEASURED from the published APK
| Part | Size | Why |
|---|---|---|
| `libchrome.so` | 226.5 MB | not an `is_official_build` (no ThinLTO/PGO/identical-code-folding tuning), debug-ish layout; everything Chrome has is linked in |
| all native libs | ~235 MB | also XR/ARCore libs and `libimpress_api_jni.so` (18.6 MB) |
| `resources.arsc` | 34.5 MB | every language string table |
| 332 locale `.pak` files | 49 MB | all locales, nothing filtered |
| dex | 12.4 MB | no R8 shrinking of unused Chrome code |
| `icudtl.dat` / `resources.pak` | 9.3 / 8.5 MB | needed |
All 4208 entries are stored uncompressed (needed for mmap-ing the native library), so the APK is as large as its contents.

Levers, in order of size/risk (none applied yet; each needs a full rebuild because it changes `args.gn`):
1. `is_official_build=true` (+ `use_mold=false`, `chrome_orderfile_config` needs lld): smaller and faster `libchrome.so` (typically 25-40 % smaller; MEASURE).
2. Locale filtering (keep en-US + hi): ~45 MB.
3. Remove XR/ARCore/`libimpress_api_jni`: ~20+ MB.
4. R8 on the Java side: a few MB.

## Chromium 158.0.8127.42 rebase — branch `rebase-158`, worktree `/home/user/swiftra-158`
STATE: source series regenerated and committed on the branch; NOT built, NOT device-tested.
* 22 of 24 patches apply offset-free; real conflicts were only 0009, 0010, 0011, 0103, 0112 (resolved in `tools/rebase/regen.py`).
* 0000 (the 155.0.8059.84 upstream fix diff) is dropped: 158 already contains those fixes.
* 0103/0112: clipboard/share/open-file sections dropped (they are pristine by design now).
* 0016 skips studies that no longer exist or changed upstream (15 of 79), so unaudited experiments are never shipped.
* Remaining before publish: baseline build of 158 (`a1`, running from branch `baseline-158`), version strings/fixtures/tests retargeted, 0002/0013/0019 transform checks on a real tree, personal build, full device E2E.
* Security: a newer patch level is what matters; Swiftra has no auto-update, so each new Chrome stable needs a manual rebase+build+test. No "more secure than Chrome" claim is made.
