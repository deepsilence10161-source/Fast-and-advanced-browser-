#!/usr/bin/env python3
"""Regenerate patches/personal/0114-personal-gemini-chat.patch and its source guard 0114-...-source-guard.py.

Pristine Chromium 158.0.8127.42 files come from raw.githubusercontent.com (cached in CACHE). The earlier personal patches
that touch the same files (0105 and 0112 edit chrome_java_sources.gni) are applied first, so the new patch is written
against the tree state it will really meet. New Java files are read from tools/swiftra_gemini/src. Usage: regen_patch.py [--check]
"""
import hashlib, os, re, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAG = os.environ.get("CHROMIUM_TAG", "158.0.8127.42")
CACHE = Path(os.environ.get("CACHE", "/home/user/w/cache158")) / TAG
PATCH = ROOT / "patches/personal/0114-personal-gemini-chat.patch"
GUARD = ROOT / "patches/personal/0114-personal-gemini-source-guard.py"

GNI = "chrome/android/chrome_java_sources.gni"
PREFS = "chrome/android/java/res/xml/main_preferences.xml"
MAIN = "chrome/android/java/src/org/chromium/chrome/browser/settings/MainSettings.java"
BRIDGE = "chrome/browser/browsing_data/android/java/src/org/chromium/chrome/browser/browsing_data/BrowsingDataBridge.java"
BUILD = "chrome/browser/browsing_data/android/BUILD.gn"
EDITED = [GNI, PREFS, MAIN, BRIDGE, BUILD]
NEW = {
    "chrome/android/java/src/org/chromium/chrome/browser/swiftra/gemini/SwiftraGemini.java": "src/SwiftraGemini.java",
    "chrome/browser/browsing_data/android/java/src/org/chromium/chrome/browser/browsing_data/SwiftraKeepSignin.java": "src/SwiftraKeepSignin.java",
}
EARLIER = ["0101-persistent-account-boundary.patch", "0103-personal-egress-and-storage.patch",
           "0105-face-guard-presence-mode.patch", "0107-personal-signin-message.patch",
           "0109-personal-omnibox-clipboard.patch", "0111-personal-google-egress.patch",
           "0112-personal-relax-clipboard-files-signin-scrub.patch", "0113-personal-158-screenshot-protection.patch"]


def fetch(rel):
    p = CACHE / rel
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(urllib.request.urlopen(f"https://raw.githubusercontent.com/chromium/chromium/{TAG}/{rel}", timeout=60).read())
    return p.read_bytes()


def sections(patch_text):
    parts = re.split(r"(?m)^(?=--- (?:a/|/dev/null))", patch_text)
    return [s for s in parts if s.startswith("--- ")]


def one(text, old, new):
    assert text.count(old) == 1, ("anchor count", text.count(old), old[:70])
    return text.replace(old, new)


def edit(rel, text):
    if rel == GNI:
        return one(text, '  "java/src/org/chromium/chrome/browser/swiftra/faceguard/PresenceFaceAnalyzer.java",\n',
                   '  "java/src/org/chromium/chrome/browser/swiftra/faceguard/PresenceFaceAnalyzer.java",\n'
                   '  "java/src/org/chromium/chrome/browser/swiftra/gemini/SwiftraGemini.java",\n')
    if rel == PREFS:
        anchor = ('    <org.chromium.chrome.browser.ui.settings_promo_card.SettingsPromoCardPreference\n'
                  '        android:key="settings_promo_card"\n        android:order="0" />\n')
        add = ('    <org.chromium.components.browser_ui.settings.ChromeBasePreference\n'
               '        android:key="swiftra_gemini"\n        android:order="-3"\n        android:title="Gemini chat"\n'
               '        android:summary="Chat with Gemini in a browser tab, signed in with one Google account. Your chats and what Gemini remembers are kept by Google in that account, not by Swiftra, and Delete browsing data never removes them."\n'
               '        android:persistent="false" />\n'
               '    <org.chromium.components.browser_ui.settings.ChromeBasePreference\n'
               '        android:key="swiftra_gemini_activity"\n        android:order="-2"\n        android:title="Gemini chat history"\n'
               '        android:summary="Review or delete your saved Gemini chats (Google account activity)."\n'
               '        android:persistent="false" />\n'
               '    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference\n'
               '        android:key="swiftra_gemini_keep_signin"\n        android:order="-1"\n'
               '        android:title="Stay signed in to Google after deleting data"\n'
               '        android:summary="On: Delete browsing data keeps the cookies, site storage and cached pages of google.com so Gemini stays linked to your account. History and every other site are still deleted. Off: you are signed out of Google each time."\n'
               '        android:persistent="false" />\n')
        return one(text, anchor, anchor + add)
    if rel == MAIN:
        text = one(text, "import org.chromium.chrome.browser.signin.services.SigninManager;\n",
                   "import org.chromium.chrome.browser.signin.services.SigninManager;\n"
                   "import org.chromium.chrome.browser.swiftra.gemini.SwiftraGemini;\n")
        return one(text, "        SettingsUtils.addPreferencesFromResource(this, R.xml.main_preferences);\n",
                   "        SettingsUtils.addPreferencesFromResource(this, R.xml.main_preferences);\n"
                   "        SwiftraGemini.setUp(this, getActivity());\n")
    if rel == BRIDGE:
        return one(text, "            String @Nullable [] ignoredDomains) {\n        BrowsingDataBridgeJni.get()\n",
                   "            String @Nullable [] ignoredDomains) {\n"
                   "        // Swiftra personal: keep the Google web sign-in (Gemini chats live in that account).\n"
                   "        excludedDomains = SwiftraKeepSignin.withKeptDomains(excludedDomains);\n"
                   "        BrowsingDataBridgeJni.get()\n")
    if rel == BUILD:
        text = one(text, '    "java/src/org/chromium/chrome/browser/browsing_data/BrowsingDataBridge.java",\n    "java/src/org/chromium/chrome/browser/browsing_data/TimePeriodUtils.java",\n',
                   '    "java/src/org/chromium/chrome/browser/browsing_data/BrowsingDataBridge.java",\n'
                   '    "java/src/org/chromium/chrome/browser/browsing_data/SwiftraKeepSignin.java",\n'
                   '    "java/src/org/chromium/chrome/browser/browsing_data/TimePeriodUtils.java",\n')
        return one(text, '    "//base:callback_java",\n', '    "//base:base_java",\n    "//base:callback_java",\n')
    raise KeyError(rel)


def build_trees(d):
    a, b = Path(d) / "a", Path(d) / "b"
    for rel in EDITED:
        for base in (a, b):
            (base / rel).parent.mkdir(parents=True, exist_ok=True)
            (base / rel).write_bytes(fetch(rel))
    # bring both trees to the state after the earlier personal patches (only their sections for our files)
    for name in EARLIER:
        txt = (ROOT / "patches/personal" / name).read_text()
        keep = [s for s in sections(txt) if re.match(r"--- a/(\S+)", s) and re.match(r"--- a/(\S+)", s).group(1) in EDITED]
        if not keep:
            continue
        sub = Path(d) / "sub.patch"
        sub.write_text("".join(keep))
        for base in (a, b):
            subprocess.run(["patch", "-d", str(base), "-p1", "--forward", "--batch", "--no-backup-if-mismatch", "--fuzz=0", "-i", str(sub)],
                           check=True, capture_output=True)
    return a, b


def guard_text(hashes):
    tpl = (ROOT / "patches/personal/0104-face-guard-source-guard.py").read_text()
    tpl = re.sub(r"(?s)EXPECTED = \{.*?\n\}\n", "EXPECTED = {\n" + ",\n".join(f'    "{k}": "{v}"' for k, v in sorted(hashes.items())) + "\n}\n", tpl, count=1)
    tpl = re.sub(r"NEW_PATHS = \(.*?\)\n", "NEW_PATHS = (" + ", ".join(repr(k) for k in sorted(NEW)) + ")\n", tpl, count=1)
    tpl = tpl.replace("before the opt-in Face Guard (presence mode) patch writes anything", "before the opt-in Gemini chat patch (0114) writes anything")
    tpl = tpl.replace("The pinned files are not modified by any earlier patch.", "Pinned hashes are the file state AFTER the earlier personal patches (chrome_java_sources.gni after 0105 and 0112).")
    tpl = tpl.replace("Face Guard behaviour", "Gemini chat behaviour").replace("0104-face-guard-source-guard.py", "0114-personal-gemini-source-guard.py")
    tpl = re.sub(r"Runs AFTER .*?\n", "Runs AFTER the ordinary series and personal 0100-0113 on a restored Chromium 158.0.8127.42 tree.\n", tpl, count=1)
    return tpl


def main():
    check = "--check" in sys.argv
    with tempfile.TemporaryDirectory() as d:
        a, b = build_trees(d)
        hashes = {rel: hashlib.sha256((a / rel).read_bytes()).hexdigest() for rel in EDITED}
        for rel in EDITED:
            (b / rel).write_text(edit(rel, (b / rel).read_text()))
        for rel, src in NEW.items():
            (b / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / "tools/swiftra_gemini" / src, b / rel)
        r = subprocess.run(["git", "diff", "--no-index", "--no-color", "a", "b"], cwd=d, capture_output=True, text=True)
        out = r.stdout
        out = re.sub(r"^diff --git a/a/(.*?) b/b/", r"diff --git a/\1 b/", out, flags=re.M)
        out = re.sub(r"^diff --git a/b/(.*) b/b/(.*)$", r"diff --git a/\1 b/\2", out, flags=re.M)
        out = re.sub(r"^--- a/a/", "--- a/", out, flags=re.M)
        out = re.sub(r"^\+\+\+ b/b/", "+++ b/", out, flags=re.M)
        out = re.sub(r"(?m)^diff --git .*\n(?:new file mode .*\n)?(?:index .*\n)?", lambda m: "", out)
        guard = guard_text(hashes)
        if check:
            ok = PATCH.exists() and PATCH.read_text() == out and GUARD.exists() and GUARD.read_text() == guard
            print("0114 is %s" % ("up to date" if ok else "STALE: run tools/swiftra_gemini/regen_patch.py"))
            return 0 if ok else 1
        PATCH.write_text(out)
        GUARD.write_text(guard)
        os.chmod(GUARD, 0o755)
        print("wrote", PATCH.name, len(out.splitlines()), "lines;", GUARD.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
