// Copyright 2026 The Swiftra Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package org.chromium.components.safe_browsing;

import org.chromium.build.annotations.NullMarked;
import org.chromium.build.annotations.Nullable;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.IDN;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.zip.GZIPInputStream;

/**
 * Swiftra Shield core: on-device Safe Browsing style lookup (no URL ever leaves the device).
 *
 * <p>Canonicalization and host/path expressions mirror SBProtocolManagerUtil (CanonicalizeUrl,
 * GenerateHostVariantsToCheckV4, GeneratePathVariantsToCheck). The Python twin
 * (scripts/shield/sbcanon.py) builds the list; both are tested against the same vectors.
 *
 * <p>Strings below are Latin-1 views of bytes (one char per byte) so byte-level semantics match.
 */
@NullMarked
public final class SwiftraShield {
    public static final int THREAT_NONE = 0;
    public static final int THREAT_SOCIAL_ENGINEERING = 2;
    public static final int THREAT_UNWANTED_SOFTWARE = 3;
    public static final int THREAT_POTENTIALLY_HARMFUL_APPLICATION = 4;

    static final byte[] MAGIC = "SWSHLD01".getBytes(StandardCharsets.US_ASCII);
    static final byte[] TMAGIC = "SWSHZ001".getBytes(StandardCharsets.US_ASCII);
    static final int MAX_LISTS = 16;

    private SwiftraShield() {}

    // ---------------------------------------------------------------- canonicalization

    private static String latin1(byte[] b) {
        return new String(b, StandardCharsets.ISO_8859_1);
    }

    private static int hex(char c) {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
    }

    private static String unescapeOnce(String s) {
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '%' && i + 2 < s.length()) {
                int h = hex(s.charAt(i + 1));
                int l = hex(s.charAt(i + 2));
                if (h >= 0 && l >= 0) {
                    sb.append((char) (h * 16 + l));
                    i += 2;
                    continue;
                }
            }
            sb.append(c);
        }
        return sb.toString();
    }

    static String unescape(String s) {
        for (int i = 0; i <= 1024; i++) {
            String out = unescapeOnce(s);
            if (out.length() == s.length()) return out;
            s = out;
        }
        return s;
    }

    static String escape(String s) {
        StringBuilder sb = new StringBuilder(s.length() * 2);
        for (int i = 0; i < s.length(); i++) {
            int c = s.charAt(i) & 0xFF;
            if (c <= 0x20 || c > 0x7E || c == '#' || c == '%') {
                sb.append('%');
                sb.append(Character.toUpperCase(Character.forDigit(c >> 4, 16)));
                sb.append(Character.toUpperCase(Character.forDigit(c & 15, 16)));
            } else {
                sb.append((char) c);
            }
        }
        return sb.toString();
    }

    private static String asciiLower(String s) {
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            sb.append(c >= 'A' && c <= 'Z' ? (char) (c + 32) : c);
        }
        return sb.toString();
    }

    private static long ipv4Part(String p) {
        if (p.isEmpty() || p.length() > 12) return -1;
        try {
            if (p.length() >= 2 && (p.startsWith("0x") || p.startsWith("0X"))) {
                String h = p.substring(2);
                return h.isEmpty() ? 0 : Long.parseLong(h, 16);
            }
            if (p.length() > 1 && p.charAt(0) == '0') return Long.parseLong(p.substring(1), 8);
            return Long.parseLong(p, 10);
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    private static boolean looksNumeric(String p) {
        if (p.length() >= 2 && (p.startsWith("0x") || p.startsWith("0X"))) {
            for (int i = 2; i < p.length(); i++) if (hex(p.charAt(i)) < 0) return false;
            return true;
        }
        if (p.isEmpty()) return false;
        for (int i = 0; i < p.length(); i++) {
            char c = p.charAt(i);
            if (c < '0' || c > '9') return false;
        }
        return true;
    }

    /** Splits on |c| keeping empty fields (like String.split(regex, -1) without regex). */
    static List<String> splitAll(String s, char c) {
        List<String> out = new ArrayList<>();
        int start = 0;
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) == c) {
                out.add(s.substring(start, i));
                start = i + 1;
            }
        }
        out.add(s.substring(start));
        return out;
    }

    /** WHATWG IPv4 parser (GURL compatible); returns dotted quad or null. */
    static @Nullable String ipv4Normalize(String host) {
        List<String> parts = splitAll(host, '.');
        if (parts.size() > 1 && parts.get(parts.size() - 1).isEmpty()) {
            parts.remove(parts.size() - 1);
        }
        if (parts.isEmpty() || parts.size() > 4) return null;
        if (!looksNumeric(parts.get(parts.size() - 1))) return null;
        long[] nums = new long[parts.size()];
        for (int i = 0; i < nums.length; i++) {
            nums[i] = ipv4Part(parts.get(i));
            if (nums[i] < 0) return null;
        }
        for (int i = 0; i < nums.length - 1; i++) if (nums[i] > 255) return null;
        long limit = 1L << (8 * (5 - nums.length));
        if (nums[nums.length - 1] >= limit) return null;
        long v = nums[nums.length - 1];
        for (int i = 0; i < nums.length - 1; i++) v += nums[i] << (8 * (3 - i));
        return ((v >> 24) & 255) + "." + ((v >> 16) & 255) + "." + ((v >> 8) & 255) + "." + (v & 255);
    }

    static String resolveDots(String path) {
        if (!path.startsWith("/")) path = "/" + path;
        List<String> segs = splitAll(path.substring(1), '/');
        List<String> out = new ArrayList<>();
        for (int i = 0; i < segs.size(); i++) {
            boolean last = i == segs.size() - 1;
            String s = segs.get(i);
            if (s.equals(".")) {
                if (last) out.add("");
                continue;
            }
            if (s.equals("..")) {
                if (!out.isEmpty()) out.remove(out.size() - 1);
                if (last) out.add("");
                continue;
            }
            out.add(s);
        }
        return "/" + String.join("/", out);
    }

    private static String collapse(String s, char c) {
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char x = s.charAt(i);
            if (x == c && sb.length() > 0 && sb.charAt(sb.length() - 1) == c) continue;
            sb.append(x);
        }
        return sb.toString();
    }

    private static String trimChar(String s, char c) {
        int b = 0;
        int e = s.length();
        while (b < e && s.charAt(b) == c) b++;
        while (e > b && s.charAt(e - 1) == c) e--;
        return s.substring(b, e);
    }

    /** Components of a standard URL (port/query/ref are null when absent). */
    static final class Parts {
        final String scheme;
        final String host;
        final @Nullable String port;
        final String path;
        final @Nullable String query;
        final @Nullable String ref;

        Parts(String scheme, String host, @Nullable String port, String path, @Nullable String query,
                @Nullable String ref) {
            this.scheme = scheme;
            this.host = host;
            this.port = port;
            this.path = path;
            this.query = query;
            this.ref = ref;
        }
    }

    /** url::ParseStandardUrl-like split; null if not a URL. */
    static @Nullable Parts split(String spec) {
        int colon = spec.indexOf(':');
        if (colon <= 0) return null;
        char c0 = spec.charAt(0);
        if (!((c0 >= 'a' && c0 <= 'z') || (c0 >= 'A' && c0 <= 'Z'))) return null;
        for (int i = 1; i < colon; i++) {
            char c = spec.charAt(i);
            boolean ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')
                    || c == '+' || c == '.' || c == '-';
            if (!ok) return null;
        }
        String scheme = asciiLower(spec.substring(0, colon));
        String rest = spec.substring(colon + 1);
        int k = 0;
        while (k < rest.length() && (rest.charAt(k) == '/' || rest.charAt(k) == '\\')) k++;
        rest = rest.substring(k);
        int i = 0;
        while (i < rest.length() && "/?#\\".indexOf(rest.charAt(i)) < 0) i++;
        String auth = rest.substring(0, i);
        rest = rest.substring(i);
        int at = auth.lastIndexOf('@');
        if (at >= 0) auth = auth.substring(at + 1);
        @Nullable String port = null;
        int pc = auth.lastIndexOf(':');
        if (pc >= 0 && !auth.startsWith("[")) {
            boolean digits = true;
            for (int j = pc + 1; j < auth.length(); j++) {
                char c = auth.charAt(j);
                if (c < '0' || c > '9') digits = false;
            }
            if (digits) {
                port = auth.substring(pc + 1);
                auth = auth.substring(0, pc);
            }
        }
        @Nullable String ref = null;
        int hash = rest.indexOf('#');
        if (hash >= 0) {
            ref = rest.substring(hash + 1);
            rest = rest.substring(0, hash);
        }
        @Nullable String query = null;
        int q = rest.indexOf('?');
        if (q >= 0) {
            query = rest.substring(q + 1);
            rest = rest.substring(0, q);
        }
        return new Parts(scheme, auth, port, rest, query, ref);
    }

    private static boolean isStandard(String scheme) {
        return scheme.equals("http") || scheme.equals("https") || scheme.equals("ftp")
                || scheme.equals("ws") || scheme.equals("wss");
    }

    /** Approximates GURL canonical spec for raw input (idempotent for real GURL specs). */
    static @Nullable String gurlLite(String url) {
        int b = 0;
        int e = url.length();
        while (b < e && url.charAt(b) <= 0x20) b++;
        while (e > b && url.charAt(e - 1) <= 0x20) e--;
        String u = url.substring(b, e).replace("\t", "").replace("\r", "").replace("\n", "");
        String spec = latin1(u.getBytes(StandardCharsets.UTF_8));
        Parts p = split(spec);
        if (p == null || !isStandard(p.scheme)) return null;
        String host = asciiLower(unescape(p.host));
        boolean nonAscii = false;
        for (int i = 0; i < host.length(); i++) if (host.charAt(i) > 0x7F) nonAscii = true;
        if (nonAscii) {
            try {
                String uni = new String(host.getBytes(StandardCharsets.ISO_8859_1), StandardCharsets.UTF_8);
                host = asciiLower(IDN.toASCII(uni, IDN.ALLOW_UNASSIGNED));
            } catch (IllegalArgumentException ex) {
                // keep raw bytes; escaped below
            }
        }
        String ip = ipv4Normalize(host);
        if (ip != null) host = ip;
        String path = p.path.replace('\\', '/');
        path = resolveDots(path.isEmpty() ? "/" : path);
        StringBuilder out = new StringBuilder();
        out.append(p.scheme).append("://").append(escape(host)).append(path);
        String query = p.query;
        if (query != null) out.append('?').append(query);
        return out.toString();
    }

    /** Returns {host, path, query} per SBProtocolManagerUtil::CanonicalizeUrl ("" when absent). */
    public static String[] canonicalize(String url) {
        String[] empty = {"", "", ""};
        String spec = gurlLite(url);
        if (spec == null) return empty;
        String s = unescape(spec);
        Parts p = split(s);
        if (p == null) return empty;
        String host = collapse(trimChar(p.host, '.'), '.');
        String path = collapse(p.path, '/');
        host = asciiLower(host);
        if (!host.isEmpty()) {
            String ip = ipv4Normalize(host);
            if (ip != null) host = ip;
        }
        path = resolveDots(path.replace('\\', '/').isEmpty() ? "/" : path.replace('\\', '/'));
        StringBuilder out = new StringBuilder();
        out.append(p.scheme).append("://").append(host);
        String port = p.port;
        if (port != null && !port.isEmpty()) out.append(':').append(port);
        out.append(path);
        String query = p.query;
        if (query != null) out.append('?').append(query);
        String ref = p.ref;
        if (ref != null) out.append('#').append(ref);
        String fin = escape(unescape(out.toString()));
        Parts f = split(fin);
        if (f == null) return empty;
        String fq = f.query;
        return new String[] {f.host, f.path, fq == null ? "" : fq};
    }

    static List<String> hostVariants(String host, boolean isIp) {
        List<String> hosts = new ArrayList<>();
        if (host.isEmpty()) return hosts;
        if (isIp) {
            hosts.add(host);
            return hosts;
        }
        boolean skipped = false;
        for (int i = host.length() - 1; i >= 0 && hosts.size() < 4; i--) {
            if (host.charAt(i) == '.') {
                if (skipped) {
                    hosts.add(host.substring(i + 1));
                } else {
                    skipped = true;
                }
            }
        }
        hosts.add(host);
        return hosts;
    }

    static List<String> pathVariants(String path, String query) {
        List<String> paths = new ArrayList<>();
        if (path.isEmpty()) return paths;
        for (int i = 0; i < path.length() && paths.size() < 4; i++) {
            if (path.charAt(i) == '/') paths.add(path.substring(0, i + 1));
        }
        if (!paths.isEmpty() && !paths.get(paths.size() - 1).equals(path)) paths.add(path);
        if (!query.isEmpty()) paths.add(path + "?" + query);
        return paths;
    }

    public static List<String> expressions(String url) {
        String[] c = canonicalize(url);
        boolean isIp = !c[0].isEmpty() && c[0].equals(ipv4Normalize(c[0]));
        List<String> out = new ArrayList<>();
        for (String h : hostVariants(c[0], isIp)) {
            for (String p : pathVariants(c[1], c[2])) out.add(h + p);
        }
        return out;
    }

    public static long hash64(String expr) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] d = md.digest(expr.getBytes(StandardCharsets.ISO_8859_1));
            return ByteBuffer.wrap(d, 0, 8).getLong();
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    // ---------------------------------------------------------------- database

    /** Immutable view over a SWSHLD01 buffer (heap or memory-mapped). Thread-safe for reads. */
    public static final class Db {
        public final long created;
        private final ByteBuffer mBuf;
        private final int[] mTypes;
        private final int[] mCounts;
        private final int[] mOffsets;

        private Db(long created, ByteBuffer buf, int[] types, int[] counts, int[] offsets) {
            this.created = created;
            mBuf = buf;
            mTypes = types;
            mCounts = counts;
            mOffsets = offsets;
        }

        public int totalEntries() {
            int t = 0;
            for (int c : mCounts) t += c;
            return t;
        }

        public int count(int threat) {
            for (int i = 0; i < mTypes.length; i++) if (mTypes[i] == threat) return mCounts[i];
            return 0;
        }

        private boolean contains(int list, long h) {
            int lo = 0;
            int hi = mCounts[list] - 1;
            int base = mOffsets[list];
            while (lo <= hi) {
                int mid = (lo + hi) >>> 1;
                long v = mBuf.getLong(base + 8 * mid);
                if (v < h) {
                    lo = mid + 1;
                } else if (v > h) {
                    hi = mid - 1;
                } else {
                    return true;
                }
            }
            return false;
        }

        /** Threat type among |requested| matching |url|, or THREAT_NONE. Malware wins over phishing. */
        public int check(String url, int[] requested) {
            List<String> ex = expressions(url);
            if (ex.isEmpty()) return THREAT_NONE;
            long[] hs = new long[ex.size()];
            for (int i = 0; i < hs.length; i++) hs[i] = hash64(ex.get(i));
            int[] priority = {THREAT_POTENTIALLY_HARMFUL_APPLICATION, THREAT_SOCIAL_ENGINEERING,
                    THREAT_UNWANTED_SOFTWARE};
            for (int threat : priority) {
                if (!isRequested(requested, threat)) continue;
                for (int i = 0; i < mTypes.length; i++) {
                    if (mTypes[i] != threat) continue;
                    for (long h : hs) if (contains(i, h)) return threat;
                }
            }
            return THREAT_NONE;
        }
    }

    static boolean isRequested(int[] requested, int threat) {
        for (int r : requested) if (r == threat) return true;
        return false;
    }

    /** Parses and fully validates a SWSHLD01 buffer (sizes, sort order). */
    public static Db parseDb(ByteBuffer buf) throws IOException {
        int len = buf.limit();
        if (len < 20) throw new IOException("short db");
        for (int i = 0; i < 8; i++) if (buf.get(i) != MAGIC[i]) throw new IOException("bad magic");
        long created = buf.getLong(8);
        int n = buf.getInt(16);
        if (n < 1 || n > MAX_LISTS) throw new IOException("bad list count");
        int[] types = new int[n];
        int[] counts = new int[n];
        int[] offsets = new int[n];
        long off = 20L + 8L * n;
        if (off > len) throw new IOException("short header");
        for (int i = 0; i < n; i++) {
            types[i] = buf.getInt(20 + 8 * i);
            counts[i] = buf.getInt(24 + 8 * i);
            if (counts[i] < 0) throw new IOException("bad count");
        }
        for (int i = 0; i < n; i++) {
            offsets[i] = (int) off;
            off += 8L * counts[i];
            if (off > len) throw new IOException("truncated");
        }
        if (off != len) throw new IOException("trailing bytes");
        for (int i = 0; i < n; i++) {
            for (int j = 1; j < counts[i]; j++) {
                if (buf.getLong(offsets[i] + 8 * (j - 1)) >= buf.getLong(offsets[i] + 8 * j)) {
                    throw new IOException("unsorted");
                }
            }
        }
        return new Db(created, buf, types, counts, offsets);
    }

    /** Decodes SWSHZ001 transport to SWSHLD01 bytes. Caller must verify the signature first. */
    public static byte[] decodeTransport(byte[] swz, int maxEntries) throws IOException {
        if (swz.length < 8) throw new IOException("short transport");
        for (int i = 0; i < 8; i++) if (swz[i] != TMAGIC[i]) throw new IOException("bad magic");
        InputStream in = new GZIPInputStream(new ByteArrayInputStream(swz, 8, swz.length - 8));
        byte[] head = readFully(in, 12);
        ByteBuffer hb = ByteBuffer.wrap(head);
        long created = hb.getLong();
        int n = hb.getInt();
        if (n < 1 || n > MAX_LISTS) throw new IOException("bad list count");
        ByteBuffer lh = ByteBuffer.wrap(readFully(in, 8 * n));
        int[] types = new int[n];
        int[] counts = new int[n];
        long total = 0;
        for (int i = 0; i < n; i++) {
            types[i] = lh.getInt();
            counts[i] = lh.getInt();
            total += counts[i];
            if (counts[i] < 0 || total > maxEntries) throw new IOException("too many entries");
        }
        ByteBuffer out = ByteBuffer.allocate((int) (20 + 8L * n + 8L * total));
        out.put(MAGIC).putLong(created).putInt(n);
        for (int i = 0; i < n; i++) out.putInt(types[i]).putInt(counts[i]);
        for (int i = 0; i < n; i++) {
            long prev = 0;
            for (int j = 0; j < counts[i]; j++) {
                long val = 0;
                int shift = 0;
                while (true) {
                    int b = in.read();
                    if (b < 0) throw new IOException("truncated varint");
                    if (shift > 63) throw new IOException("varint overflow");
                    val |= ((long) (b & 0x7F)) << shift;
                    shift += 7;
                    if ((b & 0x80) == 0) break;
                }
                long next = prev + val;   // unsigned arithmetic on (v + 2^63)
                if (j > 0 && Long.compareUnsigned(next, prev) <= 0) throw new IOException("not increasing");
                prev = next;
                out.putLong(next ^ Long.MIN_VALUE);   // back to signed order value
            }
        }
        if (in.read() >= 0) throw new IOException("trailing bytes");
        byte[] arr = out.array();
        parseDb(ByteBuffer.wrap(arr));
        return arr;
    }

    private static byte[] readFully(InputStream in, int n) throws IOException {
        ByteArrayOutputStream bo = new ByteArrayOutputStream(n);
        byte[] buf = new byte[Math.min(n, 8192)];
        while (bo.size() < n) {
            int r = in.read(buf, 0, Math.min(buf.length, n - bo.size()));
            if (r < 0) throw new IOException("truncated");
            bo.write(buf, 0, r);
        }
        return bo.toByteArray();
    }

    /** ECDSA P-256 / SHA-256 signature (DER) check with an X.509 SubjectPublicKeyInfo key (base64). */
    public static boolean verifySignature(byte[] data, byte[] derSig, String publicKeyB64) {
        try {
            PublicKey key = KeyFactory.getInstance("EC").generatePublic(
                    new X509EncodedKeySpec(Base64.getDecoder().decode(publicKeyB64)));
            Signature v = Signature.getInstance("SHA256withECDSA");
            v.initVerify(key);
            v.update(data);
            return v.verify(derSig);
        } catch (GeneralSecurityException | IllegalArgumentException e) {
            return false;
        }
    }
}
