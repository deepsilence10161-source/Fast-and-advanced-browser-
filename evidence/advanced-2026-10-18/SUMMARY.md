# Advanced defaults (patch 0000 + 0010) — 18-10-2026

| जाँच | पहले (0009 APK) | बाद (0000+0010) x64 emulator | बाद arm64 Redroid |
|---|---|---|---|
| HTTP-only public site | चुपचाप HTTP खुला (FAIL) — runs 39103561212 / 39103562181 | native चेतावनी "This site doesn't support a secure connection", HTTP hits 0 — PASS (39119631793, 39122267905) | PASS (39115751258: blocked_no_http; 39118129068: warning_dialog) |
| Third-party cookie (cross-site iframe, SameSite=None; Secure) | s3p=1 दोनों loads में (allowed) | दोनों loads में खाली, first-party fp=1 मौजूद — PASS | PASS |
| SHIELD_E2E / STARTUP_NETLOG | PASS | PASS / PASS | PASS / PASS |
| Cold / warm median (ms) | x64 938.5 / 724; arm64 710.5 / 183.5 | 1219.5 / 902 और 1033.5 / 710 (emulator उतार-चढ़ाव) | 706.5 / 186 और 699.5 / 184.5 |
| PSS after example.com (kB) | x64 150206; arm64 278501 | 150999 / 147748 | 269062 / 270668 |

APK SHA-256: x64 `268568d68aca72084bc9075d676f01f91af51979c702d76fc2dd12a07cea1c30`, arm64 `5c0131ca473c773fd50ed58038ff06669d12ce420f4a62df46280081e1ca0b0c`
(signer cert 029de0fa…fe06)। Builds: 39103667941 (x64), 39103669428 (arm64)।
Version label 155.0.8059.80 दिखता है, code में .84 के सभी security fixes (patches/README.md, 0000)।
Fingerprinting सुरक्षा: इस चरण में नहीं — @155 में तैयार flag नहीं, अगला चरण।
