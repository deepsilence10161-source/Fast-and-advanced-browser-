# Download Shield "before" on the 0010 APKs (no patch 0015): runs 39134172867 (x64) and 39134174533 (arm64)

Both CPUs: `DOWNLOAD_SHIELD_E2E FAIL canary=downloaded redirect=downloaded clean=downloaded`.

- `canary`: a download from a URL that IS in the loaded Shield list (`SHIELD_E2E PASS` in the same run shows the list
  is loaded and navigation is blocked) finished without any warning. The test server served it and the file is in
  `/sdcard/Download`.
- `redirect`: a 302 from a clean URL to the listed URL also finished without a warning.
- `clean`: an unlisted download finished, as it should.

This is the expected FAIL. Before 0015 the Shield only checks navigations, not downloads. The result proves the
gap on a device, and also proves the harness: `<a download>` starts a real download, the redirect is followed, and
the server log matches. The "after" run uses the b1 build with 0015 (builds 39133490079 / 39133494814).
