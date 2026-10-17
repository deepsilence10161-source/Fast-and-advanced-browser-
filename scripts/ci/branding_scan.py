#!/usr/bin/env python3
"""UI hierarchy (uiautomator *.xml) में दिखने वाले text/content-desc में "Chrome"/"Chromium" branding खोजना।

उद्देश्य (b2): Swiftra build की हर capture हुई screen पर app UI में Google/Chromium का नाम न दिखे — screenshot पर
नज़र डालने की बजाय मापने योग्य। केवल इस app के package के nodes; web page content (WebView/renderer nodes का
text) नहीं गिनता क्योंकि वह साइट का है। अनुमत (जानबूझकर सुरक्षित, देखें patches/0002-swiftra-strings.py):
chrome:// URLs, Chrome Web Store, ChromeOS/Chromebook/Chromecast, The Chromium Authors, Google legal doc नाम।

Usage: branding_scan.py <dir-with-xml> [--pkg com.swiftra.app] [--json out.json]
Exit 0 = कोई leak नहीं; 3 = leak मिले; 2 = कोई xml नहीं।
"""
import argparse
import glob
import html
import json
import os
import re
import sys

# "Chrome"/"Chromium" (capital C) कहीं भी (जैसे Zulu "seChromium"); lowercase केवल शब्द-शुरुआत पर ("monochrome" नहीं)
BRAND = re.compile(r"Chrom(e|ium)|(?<![A-Za-z])chrom(e|ium)(?![a-z])|CHROM(E|IUM)")
ALLOWED = re.compile(
    r"chrome://\S*|chrome-\w+://\S*|Chrome\s*Web\s*Store|Chrom(e|ium)\s*OS|Chrome(book|box|base|cast)\w*"
    r"|The Chromium Authors|Chromium open[- ]source|(Google )?Chrome (and|&) Chrome ?OS Additional Terms of Service"
    r"|(Google )?Chrome (Additional )?Terms of Service|(Google )?Chrome Privacy (Notice|Whitepaper)", re.I)
NODE = re.compile(r"<node\b([^>]*)>|<node\b([^>]*)/>")
ATTR = re.compile(r'(\w[\w-]*)="([^"]*)"')
WEB_CLASSES = ("android.webkit.WebView",)


# सत्यता (truth) scan: Swiftra (non-Google-branded) build के लिए upstream के वे दावे जो असत्य हैं और जिनमें "Chrome" शब्द
# नहीं — branding scan इन्हें नहीं पकड़ता। patches: 0002 FACT_FIXES (copyright), 0004 (metrics toggle), 0005 (update check)।
FALSE_CLAIMS = {
    "copyright_google_llc": re.compile(r"Copyright\s+\d{4}\s+Google\s+(LLC|Inc)", re.I),
    "metrics_sends_to_google": re.compile(r"sends usage statistics and crash reports to Google", re.I),
    "update_up_to_date": re.compile(r"\bis up to date\b", re.I),
}
# अपेक्षित सही text (उपस्थिति का प्रमाण; न मिलना = वह पन्ना capture नहीं हुआ या fix नहीं पहुँचा)
EXPECTED = {
    "copyright_chromium_authors": re.compile(r"Copyright\s+\d{4}\s+The Chromium Authors", re.I),
    "update_cant_check": re.compile(r"Can.t check \S+ version", re.I),
}


def app_texts(xml, pkg):
    """इस app के (web content नहीं) हर node का (field, value, attrs)।"""
    # WebView/web-content subtree छोड़ें: renderer nodes का resource-id खाली और class android.view.View होता है,
    # इसलिए पहचान के लिए package + web-content ancestor का stack रखें
    depth_web = []
    for m in re.finditer(r"<node\b[^>]*?(/?)>|</node>", xml):
        tag = m.group(0)
        if tag == "</node>":
            if depth_web:
                depth_web.pop()
            continue
        a = dict(ATTR.findall(tag))
        selfclose = tag.endswith("/>")
        in_web = bool(depth_web and depth_web[-1]) or a.get("class") in WEB_CLASSES or \
            a.get("resource-id", "").endswith(":id/content_container_web") or a.get("class") == "android.webkit.WebView"
        if not selfclose:
            depth_web.append(in_web)
        if a.get("package") != pkg or in_web:
            continue
        for f in ("text", "content-desc"):
            v = html.unescape(a.get(f, ""))
            if v:
                yield f, v, a


def scan_xml(xml, pkg):
    leaks = []
    for f, v, a in app_texts(xml, pkg):
        if BRAND.search(ALLOWED.sub("", v)):
            leaks.append({"field": f, "value": v, "id": a.get("resource-id", ""), "class": a.get("class", "")})
    return leaks


def scan_claims(xml, pkg):
    """(असत्य दावे [{claim, value, id}], मिले अपेक्षित-text keys set)"""
    bad, seen = [], set()
    for f, v, a in app_texts(xml, pkg):
        for k, rx in FALSE_CLAIMS.items():
            if rx.search(v):
                bad.append({"claim": k, "field": f, "value": v, "id": a.get("resource-id", "")})
        seen |= {k for k, rx in EXPECTED.items() if rx.search(v)}
    return bad, seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("--pkg", default="com.swiftra.app"); ap.add_argument("--json")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.dir, "*.xml")))
    if not files:
        print("branding_scan: कोई xml नहीं"); return 2
    res = {}
    for f in files:
        l = scan_xml(open(f, encoding="utf-8", errors="replace").read(), a.pkg)
        if l:
            res[os.path.basename(f)] = l
    total = sum(len(v) for v in res.values())
    for k, v in res.items():
        for x in v:
            print(f"LEAK {k}: {x['field']}={x['value']!r} id={x['id']}")
    print(f"branding_scan: {len(files)} screens, {total} leaks")
    if a.json:
        json.dump({"screens": len(files), "leaks": total, "by_screen": res}, open(a.json, "w"), ensure_ascii=False, indent=1)
    return 3 if total else 0


if __name__ == "__main__":
    sys.exit(main())
