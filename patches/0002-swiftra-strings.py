#!/usr/bin/env python3
"""b2: app के अंदर के "Chrome"/"Google Chrome"/"Chromium" (product नाम) -> "Swiftra" — अंग्रेज़ी + सभी translations।

क्यों script (diff नहीं): grit हर message का translation ID उसके अंग्रेज़ी text के fingerprint से बनाता है। केवल
अंग्रेज़ी बदलने पर सभी भाषाओं (हिंदी सहित) के translations टूट जाते (fallback अंग्रेज़ी)। यह script उसी src के
grit (tools/grit) से पुराने और नए IDs निकालकर हर .xtb में translation को नए ID पर ले जाती है और उसके text में भी
वही नाम-बदलाव करती है। (Brave भी यही तरीका अपनाता है।) Deterministic; pristine src पर चलती है (patches.py)।

नियम (केवल text nodes; <ph>…</ph> के भीतर, attributes, desc/meaning कभी नहीं):
  "Google Chrome" -> Swiftra;  शब्द "Chromium" -> Swiftra;  शब्द "Chrome" -> Swiftra
  सुरक्षित (नहीं बदलते): Chromium open-source project/Authors (license attribution), Chrome Web Store, ChromeOS/Chrome OS,
  Chromebook, Chrome Remote Desktop, Chrome Enterprise, chrome:// URLs (lowercase — छूते ही नहीं)।
Usage: python3 0002-swiftra-strings.py <src>        stdout: "TOUCHED <src-relative path>" प्रति बदली फ़ाइल
"""
import os
import re
import sys

BRAND = "Swiftra"
GRDS = [
    "chrome/app/chromium_strings.grd",
    "components/components_chromium_strings.grd",
    "chrome/browser/ui/android/strings/android_chrome_strings.grd",
    "components/browser_ui/strings/android/browser_ui_strings.grd",
    "ui/android/java/strings/android_ui_strings.grd",          # menu button: "Customize and control Google Chrome"
    # बड़ी साझा grd — केवल सूचीबद्ध grdp के messages (incognito NTP "Chromium won't save", sad tab "Restart Chromium");
    # translations में नाम-बदलाव भी केवल उन्हीं messages का जिनका English बदला
    ("components/components_strings.grd", ["components/new_or_sad_tab_strings.grdp"]),
]
PROTECT = re.compile(
    r"Chromium(?:\s+(?:open[\s-]?source|project|Authors))|The Chromium Authors|Chromium\s*OS\b|ChromiumOS|"
    r"Chrome\s+Web\s+Store|Chrome\s*OS\b|ChromeOS|Chrome(?:book|box|base|cast)\w*|Chrome\s+Remote\s+Desktop|"
    r"(?:Google\s+)?Chrome\s+Enterprise|Chrome\s+Browser\s+Cloud\s+Management|"
    # Google के असली कानूनी दस्तावेज़ों के नाम — इन्हें "Swiftra …" कहना गलत दावा होगा (legal gate: Swiftra के अपने ToS/Privacy)
    r"(?:Google\s+)?Chrome\s*(?:and|&amp;|&)\s*Chrome\s*OS\s+Additional\s+Terms\s+of\s+Service|"
    r"(?:Google\s+)?Chrome\s+(?:Additional\s+)?Terms\s+of\s+Service|(?:Google\s+)?Chrome\s+Privacy\s+(?:Notice|Whitepaper)")
# सीमा केवल Latin अक्षरों से: कई भाषाएँ नाम को शब्द से जोड़ देती हैं ("ስለChromium", "Chromiumን") जहाँ \b नहीं बनता;
# "Chromebook"/"ChromeOS" फिर भी नहीं बदलते (आगे Latin अक्षर)।
NL, NR = r"(?<![A-Z])(?<![A-Za-z][a-z])", r"(?![A-Za-z])"   # एक छोटा उपसर्ग चलता है: Zulu "iChrome"
RULES = [(re.compile(r"Google\s+Chrome" + NR), BRAND),
         (re.compile(NL + r"Chromium" + NR), BRAND),
         (re.compile(NL + r"Chrome" + NR), BRAND)]


# translations: विभक्ति वाली भाषाएँ नाम में छोटा प्रत्यय जोड़ती हैं (fi "Chromen", hr "Chromiumu", hu "Chromiumot") — मूल
# शब्द बदलकर प्रत्यय वही (fi "Swiftran" व्याकरण-सही)। Chromebook/Chromecast आदि पहले ही mask।
# बाईं सीमा भी नहीं: Zulu जैसी भाषाएँ 1-3 अक्षर के (बड़े अक्षर वाले भी) उपसर्ग जोड़ती हैं ("seChromium", "IChromium");
# translations में बड़े C वाला "Chrome" शब्द-बीच केवल यही नाम होता है।
# लिप्यंतरित नाम (hi/ne/mr "क्रोमियम"/"क्रोम", ur "کروم") — Latin "Swiftra" (बाकी hi translations जैसा)। "क्रोम" के बाद
# मात्रा हो तो दूसरा शब्द; बुक/कास्ट/ओएस/वेब स्टोर = सुरक्षित उत्पाद-नाम। (ru "Кроме"=अलावा, el "Χρώμα"=रंग — नहीं छूते)
DEVA_MATRA = "\u093e-\u094c\u0962\u0963"
TR_RULES = [(re.compile(r"Google\s+Chrome(?![A-Z])"), BRAND),
            (re.compile(r"Chromium(?![A-Z])"), BRAND),
            (re.compile(r"Chrome(?![A-Z])"), BRAND),
            (re.compile("गूगल\\s+क्रोम(?![" + DEVA_MATRA + "])(?!\\s*(?:बुक|कास्ट|ओएस|OS|वेब\\s*स्टोर))"), BRAND),
            (re.compile("क्रोमियम"), BRAND),
            (re.compile("क्रोम(?![" + DEVA_MATRA + "])(?!\\s*(?:बुक|कास्ट|ओएस|OS|वेब\\s*स्टोर))"), BRAND),
            (re.compile("(?<![\u0600-\u06ff])کروم(?![\u0600-\u06ff])"), BRAND)]


def brand_text(t, tr=False):
    """एक text टुकड़े में नियम लागू (सुरक्षित वाक्यांश mask करके)।"""
    keep = []

    def mask(m):
        keep.append(m.group(0)); return "\x00%d\x00" % (len(keep) - 1)
    t = PROTECT.sub(mask, t)
    for rx, rep in (TR_RULES if tr else RULES):
        t = rx.sub(rep, t)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], t)


def brand_markup(body, tr=False):
    """message/translation body: केवल ph के बाहर के text nodes बदलें।"""
    out, depth = [], 0
    for tok in re.split(r"(<[^>]+>)", body):
        if tok.startswith("<"):
            if re.match(r"<ph\b", tok) and not tok.endswith("/>"):
                depth += 1
            elif tok.startswith("</ph"):
                depth = max(0, depth - 1)
            out.append(tok)
        else:
            out.append(brand_text(tok, tr) if depth == 0 else tok)
    return "".join(out)


MSG_RX = re.compile(r"(<message\b[^>]*>)(.*?)(</message>)", re.S)
TR_RX = re.compile(r'(<translation\s+id=")(\d+)(">)(.*?)(</translation>)', re.S)


def message_ids(src, grd_path):
    """grit से (preorder क्रम में) हर message का translation ID।"""
    sys.path.insert(0, os.path.join(src, "tools", "grit"))
    from grit import grd_reader
    from grit.node import message as M

    class AnyDef(dict):   # IDs शर्तों पर निर्भर नहीं; सभी <if> शाखाएँ गिननी हैं
        def __contains__(self, k): return True
        def __getitem__(self, k): return dict.get(self, k, False)
        def get(self, k, d=None): return dict.get(self, k, False)
    res = grd_reader.Parse(grd_path, defines=AnyDef(), target_platform="android", skip_validation_checks=True)
    return [(n.GetCliques()[0].GetId(), n.GetCliques()[0].GetMessage().GetPresentableContent())
            for n in res.Preorder() if isinstance(n, M.MessageNode)]


def process(src, rel, log, scope=None):
    path = os.path.join(src, rel)
    base = os.path.dirname(rel)
    orig = open(path, encoding="utf-8").read()
    # grd + उसकी <part> (.grdp) फ़ाइलें — messages दोनों में
    files = [rel] + [os.path.normpath(os.path.join(base, f)) for f in re.findall(r'<part\s+file="([^"]+)"', orig)]
    if scope is not None:
        missing = [f for f in scope if f not in files]
        if missing:
            raise SystemExit(f"[strings] {rel}: scope की फ़ाइल grd का <part> नहीं: {missing}")
        files = list(scope)
    edits = {}
    for f in files:
        t = open(os.path.join(src, f), encoding="utf-8").read()
        n = MSG_RX.sub(lambda m: m.group(1) + brand_markup(m.group(2)) + m.group(3), t)
        if n != t:
            edits[f] = n
    if not edits:
        return []
    old_ids = [i for i, _ in message_ids(src, path)]
    for f, n in edits.items():
        open(os.path.join(src, f), "w", encoding="utf-8").write(n)
    new_msgs = message_ids(src, path)
    new_ids = [i for i, _ in new_msgs]
    # translation text ID को प्रभावित नहीं करता → हर message के translations में भी नाम-बदलाव। अपवाद: जिनके अंग्रेज़ी
    # में सुरक्षित वाक्यांश (Web Store आदि) है — वहाँ भाषाएँ "Web Store" का अनुवाद कर देती हैं ("Chrome 网上应用店"),
    # तो उनके translations नहीं छूते।
    skip_tr = {i for i, txt in new_msgs if PROTECT.search(txt)}
    all_new = set(new_ids)
    # scoped grd: केवल बदले (branded) messages के translations छूते हैं; बाकी साझा grd अछूती
    brand_ids = all_new if scope is None else set(n for o, n in zip(old_ids, new_ids) if o != n)
    new = "\n".join(edits.get(f) or open(os.path.join(src, f), encoding="utf-8").read() for f in files)
    if len(old_ids) != len(new_ids):
        raise SystemExit(f"[strings] {rel}: message संख्या बदली ({len(old_ids)} -> {len(new_ids)})")
    remap = {}
    for o, n in zip(old_ids, new_ids):
        if o != n:
            if remap.get(o, n) != n:
                raise SystemExit(f"[strings] {rel}: ID {o} के दो अलग नए IDs")
            remap[o] = n
    touched = sorted(edits)
    xtbs = sorted(set(re.findall(r'<file\s+path="([^"]+\.xtb)"', orig)))
    moved = dropped = rebranded = 0
    for x in xtbs:
        xrel = os.path.normpath(os.path.join(base, x))
        xp = os.path.join(src, xrel)
        if not os.path.isfile(xp):
            continue
        xs = open(xp, encoding="utf-8").read()
        present = set(re.findall(r'<translation\s+id="(\d+)"', xs))
        # coverage = कितने (नए) messages का अनुवाद है; Chrome/Chromium वाले दो variants एक ही नए text/ID में मिल
        # सकते हैं ("Restart Chrome"/"Restart Chromium" -> "Restart Swiftra") — वह नुकसान नहीं
        before = len({remap.get(i, i) for i in present & set(old_ids)})
        emitted = set()

        def tr(m):
            nonlocal moved, dropped, rebranded
            i = m.group(2)
            if i in remap:
                n = remap[i]
                if n in present and n not in remap:   # नया text पहले से अनुवादित (दूसरे message का) — वही रखें
                    dropped += 1; return ""
                moved += 1
            elif i in brand_ids:
                n = i
            else:
                return m.group(0)                      # इस grd का message नहीं
            if n in emitted:                           # merge: नया ID इस xtb में पहले ही लिखा गया
                dropped += 1; return ""
            emitted.add(n)
            body = m.group(4) if n in skip_tr else brand_markup(m.group(4), tr=True)
            if i == n and body != m.group(4):
                rebranded += 1
            return m.group(1) + n + m.group(3) + body + m.group(5)
        nxs = TR_RX.sub(tr, xs)
        after = len(set(re.findall(r'<translation\s+id="(\d+)"', nxs)) & all_new)
        if after != before:   # कोई भाषा translation न खोए — वरना build रुके
            raise SystemExit(f"[strings] {xrel}: translation coverage {before} -> {after}")
        if nxs != xs:
            open(xp, "w", encoding="utf-8").write(nxs); touched.append(xrel)
    left = [m for m in re.findall(r"[^\n>]{0,30}\bChrom(?:e|ium)\b[^\n<]{0,30}",
                                  "\n".join(brand_text_check(b) for b in MSG_RX.findall(new)))]
    log(f"[strings] {rel}: {len(remap)} IDs बदले, {len(xtbs)} xtb, {moved} translations नए ID पर, {rebranded} अपरिवर्तित-ID translations में नाम बदला, {dropped} दोहराव/merge हटे, "
        f"बचे सुरक्षित उल्लेख {len(left)}")
    return touched


def brand_text_check(groups):
    """ph के बाहर बचा "Chrome/Chromium" (केवल सुरक्षित वाक्यांश होने चाहिए) — रिपोर्ट हेतु।"""
    body = groups[1]
    out, depth = [], 0
    for tok in re.split(r"(<[^>]+>)", body):
        if tok.startswith("<"):
            if re.match(r"<ph\b", tok) and not tok.endswith("/>"): depth += 1
            elif tok.startswith("</ph"): depth = max(0, depth - 1)
        elif depth == 0:
            out.append(tok)
    return " ".join(out)


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr); return 2
    src = sys.argv[1]
    log = lambda s: print(s, file=sys.stderr)
    entries = [(g, None) if isinstance(g, str) else g for g in GRDS]
    for rel, _ in entries:
        if not os.path.isfile(os.path.join(src, rel)):
            log(f"[strings] grd नहीं मिला: {rel}"); return 1
    for rel, scope in entries:
        for t in process(src, rel, log, scope):
            print("TOUCHED " + t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
