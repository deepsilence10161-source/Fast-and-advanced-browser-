# -*- coding: utf-8 -*-
"""Build docs/comparison-chrome-vs-swiftra.{md,xlsx} from rows.py.

Usage: python3 tools/comparison/build.py
"""
import collections, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import rows as D
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WIN = ["Swiftra", "Chrome", "बराबर", "अनिर्णीत", "लागू नहीं"]
FILL = {"Swiftra": "C6EFCE", "Chrome": "FFC7CE", "बराबर": "DDEBF7",
        "अनिर्णीत": "FFEB9C", "लागू नहीं": "E7E6E6"}


def counts():
    total = collections.Counter(r[6] for r in D.R)
    bad = set(total) - set(WIN)
    assert not bad, bad
    cats = collections.OrderedDict()
    for r in D.R:
        cats.setdefault(r[0], collections.Counter())[r[6]] += 1
    return total, cats


def summary_lines(total):
    n = len(D.R)
    decided = total["Swiftra"] + total["Chrome"] + total["बराबर"]
    return n, decided


def md():
    total, cats = counts()
    n, decided = summary_lines(total)
    o = []
    o.append(f"# असली Chrome बनाम Swiftra: विस्तृत तुलना ({D.DATE})\n")
    o.append(f"- {D.CHROME_REF}\n- {D.SWIFTRA_BUILD}\n")
    o.append("- स्थिति के शब्द: **PASS (emulator)** = x64 Android emulator, **PASS (Redroid)** = arm64 Redroid, "
             "**static** = केवल स्रोत/कोड पढ़कर, **NOT RUN** = जाँचा नहीं, **कमी** = मौजूद नहीं।\n")
    o.append("- विजेता: **Swiftra** / **Chrome** / **बराबर** / **अनिर्णीत** (माप या test नहीं) / **लागू नहीं** (कानूनी विषय)।\n")
    o.append("- यही data रंगीन Excel रूप में: `docs/comparison-chrome-vs-swiftra.xlsx` (स्रोत: `tools/comparison/rows.py`)।\n")
    o.append("\n## तुलना तालिका\n")
    o.append("| " + " | ".join(D.COLUMNS) + " |")
    o.append("|" + "---|" * len(D.COLUMNS))
    for i, r in enumerate(D.R, 1):
        cells = [str(i)] + [c.replace("|", "/") for c in r]
        cells[7] = f"**{cells[7]}**"
        o.append("| " + " | ".join(cells) + " |")
    o.append("\n## अंतिम सारांश\n")
    o.append(f"कुल **{n}** पंक्तियाँ। Swiftra **{total['Swiftra']}**, Chrome **{total['Chrome']}**, "
             f"बराबर **{total['बराबर']}**, अनिर्णीत **{total['अनिर्णीत']}**, लागू नहीं **{total['लागू नहीं']}**।\n")
    o.append("| क्षेत्र | Swiftra | Chrome | बराबर | अनिर्णीत | लागू नहीं |")
    o.append("|---|---|---|---|---|---|")
    for c, k in cats.items():
        o.append(f"| {c} | " + " | ".join(str(k[w]) for w in WIN) + " |")
    o.append("| **कुल** | " + " | ".join(f"**{total[w]}**" for w in WIN) + " |")
    o.append("")
    o.append("**ईमानदार फ़ैसला:** आज कुल मिलाकर **असली Chrome आगे है**। Swiftra अभी हर चीज़ में Chrome से आगे नहीं है।\n")
    o.append("- **Swiftra कहाँ जीतता है:** privacy और पारदर्शिता में। Standard Safe Browsing में शून्य डेटा बाहर जाता है, "
             "telemetry नहीं, server experiments नहीं, startup पर कम requests, doodle ping नहीं, और हर बदलाव खुले patch में।")
    o.append("- **Chrome कहाँ जीतता है:** security patch level (.84 बनाम .80), अपने-आप update, Safe Browsing coverage और Enhanced AI, "
             "HTTPS-by-default, Google की सेवाएँ (Sync, Password Manager, Translate, Gemini, Discover), "
             "और emulator पर start-समय/memory (अलग version पर मापा गया, असली फ़ोन पर नहीं)।")
    o.append("- **बराबर:** एक ही Chromium 155 engine वाली चीज़ें (site isolation, DoH, PQ crypto, JPEG XL, extensions का न होना, cookies default)।")
    o.append("- **अनिर्णीत:** असली फ़ोन पर speed, Speedometer, battery, AI Mode, Incognito lock, ad filter, असली Arena — यहाँ बिना माप के कोई दावा नहीं।\n")
    o.append("### Chrome को हराने का क्रम (प्राथमिकता अनुसार)\n")
    o.append("| क्रम | काम | असर | संबंधित पंक्ति |")
    o.append("|---|---|---|---|")
    for p in D.PLAN:
        o.append("| " + " | ".join(p) + " |")
    o.append("\nक्रम 1-3 पूरे होने पर Chrome की 2 बढ़त (patch level, HTTPS) बराबर होंगी "
             "और cookies/tracker blocking से 2 नई Swiftra जीत बनेंगी; हर दावा फिर से E2E से साबित किया जाएगा।\n")
    o.append("\n## स्रोत\n")
    for s in D.SOURCES:
        o.append(f"- **{s[0]}** — {s[1]}: {s[2]}")
    o.append("")
    p = os.path.join(ROOT, "docs", "comparison-chrome-vs-swiftra.md")
    open(p, "w", encoding="utf-8").write("\n".join(o))
    return p


def xlsx():
    total, cats = counts()
    n, decided = summary_lines(total)
    wb = Workbook()
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill("solid", fgColor="1F3864")
    head_font = Font(bold=True, color="FFFFFF", size=11)
    wrap = Alignment(wrap_text=True, vertical="top")

    # ---- Sheet 1: तुलना ----
    ws = wb.active
    ws.title = "तुलना"
    ws["A1"] = f"असली Chrome 155 (Android) बनाम Swiftra — विस्तृत तुलना ({D.DATE})"
    ws["A1"].font = Font(bold=True, size=15, color="1F3864")
    ws["A2"] = D.CHROME_REF
    ws["A3"] = D.SWIFTRA_BUILD
    for c in ("A2", "A3"):
        ws[c].font = Font(italic=True, size=9, color="595959")
    hr = 5
    widths = [5, 16, 26, 38, 42, 34, 16, 12, 38, 42]
    for j, h in enumerate(D.COLUMNS, 1):
        cell = ws.cell(row=hr, column=j, value=h)
        cell.fill, cell.font, cell.border = head_fill, head_font, border
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        ws.column_dimensions[get_column_letter(j)].width = widths[j - 1]
    ws.row_dimensions[hr].height = 32
    for i, r in enumerate(D.R, 1):
        vals = [i] + list(r)
        rr = hr + i
        for j, v in enumerate(vals, 1):
            cell = ws.cell(row=rr, column=j, value=v)
            cell.alignment, cell.border = wrap, border
        w = ws.cell(row=rr, column=8)
        w.fill = PatternFill("solid", fgColor=FILL[r[6]])
        w.font = Font(bold=True)
        w.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        longest = max(len(str(v)) / max(widths[k] - 2, 1) for k, v in enumerate(vals))
        ws.row_dimensions[rr].height = max(30, min(150, 15 * (int(longest) + 1)))
    last = hr + len(D.R)
    tab = Table(displayName="Comparison", ref=f"A{hr}:{get_column_letter(len(D.COLUMNS))}{last}")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
    ws.add_table(tab)
    ws.freeze_panes = ws.cell(row=hr + 1, column=4)

    # ---- Sheet 2: सारांश ----
    s = wb.create_sheet("सारांश")
    s["A1"] = "अंतिम सारांश"
    s["A1"].font = Font(bold=True, size=15, color="1F3864")
    s["A3"], s["B3"] = "विजेता", "पंक्तियाँ"
    for c in ("A3", "B3"):
        s[c].fill, s[c].font, s[c].border = head_fill, head_font, border
    for k, w in enumerate(WIN, 4):
        s.cell(row=k, column=1, value=w).fill = PatternFill("solid", fgColor=FILL[w])
        s.cell(row=k, column=1).font = Font(bold=True)
        s.cell(row=k, column=2, value=total[w])
        for col in (1, 2):
            s.cell(row=k, column=col).border = border
    s.cell(row=9, column=1, value="कुल").font = Font(bold=True)
    s.cell(row=9, column=2, value=n).font = Font(bold=True)
    ch = BarChart()
    ch.type = "bar"
    ch.title = "विजेता के अनुसार पंक्तियाँ"
    ch.legend = None
    ch.add_data(Reference(s, min_col=2, min_row=3, max_row=8), titles_from_data=True)
    ch.set_categories(Reference(s, min_col=1, min_row=4, max_row=8))
    ch.height, ch.width = 7, 14
    s.add_chart(ch, "D3")

    r0 = 12
    hdr = ["क्षेत्र"] + WIN
    for j, h in enumerate(hdr, 1):
        c = s.cell(row=r0, column=j, value=h)
        c.fill, c.font, c.border = head_fill, head_font, border
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    for i, (cat, k) in enumerate(cats.items(), 1):
        s.cell(row=r0 + i, column=1, value=cat).border = border
        for j, w in enumerate(WIN, 2):
            c = s.cell(row=r0 + i, column=j, value=k[w])
            c.border = border
            c.alignment = Alignment(horizontal="center")
            if k[w]:
                c.fill = PatternFill("solid", fgColor=FILL[w])
    rt = r0 + len(cats) + 1
    s.cell(row=rt, column=1, value="कुल").font = Font(bold=True)
    for j, w in enumerate(WIN, 2):
        c = s.cell(row=rt, column=j, value=total[w])
        c.font, c.alignment = Font(bold=True), Alignment(horizontal="center")

    verdict = [
        ("ईमानदार फ़ैसला", "आज कुल मिलाकर असली Chrome आगे है। Swiftra अभी हर चीज़ में Chrome से आगे नहीं है।"),
        ("Swiftra की जीत", "privacy और पारदर्शिता: Standard Safe Browsing में शून्य डेटा बाहर, telemetry नहीं, "
                          "server experiments नहीं, startup पर कम requests, doodle ping नहीं, खुले patches।"),
        ("Chrome की जीत", "security patch level (.84 बनाम .80), अपने-आप update, Safe Browsing coverage + Enhanced AI, "
                         "HTTPS-by-default, Google सेवाएँ (Sync, Password Manager, Translate, Gemini, Discover), "
                         "emulator पर start/memory (अलग version, असली फ़ोन नहीं)।"),
        ("बराबर", "एक ही Chromium 155 engine वाली चीज़ें: site isolation, DoH, PQ crypto, JPEG XL, extensions का न होना, cookies default।"),
        ("अनिर्णीत", "असली फ़ोन पर speed, Speedometer, battery, AI Mode, Incognito lock, ad filter, असली Arena — बिना माप के कोई दावा नहीं।"),
    ]
    rv = rt + 2
    for i, (a, b) in enumerate(verdict):
        s.cell(row=rv + i, column=1, value=a).font = Font(bold=True)
        s.merge_cells(start_row=rv + i, start_column=2, end_row=rv + i, end_column=8)
        c = s.cell(row=rv + i, column=2, value=b)
        c.alignment = wrap
        s.row_dimensions[rv + i].height = 48
    rp = rv + len(verdict) + 1
    s.cell(row=rp, column=1, value="Chrome को हराने का क्रम").font = Font(bold=True, size=12, color="1F3864")
    for j, h in enumerate(["क्रम", "काम", "असर", "संबंधित पंक्ति"], 1):
        c = s.cell(row=rp + 1, column=j, value=h)
        c.fill, c.font, c.border = head_fill, head_font, border
    for i, p in enumerate(D.PLAN, 2):
        for j, v in enumerate(p, 1):
            c = s.cell(row=rp + i, column=j, value=v)
            c.alignment, c.border = wrap, border
        s.row_dimensions[rp + i].height = 32
    for col, wdt in zip("ABCDEFGH", [22, 44, 34, 18, 12, 12, 12, 12]):
        s.column_dimensions[col].width = wdt

    # ---- Sheet 3: स्रोत ----
    t = wb.create_sheet("स्रोत")
    for j, h in enumerate(["ID", "स्रोत", "URL"], 1):
        c = t.cell(row=1, column=j, value=h)
        c.fill, c.font = head_fill, head_font
    for i, (a, b, u) in enumerate(D.SOURCES, 2):
        t.cell(row=i, column=1, value=a)
        t.cell(row=i, column=2, value=b).alignment = wrap
        c = t.cell(row=i, column=3, value=u)
        c.hyperlink, c.font = u, Font(color="0563C1", underline="single")
    t.column_dimensions["A"].width, t.column_dimensions["B"].width, t.column_dimensions["C"].width = 6, 60, 90

    p = os.path.join(ROOT, "docs", "comparison-chrome-vs-swiftra.xlsx")
    wb.save(p)
    return p


if __name__ == "__main__":
    print(md())
    print(xlsx())
    t, _ = counts()
    print(len(D.R), dict(t))
