#!/usr/bin/env python3
"""Re-target the whole patch series onto another Chromium tag and rewrite the patch files with zero offsets.

For every .patch in series order: apply onto the tag's pristine files (fuzz allowed), repair rejected hunks with the
explicit FIXES below, then write a fresh offset-free diff (pre -> post). Guards: their EXPECTED hashes are refreshed
from the tree state at that point. Transform scripts that need the full tree (0002 needs grit) are NOT run here.
Source preparation only: no compile, no device."""
import pathlib, time, sys, os, re, json, difflib, hashlib, subprocess, shutil, pathlib, urllib.request, urllib.error, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import patches as P

TAG = sys.argv[1]
WORK = pathlib.Path(sys.argv[2])
_DROP3 = ["ui/android/java/src/org/chromium/ui/base/Clipboard.java",
          "components/browser_ui/share/android/java/src/org/chromium/components/browser_ui/share/ShareHelper.java",
          "chrome/android/java/src/org/chromium/chrome/browser/download/DownloadUtils.java"]
# clipboard / share / open-file are NOT contained in this branch: those sections are dropped from 0103 and 0112
DROP = {"0103-personal-egress-and-storage.patch": _DROP3 + ["ui/android/BUILD.gn", "ui/android/java/src/org/chromium/ui/base/BrowserContainedClipboard.java"],
        "0112-personal-relax-clipboard-files-signin-scrub.patch": _DROP3}

CACHE = pathlib.Path("/home/user/w/cache158")


def fetch(f, tag=None):
    tag = tag or TAG
    cp = CACHE / tag / f
    if cp.exists():
        d = cp.read_bytes()
        return None if d == b"\x00404" else d
    u = f"https://raw.githubusercontent.com/chromium/chromium/{tag}/{f}"
    for n in range(8):
        try:
            d = urllib.request.urlopen(u, timeout=60).read()
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_bytes(d)
            return d
        except urllib.error.HTTPError as e:
            if e.code == 404:
                cp.parent.mkdir(parents=True, exist_ok=True)
                cp.write_bytes(b"\x00404")
                return None
            time.sleep(20 * (n + 1) if e.code == 429 else 3)
        except Exception:
            time.sleep(3)
    return b"ERR"

def split_sections(text):
    lines = text.splitlines(keepends=True)
    starts = [i for i, l in enumerate(lines) if l.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ ")]
    out = []
    for n, s in enumerate(starts):
        e = starts[n + 1] if n + 1 < len(starts) else len(lines)
        while e - 1 > s and lines[e - 1].startswith(("diff --git", "index ", "new file", "similarity", "deleted file")):
            e -= 1
        h = lines[s + 1][4:].split("\t")[0].strip()
        h = h[2:] if h.startswith("b/") else h
        out.append((h, "".join(lines[s:e])))
    return out

def make_diff(path, pre, post):
    a = pre.splitlines(keepends=True) if pre is not None else []
    b = post.splitlines(keepends=True)
    fa = f"a/{path}" if pre is not None else "/dev/null"
    return "".join(difflib.unified_diff(a, b, fa, f"b/{path}", n=3))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

BASE_TAG = "155.0.8059.80"   # the tag the series was written against (zero-context hunks are line-addressed to it)

def u0_sections(text):
    """Files whose hunks carry no context line (diff -U0 style). Applying those by line number to another tag silently
    lands in the wrong place (seen: 0103 download_prefs.cc inside DefaultDownloadDirectory), so they are re-derived
    semantically: apply to the BASE tag tree, take a context diff, apply THAT to the target tag."""
    out = set()
    for h, sec in split_sections(text):
        if sec.startswith("--- /dev/null"):
            continue
        hunks, cur = [], None
        for l in sec.splitlines():
            if l.startswith("@@"):
                cur = {"ctx": False}; hunks.append(cur)
            elif cur is not None and l.startswith(" "):
                cur["ctx"] = True
        if hunks and any(not x["ctx"] for x in hunks):
            out.add(h)
    return out

# sections that must never go through fuzzy `patch` (it silently lands them in the wrong function): the FIX is the source of truth
ALWAYS_FIX = {"0011-swiftra-fingerprint-shield.patch": ["third_party/blink/renderer/modules/webaudio/offline_audio_context.cc"]}

UNFIXED = []
# files whose rejected hunks are placed by an explicit FIX (fuzzy retry mislocates them: seen in download_target_determiner.cc)
NO_FUZZ = {"chrome/browser/download/download_target_determiner.cc",
           "components/external_intents/android/java/src/org/chromium/components/external_intents/ExternalNavigationHandler.java",
           "chrome/android/java/AndroidManifest.xml"}
FIXES = {}
def fix(name):
    def deco(fn):
        FIXES[name] = fn; return fn
    return deco

@fix("0009-swiftra-quiet-start.patch")
def _(root):
    p = root / "chrome/browser/ui/android/logo/logo_bridge.cc"
    t = p.read_text()
    m = re.search(r"void LogoBridge::RecordImpression\([^)]*\) \{\n.*?\n\}\n", t, re.S)
    assert m, "RecordImpression not found"
    body = ("void LogoBridge::RecordImpression(std::string_view log_url) {\n"
            "  // Swiftra: the doodle is still shown; only the impression ping to Google\n"
            "  // (doodle_impression_android, logging only) is not sent.\n}\n")
    p.write_text(t[:m.start()] + body + t[m.end():])

@fix("0010-swiftra-advanced-defaults.patch")
def _(root):  # the tag already enables kHttpsFirstBalancedModeAutoEnable upstream
    t = (root / "chrome/common/chrome_features.cc").read_text()
    assert re.search(r"kHttpsFirstBalancedModeAutoEnable,\s*base::FEATURE_ENABLED_BY_DEFAULT", t)

@fix("0011-swiftra-fingerprint-shield.patch")
def _(root):  # 158 renders OfflineAudioContext in chunks: noise the target right before its promise is resolved
    p = root / "third_party/blink/renderer/modules/webaudio/offline_audio_context.cc"
    t = p.read_text()
    inc = '#include "third_party/blink/renderer/core/frame/local_dom_window.h"\n'
    assert t.count(inc) == 1
    t = t.replace(inc, inc + '#include "third_party/blink/renderer/core/frame/swiftra_fingerprint_shield.h"\n')
    anchor = "  CHECK(rendered_buffer);\n  // Keep the target queued across `Resolve()`"
    assert t.count(anchor) == 1
    add = ("  CHECK(rendered_buffer);\n"
           "  // Swiftra fingerprint shield (core/frame/swiftra_fingerprint_shield.h).\n"
           "  if (const uint64_t key = SwiftraFingerprintKey(GetExecutionContext())) {\n"
           "    for (unsigned channel = 0; channel < rendered_buffer->numberOfChannels();\n"
           "         ++channel) {\n"
           "      base::span<float> samples =\n"
           "          rendered_buffer->getChannelData(channel)->AsSpan();\n"
           "      SwiftraNoiseAudio(key, samples.data(), samples.size(), channel);\n"
           "    }\n  }\n  // Keep the target queued across `Resolve()`")
    p.write_text(t.replace(anchor, add))


def _ins_after(t, anchor, add, n=1):
    assert t.count(anchor) == n, (anchor, t.count(anchor))
    return t.replace(anchor, anchor + add)

@fix("0101-persistent-account-boundary.patch")
def _(root):  # 158 hard-codes zygotePreloadName; the backup attributes are unchanged
    p = root / "chrome/android/java/AndroidManifest.xml"
    t = p.read_text()
    old = ('        {% if backup_key is defined %}\n        android:allowBackup="true"\n'
           '        android:backupAgent="org.chromium.chrome.browser.backup.ChromeBackupAgent"\n'
           '        android:fullBackupOnly="false"\n        android:restoreAnyVersion="true"\n'
           '        {% else %}\n        android:allowBackup="false"\n        {% endif %}\n')
    new = ('        android:allowBackup="false"\n        android:fullBackupContent="false"\n'
           '        android:dataExtractionRules="@xml/personal_no_data_transfer"\n'
           '        android:restoreAnyVersion="false"\n        tools:remove="android:backupAgent"\n')
    assert t.count(old) == 1
    p.write_text(t.replace(old, new))

_DTD_GEN = ("#if BUILDFLAG(IS_ANDROID)\n  if (DownloadPrefs::GetDefaultDownloadDirectory().empty()) {\n"
            "    ScheduleCallbackAndDeleteSelf(\n        download::DOWNLOAD_INTERRUPT_REASON_FILE_ACCESS_DENIED);\n"
            "    return QUIT_DOLOOP;\n  }\n#endif\n")
_DTD_CHK = ("#if BUILDFLAG(IS_ANDROID)\n  if (!download::IsBrowserContainedDownloadPath(\n"
            "          DownloadPrefs::GetDefaultDownloadDirectory().value(), %s)) {\n"
            "    ScheduleCallbackAndDeleteSelf(\n        download::DOWNLOAD_INTERRUPT_REASON_FILE_ACCESS_DENIED);\n"
            "    %s;\n  }\n#endif\n")

@fix("0103-personal-egress-and-storage.patch")
def _(root):
    # (a) download_target_determiner.cc: 158 turned DCHECKs into CHECK(..., NotFatalUntil::M161); fuzzy patch put two of the
    # hunks INSIDE a CHECK(...) call, so all five hunks are placed here by exact anchors (counted == 1)
    p = root / "chrome/browser/download/download_target_determiner.cc"
    t = p.read_text()
    def put(t, anchor, add, where):
        assert t.count(anchor) == 1, anchor
        return t.replace(anchor, add + anchor if where == "before" else anchor + add)
    t = put(t, "  CHECK(!should_notify_extensions_, base::NotFatalUntil::M161);\n", _DTD_GEN, "after")
    t = put(t, "  CHECK(!virtual_path_.empty(), base::NotFatalUntil::M161);\n\n  next_state_ = STATE_PROMPT_USER_FOR_DOWNLOAD_PATH;\n",
            (_DTD_CHK % ("virtual_path_.value()", "return QUIT_DOLOOP")) + "\n"
            "#if BUILDFLAG(IS_ANDROID)\n  create_target_directory_ = true;  // The checked private root is created by reservation IO.\n#endif\n",
            "before") if False else t
    # DoReserveVirtualPath: check after the CHECKs, then create_target_directory_, then next_state_
    a2 = "  CHECK(!virtual_path_.empty(), base::NotFatalUntil::M161);\n\n  next_state_ = STATE_PROMPT_USER_FOR_DOWNLOAD_PATH;\n"
    assert t.count(a2) == 1
    blk2 = ((_DTD_CHK % ("virtual_path_.value()", "return QUIT_DOLOOP")) + "\n"
            "#if BUILDFLAG(IS_ANDROID)\n  create_target_directory_ = true;  // The checked private root is created by reservation IO.\n#endif\n")
    t = t.replace(a2, "  CHECK(!virtual_path_.empty(), base::NotFatalUntil::M161);\n\n" + blk2 + "  next_state_ = STATE_PROMPT_USER_FOR_DOWNLOAD_PATH;\n")
    # ReserveVirtualPathDone
    a3 = ("  CHECK(BrowserThread::CurrentlyOn(BrowserThread::UI),\n        base::NotFatalUntil::M161);\n"
          '  DVLOG(20) << "Reserved path: " << path.AsUTF8Unsafe()\n')
    assert t.count(a3) == 1
    t = t.replace(a3, a3.split("  DVLOG")[0] + (_DTD_CHK % ("path.value()", "return")) + "\n  DVLOG" + a3.split("  DVLOG")[1])
    # DoDetermineLocalPath
    a4 = "  CHECK(local_path_.empty(), base::NotFatalUntil::M161);\n\n  next_state_ = STATE_DETERMINE_MIME_TYPE;\n"
    assert t.count(a4) == 1
    t = t.replace(a4, "  CHECK(local_path_.empty(), base::NotFatalUntil::M161);\n\n" + (_DTD_CHK % ("virtual_path_.value()", "return QUIT_DOLOOP")) + "\n  next_state_ = STATE_DETERMINE_MIME_TYPE;\n")
    # DetermineLocalPathDone
    b = "  CHECK_EQ(STATE_DETERMINE_MIME_TYPE, next_state_, base::NotFatalUntil::M161);\n"
    assert t.count(b) == 1
    t = t.replace(b, b + "\n" + (_DTD_CHK % ("local_path.value()", "return")))
    p.write_text(t)
    # (b) ExternalNavigationHandler.java: startActivity() lost the @Nullable on intentTargetUrl in 158
    f = "components/external_intents/android/java/src/org/chromium/components/external_intents/ExternalNavigationHandler.java"
    rej = (root.parent / "rejs" / "0103_ExternalNavigationHandler.java.rej").read_text()
    hunk = rej[rej.index("@@"):]                 # both hunks (startActivity/doStartActivity bodies; startActivityWithChooser)
    old_ctx = "            @Nullable GURL intentTargetUrl) {\n"
    assert hunk.count(old_ctx) == 1
    hunk = hunk.replace(old_ctx, "            GURL intentTargetUrl) {\n")
    hdr = f"--- {f}\n+++ {f}\n"
    tmp = root.parent / "_enh.patch"; tmp.write_text(hdr + hunk + "\n")
    r = subprocess.run(["patch", "-p0", "--fuzz=1", "--batch", "--forward", "--no-backup-if-mismatch", f, "-i", str(tmp)],
                       cwd=root, capture_output=True, text=True)
    print("      FIX ENH:", r.returncode, r.stdout.strip().replace("\n", " | ")[:300])
    assert r.returncode == 0

def main():
    order = [(d, n) for d in ("patches", "patches/personal") for n in P.read_series(str(ROOT / d))]
    files = set()
    for d, name in order:
        pf = ROOT / d / name
        if name.endswith(".patch") and not name.startswith("0000"):
            drop = set(DROP.get(name, []))
            files.update(h for h, _ in split_sections(pf.read_text()) if h not in drop and h != "/dev/null")
        elif name.endswith(".py") and "guard" in name:
            files.update(re.findall(r'^\s*"([A-Za-z0-9_./+-]+)":\s*"[0-9a-f]{64}"', pf.read_text(), re.M))
    shutil.rmtree(WORK, ignore_errors=True)
    errs, files = [], sorted(files)
    with cf.ThreadPoolExecutor(8) as ex:
        for f, b in zip(files, ex.map(fetch, files)):
            if b == b"ERR": errs.append(f)
            elif b is not None:
                p = WORK / f; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
    print("tag", TAG, "files", len(files), "fetch_errors", errs)
    WORK0 = WORK.parent / (WORK.name + "_base")
    shutil.rmtree(WORK0, ignore_errors=True)
    with cf.ThreadPoolExecutor(8) as ex:
        for f, b in zip(files, ex.map(lambda f: fetch(f, BASE_TAG), files)):
            if b == b"ERR": errs.append("BASE:" + f)
            elif b is not None:
                p = WORK0 / f; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
    print("base tag", BASE_TAG, "fetch_errors", errs)
    report = []
    for d, name in order:
        pf = ROOT / d / name
        if name.startswith("0000"):
            continue
        if name.endswith(".py"):
            if "guard" in name:
                text = pf.read_text()
                def repl(m):
                    fp = WORK / m.group(1)
                    return m.group(0) if not fp.exists() else m.group(0).replace(m.group(2), sha(fp))
                new = re.sub(r'^\s*"([A-Za-z0-9_./+-]+)":\s*"([0-9a-f]{64})"', repl, text, flags=re.M)
                pf.write_text(new); report.append((name, "guard hashes refreshed", new != text))
            else:
                report.append((name, "transform script NOT run here", None))
            continue
        text = pf.read_text()
        drop = set(DROP.get(name, []))
        secs = [(h, s) for h, s in split_sections(text) if h not in drop]
        affected = [h for h, _ in secs]
        # zero-context sections: derive a context diff on the BASE tag, then use that on the target tag
        u0 = u0_sections(text) - drop
        if u0:
            sec0 = "".join(sx for h, sx in secs if h in u0)
            t0 = WORK.parent / "_u0.patch"; t0.write_text(sec0)
            pre0 = {h: ((WORK0 / h).read_text() if (WORK0 / h).exists() else None) for h in u0}
            r0 = subprocess.run(["patch", "-p1", "--fuzz=0", "--batch", "--forward", "--no-backup-if-mismatch", "-i", str(t0)],
                                cwd=WORK0, capture_output=True, text=True)
            if r0.returncode or list(WORK0.rglob("*.rej")):
                print("BASE-TAG apply failed", name, r0.stdout[-500:]); sys.exit(1)
            conv = {h: make_diff(h, pre0[h], (WORK0 / h).read_text()) for h in u0}
            secs = [(h, conv.get(h, sx)) for h, sx in secs]
            print(f"   {name}: {len(u0)} zero-context file(s) re-derived semantically")
        always = set(ALWAYS_FIX.get(name, []))
        # keep non-U0 sections of this patch applied to the BASE tree too (later patches build on them)
        nonu0 = "".join(sx for h, sx in split_sections(text) if h not in drop and h not in u0)
        if nonu0:
            t1 = WORK.parent / "_n0.patch"; t1.write_text(nonu0)
            subprocess.run(["patch", "-p1", "--fuzz=0", "--batch", "--forward", "--no-backup-if-mismatch", "-i", str(t1)],
                           cwd=WORK0, capture_output=True, text=True)
        pre = {h: ((WORK / h).read_text() if (WORK / h).exists() else None) for h in affected}
        tmp = WORK.parent / "_one.patch"; tmp.write_text("".join(s for h, s in secs if h not in always))
        r = subprocess.run(["patch", "-p1", "--fuzz=0", "--batch", "--forward", "--no-backup-if-mismatch", "-i", str(tmp)],
                           cwd=WORK, capture_output=True, text=True)
        rej = list(WORK.rglob("*.rej"))
        had_rej = bool(rej)
        if rej:
            print("   rejects in", name, [str(x.relative_to(WORK)) for x in rej])
            RD = WORK.parent / "rejs"; RD.mkdir(exist_ok=True)
            for x in rej: shutil.copy(x, RD / (name[:4] + "_" + x.name))
            # retry ONLY the rejected hunks with fuzz=2 (context trimmed to the nearest line); reviewed by hand in the log
            for x in list(rej):
                tgt = str(x.relative_to(WORK))[:-4]
                if tgt in NO_FUZZ:
                    continue
                rr = subprocess.run(["patch", "-p0", "--fuzz=2", "--batch", "--forward", "--no-backup-if-mismatch", tgt, "-i", str(x)],
                                    cwd=WORK, capture_output=True, text=True)
                print(f"      FUZZ2 retry {tgt}: rc={rr.returncode} " + " | ".join(l for l in rr.stdout.splitlines() if "Hunk" in l or "FAILED" in l))
                if rr.returncode == 0:
                    x.unlink()
            rej = list(WORK.rglob("*.rej"))
        if always:
            for x in rej: x.unlink()
            FIXES[name](WORK)
        elif rej:
            if name in FIXES:
                for x in rej: x.unlink()
                FIXES[name](WORK)
            else:
                print("UNFIXED REJECTS in", name, [str(x.relative_to(WORK)) for x in rej]); UNFIXED.append(name)
                for x in rej: x.unlink()
        elif r.returncode and not had_rej:
            print("patch failed", name, r.stdout[-400:], r.stderr[-300:]); sys.exit(1)
        new_text = ""
        for h in affected:
            post = (WORK / h).read_text() if (WORK / h).exists() else None
            if post is None: print("missing after apply", name, h); sys.exit(1)
            new_text += make_diff(h, pre[h], post)
        pf.write_text(new_text); report.append((name, "regenerated", True))
        print(f"{name:60} ok files={len(affected)} fuzz_or_offset={'yes' if re.search('fuzz|offset', r.stdout) else 'no'}")
    json.dump(report, open(WORK / "REGEN_REPORT.json", "w"), indent=1)
    if UNFIXED:
        print("UNFIXED:", UNFIXED); sys.exit(1)

main()
