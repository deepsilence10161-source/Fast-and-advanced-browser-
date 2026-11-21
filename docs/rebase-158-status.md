# Rebase to Chromium 158.0.8127.42 — status (21 Nov 2026)

Branch `rebase-158`. Chrome stable is 158.0.8127.42 (17 Nov 2026); there is no auto-update in Swiftra, so a Swiftra
build on 158 is only "same Chromium patch level as Chrome stable on the day of the build", not "more secure than Chrome".

## What had to be fixed (all found by compile errors or device tests, not by the first apply)
| Problem | Cause | Fix |
|---|---|---|
| `0002` strings: "source translation not found" | upstream removed the desktop Safe Browsing subtitle strings that 0002 used as translation source | English-only fact fix (`english_only_ok`); other languages fall back to English for those two strings |
| `offline_audio_context.cc` did not compile (0011) | `patch --fuzz=3` placed the audio-noise hunk in `suspendContext` | hunk re-placed by exact anchor before `resolver->Resolve()` in the new chunked render path |
| `download_prefs.cc`, `download_target_determiner.cc` did not compile (0103) | 0101/0103 were written as zero-context diffs (`-U0`), applied by line number; upstream turned `DCHECK` into `CHECK(..., NotFatalUntil::M161)` | `regen.py` now derives zero-context patches on the 155 tree and re-applies them with context; the 5 determiner hunks are placed by exact anchors |
| **C05 FLAG_SECURE FAIL** on device (built fine!) | 158 moved FLAG_SECURE ownership to `ScreenshotProtectionController`, which clears the flag for normal tabs; 0103 only patched `IncognitoSnapshotController` | new patch `0113` (158 only) |
| Hidden risk | `regen.py` used `--fuzz=3` (ignores all context) | now `--fuzz=0`, rejected hunks retried with fuzz 2 only where reviewed |

Lesson: a patch that applies and compiles can still be wrong (C05). Every rebase needs the device suite, not only a build.

## Measured on 158.0.8127.42 (x64 emulator, Android 16, this branch, personal-dev, build with 0113)
- Personal E2E: 12/12 PASS (run 44835186550) incl. C05 FLAG_SECURE, C10 open-file, C11/C12 Google web sign-in page.
- Clipboard K00-K04: 5/5 PASS (system clipboard, as in Chrome).
- Forensics: tabs-closed CLEAN after Delete.
- Face Guard: nofaces / one face / two faces PASS (44836306560 / 44836324757 / 44836341371).
- arm64: build running at the time of writing (see the release/runs); NOT measured.

## Not done / not claimed
- Speed Pack (0016) still skips studies it cannot re-verify on 158 (not re-audited).
- `tests/` pins the 155 series; the pinned series list in `tools/personal_browser/prepare.py` was extended with 0113 only.
- No claim of being more secure than Chrome; Swiftra has no Sync, no password manager, no auto-update.
