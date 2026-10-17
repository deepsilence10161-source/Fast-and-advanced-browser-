import org.chromium.components.safe_browsing.SwiftraShield;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

/** args: vectors.tsv (url\thost\tpath\tquery\texpr|expr..\thashes) [db.swz db.sig pubkey_b64 checks.tsv] */
public class ShieldParity {
    public static void main(String[] a) throws Exception {
        int fail = 0, n = 0;
        for (String line : Files.readAllLines(Paths.get(a[0]), StandardCharsets.UTF_8)) {
            String[] f = line.split("\t", -1);
            String url = f[0];
            String[] c = SwiftraShield.canonicalize(url);
            List<String> ex = SwiftraShield.expressions(url);
            StringBuilder hs = new StringBuilder();
            for (String e : ex) hs.append(hs.length() > 0 ? "," : "").append(SwiftraShield.hash64(e));
            String got = c[0] + "\t" + c[1] + "\t" + c[2] + "\t" + String.join("|", ex) + "\t" + hs;
            String exp = f[1] + "\t" + f[2] + "\t" + f[3] + "\t" + f[4] + "\t" + f[5];
            n++;
            if (!got.equals(exp)) { fail++; System.out.println("MISMATCH " + url + "\n  got " + got + "\n  exp " + exp); }
        }
        System.out.println("vectors " + n + " fail " + fail);
        if (a.length >= 5) {
            byte[] swz = Files.readAllBytes(Paths.get(a[1]));
            byte[] sig = Files.readAllBytes(Paths.get(a[2]));
            boolean ok = SwiftraShield.verifySignature(swz, sig, a[3]);
            byte[] bad = swz.clone(); bad[bad.length / 2] ^= 1;
            boolean badOk = SwiftraShield.verifySignature(bad, sig, a[3]);
            System.out.println("sig " + ok + " tampered " + badOk);
            if (!ok || badOk) fail++;
            long t0 = System.nanoTime();
            SwiftraShield.Db db = SwiftraShield.parseDb(ByteBuffer.wrap(SwiftraShield.decodeTransport(swz, 8_000_000)));
            System.out.println("db entries " + db.totalEntries() + " created " + db.created + " decode+validate ms " + (System.nanoTime() - t0) / 1_000_000);
            int[] req = {2, 3, 4};
            long t1 = System.nanoTime(); int checks = 0;
            for (String line : Files.readAllLines(Paths.get(a[4]), StandardCharsets.UTF_8)) {
                String[] f = line.split("\t", -1);
                int got = db.check(f[0], req); checks++;
                if (got != Integer.parseInt(f[1])) { fail++; System.out.println("CHECK " + f[0] + " got " + got + " exp " + f[1]); }
            }
            System.out.println("checks " + checks + " avg us " + (System.nanoTime() - t1) / 1000 / Math.max(1, checks));
        }
        System.out.println(fail == 0 ? "ALL PASS" : "FAILURES " + fail);
        System.exit(fail == 0 ? 0 : 1);
    }
}
