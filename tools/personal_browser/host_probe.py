#!/usr/bin/env python3
"""Compile/execute the ACTUAL patched account facade/provider against host stubs.

The real pinned AccountManagerFacade interface is compiled too. Android and
Chromium dependencies, Promise and the UI queue are explicitly STUBBED; no
Android build, Binder, Play services, ART, native Sync or website runs here.
Can detect interface/callback/thread-contract regressions, never certify data
containment. Source inputs are copied into a temporary host-only compilation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

JAVA_PREFIX = "components/signin/public/android/java/src/org/chromium/components/signin/"
COMPILED = (
    "AccountManagerFacade.java", "AccountManagerFacadeProvider.java",
    "BrowserContainedAccountManagerFacade.java",
)

STUBS = {
    "android/accounts/AccountManager.java": '''package android.accounts;
public class AccountManager {
    public static AccountManager get(Object context) { throw new AssertionError("platform account access"); }
}''',
    "android/app/Activity.java": '''package android.app;
public class Activity { public Activity() { throw new AssertionError("activity construction"); } }''',
    "android/content/Intent.java": '''package android.content;
public class Intent { public Intent() { throw new AssertionError("intent construction"); } }''',
    "android/os/Bundle.java": '''package android.os;
public class Bundle { public Bundle() { throw new AssertionError("bundle construction"); } }''',
    "org/chromium/base/Callback.java": '''package org.chromium.base;
public interface Callback<T> { void onResult(T value); }''',
    "org/chromium/base/ThreadUtils.java": '''package org.chromium.base;
public class ThreadUtils {
    private static final Thread UI = Thread.currentThread();
    public static void assertOnUiThread() { if (Thread.currentThread() != UI) throw new AssertionError("wrong thread"); }
}''',
    "org/chromium/base/Promise.java": '''package org.chromium.base;
public class Promise<T> {
    private final T value;
    private Promise(T value) { this.value = value; }
    public static <T> Promise<T> fulfilled(T value) { return new Promise<T>(value); }
    public T getResult() { return value; }
    public boolean isFulfilled() { return true; }
}''',
    "org/chromium/base/ResettersForTesting.java": '''package org.chromium.base;
public class ResettersForTesting {
    private static final java.util.List<Runnable> RESETTERS = new java.util.ArrayList<>();
    public static void register(Runnable runnable) { RESETTERS.add(runnable); }
    public static void reset() { for (Runnable r : RESETTERS) r.run(); RESETTERS.clear(); }
}''',
    "org/chromium/base/ServiceLoaderUtil.java": '''package org.chromium.base;
public class ServiceLoaderUtil {
    public static <T> T maybeCreate(Class<T> type) { throw new AssertionError("service loader must not initialize"); }
}''',
    "org/chromium/base/task/TaskTraits.java": '''package org.chromium.base.task;
public class TaskTraits { public static final int UI_DEFAULT = 7; }''',
    "org/chromium/base/task/PostTask.java": '''package org.chromium.base.task;
public class PostTask {
    private static final java.util.Queue<Runnable> TASKS = new java.util.concurrent.ConcurrentLinkedQueue<>();
    public static void postTask(int traits, Runnable runnable) {
        if (traits != TaskTraits.UI_DEFAULT) throw new AssertionError("not UI task");
        TASKS.add(runnable);
    }
    public static void drain() {
        org.chromium.base.ThreadUtils.assertOnUiThread();
        Runnable r; while ((r = TASKS.poll()) != null) r.run();
    }
}''',
    "org/chromium/components/signin/AccessTokenData.java": '''package org.chromium.components.signin;
public class AccessTokenData {}''',
    "org/chromium/components/signin/AccountsChangeObserver.java": '''package org.chromium.components.signin;
public interface AccountsChangeObserver {}''',
    "org/chromium/components/signin/base/AccountCapabilities.java": '''package org.chromium.components.signin.base;
public class AccountCapabilities {
    public final java.util.Map<String, Boolean> values;
    public AccountCapabilities(String[] names, boolean[] values) {
        if (names.length != 0 || values.length != 0) throw new AssertionError("fabricated capabilities");
        this.values = java.util.Collections.emptyMap();
    }
    public AccountCapabilities(java.util.Map<String, Boolean> values) {
        throw new AssertionError("do not use the actual API's VisibleForTesting constructor");
    }
}''',
    "org/chromium/components/signin/base/AccountInfo.java": '''package org.chromium.components.signin.base;
public class AccountInfo {}''',
    "org/chromium/components/signin/base/CoreAccountInfo.java": '''package org.chromium.components.signin.base;
public class CoreAccountInfo {}''',
    "org/chromium/google_apis/gaia/CoreAccountId.java": '''package org.chromium.google_apis.gaia;
public class CoreAccountId {}''',
    "org/chromium/google_apis/gaia/GoogleServiceAuthError.java": '''package org.chromium.google_apis.gaia;
public class GoogleServiceAuthError {
    public final int state;
    public GoogleServiceAuthError(int state) { this.state = state; }
}''',
    "org/chromium/google_apis/gaia/GoogleServiceAuthErrorState.java": '''package org.chromium.google_apis.gaia;
public class GoogleServiceAuthErrorState { public static final int REQUEST_CANCELED = 13; }''',
}

for package, names in (
    ("androidx.annotation", ("AnyThread", "MainThread", "VisibleForTesting")),
    ("org.chromium.build.annotations", ("Nullable", "NullMarked")),
    ("org.jni_zero", ("CalledByNative",)),
):
    for name in names:
        STUBS[package.replace(".", "/") + "/" + name + ".java"] = (
            "package " + package + ";\n"
            "@java.lang.annotation.Target({java.lang.annotation.ElementType.TYPE_USE, "
            "java.lang.annotation.ElementType.TYPE, java.lang.annotation.ElementType.METHOD, "
            "java.lang.annotation.ElementType.PARAMETER, java.lang.annotation.ElementType.FIELD, "
            "java.lang.annotation.ElementType.CONSTRUCTOR})\n"
            "public @interface " + name + " {}")

PROBE = '''package org.chromium.components.signin;
import org.chromium.base.ThreadUtils;
import org.chromium.base.ResettersForTesting;
import org.chromium.base.task.PostTask;
import org.chromium.google_apis.gaia.GoogleServiceAuthError;
import org.chromium.google_apis.gaia.GoogleServiceAuthErrorState;

public class PersonalAccountHostProbe {
    private static int checks;
    private static void check(boolean good) { checks++; if (!good) throw new AssertionError("contract " + checks); }
    private static void denied(AccountManagerFacade facade) {
        int[] success = {0}, failure = {0};
        facade.getAccessToken(null, "synthetic-scope", new AccountManagerFacade.GetAccessTokenCallback() {
            public void onGetTokenSuccess(AccessTokenData token) { success[0]++; }
            public void onGetTokenFailure(GoogleServiceAuthError error) {
                check(error.state == GoogleServiceAuthErrorState.REQUEST_CANCELED);
                failure[0]++;
            }
        });
        check(success[0] == 0 && failure[0] == 1);
    }
    public static void main(String[] args) throws Exception {
        ThreadUtils.assertOnUiThread();
        AccountManagerFacade facade = AccountManagerFacadeProvider.getInstance();
        check(facade instanceof BrowserContainedAccountManagerFacade);
        check(AccountManagerFacadeProvider.getInstance() == facade);
        check(facade.getAccounts().isFulfilled());
        check(facade.getAccounts().getResult().isEmpty());
        boolean immutable = false;
        try { facade.getAccounts().getResult().add(null); } catch (UnsupportedOperationException e) { immutable = true; }
        check(immutable);
        AccountsChangeObserver observer = new AccountsChangeObserver() {};
        facade.addObserver(observer); facade.removeObserver(observer);
        check(facade.getAccounts().getResult().isEmpty());
        denied(facade);
        facade.disallowTokenRequestsForTesting(); denied(facade);
        int[] completed = {0};
        facade.invalidateAccessToken("synthetic-not-a-credential", () -> completed[0]++);
        facade.invalidateAccessToken("synthetic-not-a-credential", null);
        facade.waitForPendingTokenRequestsToComplete(() -> completed[0]++);
        check(completed[0] == 2);
        int[] child = {0};
        facade.checkIsSubjectToParentalControls(null, (isChild, account) -> {
            check(!isChild && account == null); child[0]++;
        });
        check(child[0] == 1);
        check(facade.getAccountCapabilities(null).isFulfilled());
        check(facade.getAccountCapabilities(null).getResult().values.isEmpty());
        int[] update = {0}, confirm = {0}, add = {0};
        facade.updateCredentials(null, null, result -> { check(!result); update[0]++; });
        facade.updateCredentials(null, null, null);
        facade.confirmCredentials(null, null, result -> { check(result == null); confirm[0]++; });
        check(update[0] == 1 && confirm[0] == 1);
        facade.createAddAccountIntent(null, result -> {
            ThreadUtils.assertOnUiThread(); check(result == null); add[0]++;
        });
        check(add[0] == 0); PostTask.drain(); check(add[0] == 1);
        Thread worker = new Thread(() -> facade.createAddAccountIntent("synthetic@example.com", result -> {
            ThreadUtils.assertOnUiThread(); check(result == null); add[0]++;
        }));
        worker.start(); worker.join();
        check(add[0] == 1); PostTask.drain(); check(add[0] == 2);
        int[] threadRejections = {0};
        Thread wrongThread = new Thread(() -> {
            try { facade.getAccounts(); } catch (AssertionError e) { threadRejections[0]++; }
        });
        wrongThread.start(); wrongThread.join(); check(threadRejections[0] == 1);
        check(facade.didAccountFetchSucceed());
        AccountManagerFacade test = new BrowserContainedAccountManagerFacade();
        AccountManagerFacadeProvider.setInstanceForTests(test);
        check(AccountManagerFacadeProvider.getInstance() == test);
        ResettersForTesting.reset(); check(AccountManagerFacadeProvider.getInstance() == facade);
        check(facade.getAccounts().getResult().isEmpty());
        System.out.println("PERSONAL_ACCOUNT_HOST_PROBE assertions=" + checks);
    }
}
'''


def run_probe(src: Path, facade_override: str | None = None) -> dict:
    if not shutil.which("javac") or not shutil.which("java"):
        raise RuntimeError("host_JDK_missing")
    actual = {name: (src / JAVA_PREFIX / name).read_text() for name in COMPILED}
    if facade_override is not None:
        actual["BrowserContainedAccountManagerFacade.java"] = facade_override
    report = {
        "test_type": "HOST JAVA WITH STUBBED ANDROID/CHROMIUM DEPENDENCIES; NOT ANDROID",
        "product_containment": "NOT RUN / NOT CERTIFIED",
        "source_sha256": {name: hashlib.sha256(text.encode()).hexdigest() for name, text in actual.items()},
        "dependency_stubs": True,
        "mutation_control": facade_override is not None,
    }
    with tempfile.TemporaryDirectory(prefix="personal-account-host-") as tmp:
        folder = Path(tmp)
        inputs = dict(STUBS)
        inputs.update({"org/chromium/components/signin/" + name: text for name, text in actual.items()})
        inputs["org/chromium/components/signin/PersonalAccountHostProbe.java"] = PROBE
        paths = []
        for relative, text in inputs.items():
            path = folder / "src" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            paths.append(str(path))
        compiled = subprocess.run(
            ["javac", "-Xlint:all", "-Werror", "-d", str(folder / "classes"), *sorted(paths)],
            text=True, capture_output=True, timeout=45)
        report["javac_exit"] = compiled.returncode
        if compiled.returncode:
            report.update(status="FAIL (host compile)", diagnostic=compiled.stderr[-3000:])
            return report
        executed = subprocess.run(
            ["java", "-ea", "-cp", str(folder / "classes"),
             "org.chromium.components.signin.PersonalAccountHostProbe"],
            text=True, capture_output=True, timeout=30)
        report.update(java_exit=executed.returncode, output=executed.stdout.strip(),
                      diagnostic=executed.stderr[-3000:],
                      status="PASS (host component with stubs)" if executed.returncode == 0 else "FAIL (host component)")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patched-source", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_probe(args.patched_source)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        report = {"status": "NOT RUN / HOST PROBE ERROR", "product_containment": "NOT RUN / NOT CERTIFIED"}
    print(json.dumps(report, indent=2))
    return 0 if report["status"].startswith("PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
