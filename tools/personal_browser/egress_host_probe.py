#!/usr/bin/env python3
"""Host execution of selected personal egress components, NEVER Android acceptance.

Compiles the real patched Clipboard base/private subclass and snapshot controller
with explicit Android/Chromium/JNI stubs. The native download-path predicate is
compiled directly, without Chromium stubs, with ASan/UBSan. Neither probe runs a
browser, downloads a file, invokes Android Binder or proves filesystem/encryption
or real screen/clipboard isolation. It only uses caller-owned synthetic source.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

JAVA_PATHS = {
    "org/chromium/ui/base/Clipboard.java": "ui/android/java/src/org/chromium/ui/base/Clipboard.java",
    "org/chromium/ui/base/BrowserContainedClipboard.java": "ui/android/java/src/org/chromium/ui/base/BrowserContainedClipboard.java",
    "org/chromium/chrome/browser/incognito/IncognitoSnapshotController.java": "chrome/android/java/src/org/chromium/chrome/browser/incognito/IncognitoSnapshotController.java",
}
PATH_HEADER = "chrome/browser/download/browser_contained_download_path.h"
STUBS = {
    "android/content/Context.java": '''package android.content;
public class Context {
 public static final String CLIPBOARD_SERVICE = "clipboard";
 public Object getSystemService(String name) { throw new AssertionError("OS clipboard/service access"); }
}''',
    "android/content/ClipboardManager.java": '''package android.content;
public class ClipboardManager {}''',
    "android/content/ClipData.java": '''package android.content;
public class ClipData { public ClipData() { throw new AssertionError("external clip construction"); } }''',
    "android/net/Uri.java": '''package android.net;
public class Uri { public static Uri parse(String value) { throw new AssertionError("external URI access"); } }''',
    "android/os/Build.java": '''package android.os;
public class Build {
 public static class VERSION { public static int SDK_INT = 36; }
 public static class VERSION_CODES { public static final int Q = 29, TIRAMISU = 33; }
}''',
    "android/view/WindowManager.java": '''package android.view;
public interface WindowManager {
 public static class LayoutParams { public static final int FLAG_SECURE = 0x2000; public int flags; }
}''',
    "android/view/Window.java": '''package android.view;
public class Window {
 private final WindowManager.LayoutParams attributes = new WindowManager.LayoutParams();
 public WindowManager.LayoutParams getAttributes() { return attributes; }
 public void addFlags(int flags) { attributes.flags |= flags; }
 public void clearFlags(int flags) { throw new AssertionError("secure flags cleared"); }
}''',
    "android/app/Activity.java": '''package android.app;
public class Activity {
 private final android.view.Window window = new android.view.Window();
 public boolean recentsEnabled = true;
 public android.view.Window getWindow() { return window; }
 public void setRecentsScreenshotEnabled(boolean enabled) {
  if (android.os.Build.VERSION.SDK_INT < 33) throw new AssertionError("unsupported API");
  if (enabled) throw new AssertionError("private recents enabled");
  recentsEnabled = enabled;
 }
}''',
    "org/chromium/base/Callback.java": '''package org.chromium.base;
public interface Callback<T> { void onResult(T result); }''',
    "org/chromium/base/ContextUtils.java": '''package org.chromium.base;
public class ContextUtils {
 public static android.content.Context getApplicationContext() { return new android.content.Context(); }
}''',
    "org/chromium/base/Log.java": '''package org.chromium.base;
public class Log { public static void w(String tag, String message) {} }''',
    "org/chromium/base/ResettersForTesting.java": '''package org.chromium.base;
public class ResettersForTesting { public static void register(Runnable callback) {} }''',
    "org/chromium/url/GURL.java": '''package org.chromium.url;
public class GURL {
 private final String spec;
 public GURL(String spec) { this.spec = spec; }
 public String getSpec() { return spec; }
}''',
    "org/chromium/ui/base/ClipboardImpl.java": '''package org.chromium.ui.base;
public class ClipboardImpl extends Clipboard {
 public ClipboardImpl(android.content.ClipboardManager manager) {
  throw new AssertionError("platform clipboard backend selected");
 }
}''',
    "org/chromium/ui/base/ClipboardJni.java": '''package org.chromium.ui.base;
public class ClipboardJni {
 public static int changes;
 private static final Clipboard.Natives INSTANCE = new Clipboard.Natives() {
  public void onPrimaryClipChanged(long ptr) { changes++; }
  public void onPrimaryClipTimestampInvalidated(long ptr, long timestamp) {
   throw new AssertionError("unexpected OS clipboard timestamp invalidation");
  }
  public long getLastModifiedTimeToJavaTime(long ptr) { return 0; }
  public void cleanupForTesting() {}
 };
 public static Clipboard.Natives get() { return INSTANCE; }
}''',
}

for package, name, arguments in (
    ("android.annotation", "SuppressLint", "String[] value();"),
    ("androidx.annotation", "VisibleForTesting", ""),
    ("org.chromium.build.annotations", "NullMarked", ""),
    ("org.chromium.build.annotations", "Nullable", ""),
    ("org.jni_zero", "CalledByNative", ""),
    ("org.jni_zero", "JNINamespace", "String value();"),
    ("org.jni_zero", "JniType", "String value();"),
    ("org.jni_zero", "NativeMethods", ""),
):
    STUBS[package.replace(".", "/") + "/" + name + ".java"] = (
        "package " + package + ";\n"
        "@java.lang.annotation.Target({java.lang.annotation.ElementType.TYPE_USE, "
        "java.lang.annotation.ElementType.TYPE, java.lang.annotation.ElementType.METHOD, "
        "java.lang.annotation.ElementType.PARAMETER, java.lang.annotation.ElementType.FIELD, "
        "java.lang.annotation.ElementType.CONSTRUCTOR})\n"
        "public @interface " + name + " {" + arguments + "}")

JAVA_PROBE = '''package org.chromium.ui.base;
import java.util.HashMap;
import java.util.Map;
import android.app.Activity;
import android.os.Build;
import android.view.WindowManager;
import org.chromium.chrome.browser.incognito.IncognitoSnapshotController;
import org.chromium.url.GURL;

public class PersonalEgressHostProbe {
 private static int checks;
 private static void check(boolean good) { checks++; if (!good) throw new AssertionError("contract " + checks); }
 private static class Snapshot extends IncognitoSnapshotController {
  Snapshot(Activity activity) { super(activity, () -> { throw new AssertionError("incognito state consulted"); }); }
  void update() { updateIncognitoTabSnapshotState(); }
 }
 public static void main(String[] args) {
  Clipboard.resetForTesting();
  Clipboard clip = Clipboard.getInstance();
  check(clip instanceof BrowserContainedClipboard);
  check(Clipboard.getInstance() == clip);
  clip.setNativePtr(1);
  check(clip.canCopy() && !clip.canPaste());
  check(clip.getCoercedText() == null && clip.getHTMLText() == null);
  check(clip.getLastModifiedTimeMs() == 0);
  clip.setText("synthetic private text");
  check("synthetic private text".equals(clip.getCoercedText()));
  check(clip.hasCoercedText() && clip.canPaste());
  check(clip.hasClipboardDataForMimeType("text/plain"));
  long first = clip.getLastModifiedTimeMs(); check(first > 0);
  clip.onWindowFocusChanged(false); clip.onWindowFocusChanged(true);
  check("synthetic private text".equals(clip.getCoercedText()));
  check(clip.getLastModifiedTimeMs() == first);
  clip.setText("private label", "second"); check("second".equals(clip.getCoercedText()));
  clip.setText("private label", "third", true); check("third".equals(clip.getCoercedText()));
  clip.setHTMLText("<b>synthetic</b>", "synthetic");
  check("<b>synthetic</b>".equals(clip.getHTMLText()));
  check("synthetic".equals(clip.getCoercedText()) && clip.hasHTMLOrStyledText());
  Map<String, String> values = new HashMap<>();
  values.put("text/plain", "local"); values.put("chromium/x-web-custom-data", "local custom");
  clip.setClipboardText(values); values.put("text/plain", "mutated caller");
  check("local".equals(clip.getCoercedText()));
  check("local custom".equals(clip.getCustomClipData("chromium/x-web-custom-data")));
  check(clip.hasClipboardDataForMimeType("chromium/x-web-custom-data"));
  clip.setPassword("synthetic-not-a-real-password");
  check("synthetic-not-a-real-password".equals(clip.getCoercedText()));
  clip.copyUrlToClipboard(new GURL("https://example.com/"));
  check(clip.hasUrl() && "https://example.com/".equals(clip.getUrl()));
  clip.setText("https://example.com/ not a single URL"); check(!clip.hasUrl());
  clip.setText("javascript:synthetic"); check(!clip.hasUrl());
  clip.setImageFileProvider(new Clipboard.ImageFileProvider() {
   public void storeImageAndGenerateUri(byte[] data, String extension, org.chromium.base.Callback<android.net.Uri> callback) {
    throw new AssertionError("image export provider used");
   }
   public void storeLastCopiedImageMetadata(Clipboard.ClipboardUriMetadata value) { throw new AssertionError("URI export metadata"); }
   public Clipboard.ClipboardUriMetadata getLastCopiedImageMetadata() { throw new AssertionError("URI metadata read"); }
   public void clearLastCopiedImageMetadata() { throw new AssertionError("URI metadata deletion"); }
  });
  byte[] png = {(byte)137,80,78,71,13,10,26,10,11}; // Signature fixture, NOT a decoded image test.
  clip.setImage(png, "png"); png[8] = 99;
  check(clip.hasImage() && clip.getPng()[8] == 11);
  byte[] copy = clip.getPng(); copy[8] = 98;
  check(clip.getPng()[8] == 11);
  check(clip.getCoercedText() == null && clip.hasClipboardDataForMimeType("image/png"));
  clip.setImage(new byte[] {1,2,3}, "png"); check(clip.getPng()[8] == 11);
  check(clip.getImageUri() == null && clip.getImageUriIfSharedByThisApp() == null);
  check(clip.getImageUriString() == null && !clip.hasFilenames() && clip.getFilenames() == null);
  clip.setImageUri(null); clip.setImageUri(null, true); clip.setImageUri(null, null, true);
  clip.setFilenames(new String[] {"content://synthetic/not-opened"});
  check(clip.getPng()[8] == 11 && !clip.hasFilenames());
  clip.clear(); check(!clip.canPaste() && !clip.hasImage() && clip.getCoercedText() == null);
  check(clip.getLastModifiedTimeMs() > first);
  check(ClipboardJni.changes > 0);
  for (int sdk : new int[] {29, 32, 33, 36}) {
   Build.VERSION.SDK_INT = sdk;
   Activity activity = new Activity(); Snapshot snapshot = new Snapshot(activity);
   snapshot.update(); snapshot.update();
   check((activity.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_SECURE) != 0);
   check(activity.recentsEnabled == (sdk < 33));
  }
  System.out.println("PERSONAL_EGRESS_HOST_PROBE assertions=" + checks);
 }
}
'''

CPP_PROBE = '''#include <iostream>
#include <string>
#include <string_view>
#include "browser_contained_download_path.h"
static std::string decode(const std::string& input) {
 std::string result;
 for (std::size_t i = 0; i < input.size(); i += 2) {
  result.push_back(static_cast<char>(std::stoul(input.substr(i, 2), nullptr, 16)));
 }
 return result;
}
int main() {
 std::string line;
 while (std::getline(std::cin, line)) {
  const auto split = line.find(' ');
  if (split == std::string::npos) return 2;
  const auto root = decode(line.substr(0, split));
  const auto path = decode(line.substr(split + 1));
  std::cout << (download::IsBrowserContainedDownloadPath(root, path) ? "1" : "0") << '\\n';
 }
 return 0;
}
'''


def run_java(src: Path, overrides: dict[str, str] | None = None) -> dict:
    if not shutil.which("java") or not shutil.which("javac"):
        raise RuntimeError("host_JDK_missing")
    actual = {key: (src / relative).read_text() for key, relative in JAVA_PATHS.items()}
    for key, value in (overrides or {}).items():
        if key not in actual:
            raise ValueError("unexpected_source_override")
        actual[key] = value
    report = {"test_type": "HOST JVM; REAL THREE SOURCE CLASSES; ANDROID/JNI DEPENDENCIES STUBBED",
              "product_containment": "NOT RUN / NOT CERTIFIED", "dependency_stubs": True,
              "source_sha256": {key: hashlib.sha256(value.encode()).hexdigest() for key, value in actual.items()},
              "mutation_control": bool(overrides)}
    with tempfile.TemporaryDirectory(prefix="personal-egress-java-") as temp:
        root = Path(temp)
        files = {**STUBS, **actual,
                 "org/chromium/ui/base/PersonalEgressHostProbe.java": JAVA_PROBE}
        paths = []
        for relative, text in files.items():
            path = root / "src" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            paths.append(str(path))
        compiled = subprocess.run(["javac", "-Xlint:all", "-Werror", "-d", str(root / "classes"), *sorted(paths)],
                                  text=True, capture_output=True, timeout=45)
        report["compiler_exit"] = compiled.returncode
        if compiled.returncode:
            report.update(status="FAIL (host compile)", diagnostic=compiled.stderr[-4000:])
            return report
        run = subprocess.run(["java", "-ea", "-cp", str(root / "classes"),
                              "org.chromium.ui.base.PersonalEgressHostProbe"],
                             text=True, capture_output=True, timeout=30)
        report.update(runtime_exit=run.returncode, output=run.stdout.strip(), diagnostic=run.stderr[-4000:])
        found = re.fullmatch(r"PERSONAL_EGRESS_HOST_PROBE assertions=(\d+)", run.stdout.strip())
        report["assertions"] = int(found[1]) if found else 0
        report["status"] = "PASS (host component with stubs)" if run.returncode == 0 and found else "FAIL (host component)"
    return report


def run_paths(src: Path, cases: list[tuple[bytes, bytes, bool]], override: str | None = None) -> dict:
    if not shutil.which("g++"):
        raise RuntimeError("host_CXX_missing")
    header = (src / PATH_HEADER).read_text() if override is None else override
    report = {"test_type": "HOST C++ ACTUAL PRODUCTION PREDICATE; NO ANDROID/DOWNLOAD FILESYSTEM OPERATIONS",
              "dependency_stubs": False, "sanitizers": ["address", "undefined"],
              "product_containment": "NOT RUN / NOT CERTIFIED",
              "source_sha256": hashlib.sha256(header.encode()).hexdigest(),
              "mutation_control": override is not None, "checks": len(cases)}
    with tempfile.TemporaryDirectory(prefix="personal-egress-cpp-") as temp:
        folder = Path(temp)
        (folder / "browser_contained_download_path.h").write_text(header)
        (folder / "probe.cc").write_text(CPP_PROBE)
        compiled = subprocess.run(
            ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-O2",
             "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-I", str(folder),
             str(folder / "probe.cc"), "-o", str(folder / "probe")],
            text=True, capture_output=True, timeout=45)
        report["compiler_exit"] = compiled.returncode
        if compiled.returncode:
            report.update(status="FAIL (host compile)", diagnostic=compiled.stderr[-4000:])
            return report
        payload = "".join(root.hex() + " " + path.hex() + "\n" for root, path, _ in cases)
        run = subprocess.run([str(folder / "probe")], input=payload, text=True,
                             capture_output=True, timeout=30)
        report["runtime_exit"] = run.returncode
        report["diagnostic"] = run.stderr[-4000:]
        lines = run.stdout.splitlines()
        mismatches = [i for i, (_, _, expected) in enumerate(cases)
                      if i >= len(lines) or lines[i] != ("1" if expected else "0")]
        report["mismatch_indices"] = mismatches[:20]
        report["output_lines"] = len(lines)
        report["status"] = ("PASS (host native predicate, sanitized)" if run.returncode == 0
                            and len(lines) == len(cases) and not mismatches else "FAIL (host native predicate)")
    return report
