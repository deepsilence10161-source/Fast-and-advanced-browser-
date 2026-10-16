#!/usr/bin/env python3
"""GitHub Actions repository secret सेट करना — मान केवल फ़ाइल से, कभी argv/stdout में नहीं।

Usage: put-secret.py <SECRET_NAME> <value-file> [--base64]
  --base64 : फ़ाइल की bytes को base64 करके रखें (binary जैसे keystore के लिए)
Token: /home/user/.secrets/gh_token (curl config stdin से, gh.sh जैसा)। मान libsodium sealed box
(repo public key) से encrypt होकर ही भेजा जाता है। Output में केवल HTTP status।
Requires: pip install pynacl
"""
import base64, json, os, subprocess, sys
from nacl import encoding, public

REPO = "deepsilence10161-source/Fast-and-advanced-browser-"
TOKEN = "/home/user/.secrets/gh_token"


def api(method, path, body=None):
    """curl: token केवल config (stdin) में; body (encrypted) अस्थायी 600-फ़ाइल से।"""
    import tempfile
    tok = open(TOKEN).read().strip()
    cfg = f'header = "Authorization: Bearer {tok}"\nheader = "Accept: application/vnd.github+json"\n'
    cmd = ["curl", "-K", "-", "-sS", "-X", method, "-w", "\n%{http_code}"]
    tmp = None
    if body is not None:
        fd, tmp = tempfile.mkstemp(dir="/home/user/.secrets"); os.write(fd, json.dumps(body).encode()); os.close(fd)
        cmd += ["-H", "Content-Type: application/json", "--data-binary", "@" + tmp]
    cmd.append(f"https://api.github.com/repos/{REPO}{path}")
    try:
        r = subprocess.run(cmd, input=cfg, capture_output=True, text=True)
    finally:
        if tmp: os.remove(tmp)
    out, code = r.stdout.rsplit("\n", 1)
    return int(code), out


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    name, vf = sys.argv[1], sys.argv[2]
    raw = open(vf, "rb").read()
    val = base64.b64encode(raw) if "--base64" in sys.argv else raw.strip()
    code, out = api("GET", "/actions/secrets/public-key")
    if code != 200:
        print("public-key HTTP", code); sys.exit(1)
    pk = json.loads(out)
    box = public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder()))
    enc = base64.b64encode(box.encrypt(val)).decode()
    code, _ = api("PUT", f"/actions/secrets/{name}", {"encrypted_value": enc, "key_id": pk["key_id"]})
    print(f"{name}: HTTP {code}")
    sys.exit(0 if code in (201, 204) else 1)


if __name__ == "__main__":
    main()
