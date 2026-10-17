// Copyright 2026 The Swiftra Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package org.chromium.components.safe_browsing;

import android.content.Context;
import android.net.ConnectivityManager;
import android.os.SystemClock;

import org.chromium.base.ContextUtils;
import org.chromium.base.Log;
import org.chromium.base.task.PostTask;
import org.chromium.base.task.TaskTraits;
import org.chromium.build.annotations.NullMarked;
import org.chromium.build.annotations.Nullable;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Swiftra Shield: on-device implementation of {@link SafeBrowsingApiHandler} for builds without
 * Google Play services Safe Browsing (non-branded). Every check is answered locally from a signed
 * list; no URL, hash or prefix of a visited page is sent anywhere. Only the list itself is
 * downloaded (signed with ECDSA P-256, verified before use, rollback-protected).
 */
@NullMarked
public final class SwiftraShieldApiHandler implements SafeBrowsingApiHandler {
    private static final String TAG = "SwiftraShield";
    static final String DB_URL =
            "https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/releases/download/shield-db/shield.swz";
    static final String SIG_URL = DB_URL + ".sig";
    /** X.509 SubjectPublicKeyInfo (base64) of the list signing key (private key never in source). */
    static final String PUBLIC_KEY =
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEbVLbrurOPDexJAjk35SxmUID+BH6Z1ECuzPWudrdCg2UJKB832p2zBMi3Z59GsMOpMmjWv5z9YAt3Qdigb6ZTA==";
    private static final long UPDATE_UNMETERED_MS = 24L * 3600 * 1000;
    private static final long UPDATE_METERED_MS = 72L * 3600 * 1000;
    private static final long RETRY_AFTER_FAILURE_MS = 3600L * 1000;
    private static final long MAX_FUTURE_SKEW_S = 2L * 24 * 3600;
    private static final int MAX_DOWNLOAD_BYTES = 48 * 1024 * 1024;
    private static final int MAX_ENTRIES = 8_000_000;
    // SafeBrowsingJavaResponseStatus (safe_browsing_api_handler_util.h)
    private static final int STATUS_SUCCESS_WITH_LOCAL_BLOCKLIST = 0;
    private static final int STATUS_FAILURE_BLOCK_LIST_UNAVAILABLE = 5;

    private static volatile SwiftraShield.@Nullable Db sDb;
    private static final AtomicBoolean sBusy = new AtomicBoolean();
    private static volatile long sNextAttemptElapsedMs;

    private @Nullable Observer mObserver;

    public SwiftraShieldApiHandler() {
        PostTask.postTask(TaskTraits.BEST_EFFORT_MAY_BLOCK, SwiftraShieldApiHandler::loadAndMaybeUpdate);
    }

    /** Entries in the loaded list, or -1 if no list is loaded yet (used for honest UI state). */
    public static int loadedEntries() {
        SwiftraShield.Db db = sDb;
        return db == null ? -1 : db.totalEntries();
    }

    /** Creation time (unix seconds) of the loaded list, or 0. */
    public static long loadedCreatedSeconds() {
        SwiftraShield.Db db = sDb;
        return db == null ? 0 : db.created;
    }

    @Override
    public void setObserver(Observer observer) {
        mObserver = observer;
    }

    @Override
    public void startUriLookup(long callbackId, String uri, int[] threatTypes, int protocol) {
        Observer observer = mObserver;
        if (observer == null || callbackId < 0) return;   // startup ping (-1) needs no answer
        long t0 = SystemClock.elapsedRealtimeNanos();
        SwiftraShield.Db db = sDb;
        maybeScheduleUpdate();
        if (db == null) {
            // Recoverable failure: native treats it as SAFE for this URL but keeps the API enabled.
            observer.onUrlCheckDone(callbackId, LookupResult.FAILURE, SwiftraShield.THREAT_NONE,
                    new int[0], STATUS_FAILURE_BLOCK_LIST_UNAVAILABLE, elapsedUs(t0));
            return;
        }
        int threat;
        try {
            threat = db.check(uri, threatTypes);
        } catch (RuntimeException e) {
            Log.w(TAG, "check failed", e);
            observer.onUrlCheckDone(callbackId, LookupResult.FAILURE, SwiftraShield.THREAT_NONE,
                    new int[0], STATUS_FAILURE_BLOCK_LIST_UNAVAILABLE, elapsedUs(t0));
            return;
        }
        observer.onUrlCheckDone(callbackId, LookupResult.SUCCESS, threat, new int[0],
                STATUS_SUCCESS_WITH_LOCAL_BLOCKLIST, elapsedUs(t0));
    }

    private static long elapsedUs(long t0) {
        return (SystemClock.elapsedRealtimeNanos() - t0) / 1000;
    }

    private static File dir() {
        File d = new File(ContextUtils.getApplicationContext().getFilesDir(), "swiftra_shield");
        if (!d.isDirectory() && !d.mkdirs()) Log.w(TAG, "cannot create %s", d);
        return d;
    }

    private static void maybeScheduleUpdate() {
        if (SystemClock.elapsedRealtime() < sNextAttemptElapsedMs || sBusy.get()) return;
        PostTask.postTask(TaskTraits.BEST_EFFORT_MAY_BLOCK, SwiftraShieldApiHandler::loadAndMaybeUpdate);
    }

    private static void loadAndMaybeUpdate() {
        if (!sBusy.compareAndSet(false, true)) return;
        try {
            File db = new File(dir(), "shield.bin");
            if (sDb == null && db.isFile()) {
                try {
                    SwiftraShield.Db loaded = map(db);
                    sDb = loaded;
                    Log.i(TAG, "list loaded: %d entries", loaded.totalEntries());
                } catch (IOException e) {
                    Log.w(TAG, "stored list invalid, discarding", e);
                    if (!db.delete()) Log.w(TAG, "cannot delete %s", db);
                }
            }
            long age = db.isFile() ? System.currentTimeMillis() - db.lastModified() : Long.MAX_VALUE;
            long interval = isMetered() ? UPDATE_METERED_MS : UPDATE_UNMETERED_MS;
            if (sDb != null && age < interval) {
                sNextAttemptElapsedMs = SystemClock.elapsedRealtime() + (interval - age);
                return;
            }
            try {
                update(db);
                sNextAttemptElapsedMs = SystemClock.elapsedRealtime() + interval;
            } catch (IOException e) {
                Log.w(TAG, "update failed: %s", e.getMessage());
                sNextAttemptElapsedMs = SystemClock.elapsedRealtime() + RETRY_AFTER_FAILURE_MS;
            }
        } finally {
            sBusy.set(false);
        }
    }

    private static boolean isMetered() {
        Context c = ContextUtils.getApplicationContext();
        ConnectivityManager cm = (ConnectivityManager) c.getSystemService(Context.CONNECTIVITY_SERVICE);
        try {
            return cm == null || cm.isActiveNetworkMetered();
        } catch (SecurityException e) {
            return true;
        }
    }

    private static SwiftraShield.Db map(File f) throws IOException {
        try (RandomAccessFile raf = new RandomAccessFile(f, "r");
                FileChannel ch = raf.getChannel()) {
            // The mapping stays valid after the channel is closed; data is paged in on demand.
            return SwiftraShield.parseDb(ch.map(FileChannel.MapMode.READ_ONLY, 0, ch.size()));
        }
    }

    private static void update(File dest) throws IOException {
        byte[] sig = download(SIG_URL, 4096);
        byte[] swz = download(DB_URL, MAX_DOWNLOAD_BYTES);
        if (!SwiftraShield.verifySignature(swz, sig, PUBLIC_KEY)) throw new IOException("bad signature");
        byte[] bin = SwiftraShield.decodeTransport(swz, MAX_ENTRIES);
        SwiftraShield.Db fresh = SwiftraShield.parseDb(ByteBuffer.wrap(bin));
        SwiftraShield.Db cur = sDb;
        long nowS = System.currentTimeMillis() / 1000;
        if (fresh.created > nowS + MAX_FUTURE_SKEW_S) throw new IOException("list from the future");
        if (cur != null && fresh.created <= cur.created) {
            // Same or older (rollback) list: keep current, just refresh the timestamp.
            if (!dest.setLastModified(System.currentTimeMillis())) Log.w(TAG, "cannot touch list");
            return;
        }
        File tmp = new File(dir(), "shield.bin.tmp");
        try (FileOutputStream out = new FileOutputStream(tmp)) {
            out.write(bin);
            out.getFD().sync();
        }
        if (!tmp.renameTo(dest)) throw new IOException("rename failed");
        sDb = map(dest);
        Log.i(TAG, "list updated: %d entries, created %d", fresh.totalEntries(), fresh.created);
    }

    private static byte[] download(String url, int cap) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setConnectTimeout(15000);
            c.setReadTimeout(60000);
            c.setInstanceFollowRedirects(true);
            c.setUseCaches(false);
            c.setRequestProperty("User-Agent", "SwiftraShield/1");
            int code = c.getResponseCode();
            if (code != 200) throw new IOException("HTTP " + code + " for " + url);
            if (!"https".equals(c.getURL().getProtocol())) throw new IOException("non-https redirect");
            try (InputStream in = c.getInputStream()) {
                ByteArrayOutputStream bo = new ByteArrayOutputStream();
                byte[] buf = new byte[65536];
                int r;
                while ((r = in.read(buf)) >= 0) {
                    bo.write(buf, 0, r);
                    if (bo.size() > cap) throw new IOException("download too large");
                }
                return bo.toByteArray();
            }
        } finally {
            c.disconnect();
        }
    }
}
