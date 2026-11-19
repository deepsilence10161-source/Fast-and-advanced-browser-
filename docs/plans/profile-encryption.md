# Whole-profile encryption: decision and design (2026-11-19)

Status: **NOT BUILT.** This file records why, what the build already does, and what a safe version would need.

## What already protects the profile
- Android file-based encryption (FBE) encrypts the app's data directory with keys tied to the phone's lock screen
  credential. That is the whole-profile encryption a browser app can rely on, and it is outside Swiftra's code.
- 0021: cookies and card/IBAN values use an OSCrypt key from the Android Keystore (not the public upstream constant).
- 0101: no browser sign-in or Sync, so profile data is not copied to a cloud account.
- Face Guard (0105) is a UI lock only. It does **not** encrypt anything.

## Why no extra app-level layer was added in this batch
1. Chromium keeps the profile in many places and formats (SQLite files, LevelDB, the HTTP and code caches, GPU
   shader caches, Blink and IndexedDB blobs, extensions-like state, crash dumps). An encrypting layer under all of
   them needs a file-system-level shim (an encrypted overlay mounted for the browser process) or patches across
   //net, //sql and //storage. Patching only some stores would give a false "encrypted" claim.
2. A key that only the app holds can be lost (app data cleared, Keystore invalidated after a new fingerprint or a
   lock-screen reset, device restore). Then the whole profile is unreadable. Because of this project's rule, the
   build never wipes by itself on key loss, so a half-built version would leave users with an unreadable profile and
   no recovery.
3. It cannot be verified on the CI emulators: they have no enrolled biometric and no hardware-backed Keystore, so
   "protected when the phone is locked" would stay unmeasured.

## What a safe version needs (acceptance, before any claim)
- Scope the first version to **data the user marks private**, not the whole profile: the OSCrypt-protected stores
  plus the private-mode partitions of 0103.
- Keystore key with `setUserAuthenticationRequired` only if a recovery path exists: an optional exported recovery
  key (shown once, user-saved). No automatic wipe, ever. On key loss: show a clear message and keep the files, so a
  restored key can still read them.
- Tests on a real device with an enrolled biometric: key invalidation by adding a fingerprint, reboot, app-data
  clear (must be recoverable from the exported key), and a check that no plaintext canary is found in the profile
  directory (`grep -r` of a canary across /data/data/<pkg> after use).
- Release text must state exactly which stores are covered.

## Status in the release
Reported as: **not implemented; Android FBE plus the existing Keystore-backed OSCrypt are what protect stored data.**
