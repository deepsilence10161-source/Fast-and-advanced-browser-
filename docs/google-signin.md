# Google sign-in in Swiftra — what works, what cannot (21 Nov 2026)

## What a user means by "sign in"
| # | Flow | Status | Evidence |
|---|---|---|---|
| 1 | Google **website** login (accounts.google.com, Gmail, YouTube, any "Sign in with Google" popup) | Works up to the credential step | MEASURED, device E2E `C11`/`C12` (x64 emulator + arm64 Redroid): the form loads, JS runs, Google's account lookup answers "Couldn't find this account" for a made-up address. UA brands `Chromium,Not(A:Brand` (no "Google Chrome" brand), `webdriver=false`, cookies on, WebAuthn API, FedCM and Credential Management API present. Password / 2-step / passkey were NOT exercised (no credentials are used in CI). |
| 2 | "Sign in with Google" button/One Tap on third-party sites | API present (FedCM); not measured end-to-end (needs a registered client id) | MEASURED: `IdentityCredential` exists. SOURCE: `0010` sets third-party cookie blocking as default; sign-in popups and FedCM do not need third-party cookies. |
| 3 | Chrome-style **browser sign-in / Sync** ("Sign in to Swiftra") | **Cannot be built from the open-source tree** | SOURCE: Chromium 155 `components/signin/public/android/.../` has `AccountManagerDelegate` and `NullAccountManagerDelegate` only; the real delegate is loaded by `ServiceLoaderUtil` from Google's private code. Since 15 Mar 2021 Google restricts Sync/OAuth scopes to Chrome builds with Google's own keys (blog.chromium.org, "Limiting Private API availability in Chromium"). |
| 4 | Passkeys / Google Password Manager | Not available | SOURCE: Android WebAuthn goes through the Play Services *privileged* FIDO2 API, which only allow-listed browsers can call. `isUserVerifyingPlatformAuthenticatorAvailable()` returned `false` (MEASURED, emulator). Needs a physical device test to say more. |

## Consequence
Brave, Vivaldi, Edge etc. all do the same: Google login happens on the Google website; browser-level Google Sync is Chrome-only. The in-browser "Sign in" entry in Swiftra opens the Google web login (0112).

## Open items
* Third-party cookies are blocked by default (0010). It is a deliberate privacy choice; if some site's embedded login breaks, the per-site setting exists.
* Real login on a phone (password, 2-step prompt, passkey) must be tried by the owner: results to be added here.
