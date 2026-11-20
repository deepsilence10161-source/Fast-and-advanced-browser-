# -*- coding: utf-8 -*-
"""Chrome vs Swiftra PERSONAL (private) build, 20-11-2026. Run: python3 tools/comparison/personal_edition.py
Writes docs/comparison-chrome-vs-swiftra-personal.{md,xlsx}"""
import os
M, S, D = "MEASURED", "SOURCE", "DESIGN+MEASURED"
H = ["#", "Area", "Kya check hua", "Chrome", "Swiftra Personal", "Proof", "Winner", "Seedhi baat / limit"]
R = []
def r(*a):
    assert len(a) == 7, a
    R.append(a)

A = "1 Google ko data"
r(A, "Browser chalu chhod do (idle) - Google ko requests", "Chrome 133: 3 requests (accounts.google.com, optimizationguide-pa, update.googleapis.com, www.google.com)", "0 requests, 0 Google naam resolve", M, "Swiftra", "NetLog sirf Chromium ka network dekhta hai. Android/Play services, keyboard, IP isme nahi aate. Chrome 133 hai, 158 nahi.")
r(A, "Website browse karte waqt Google ko requests", "2 (accounts.google.com, optimizationguide-pa)", "0", M, "Swiftra", "Sirf x64 emulator par. arm64 par egress measure nahi hua.")
r(A, "Address bar mein type/search karte waqt", "3 requests (www.google.com, accounts, optimizationguide)", "0 (suggestions default band)", M, "Swiftra", "Swiftra mein search suggestions band hain, yani suggestions ka feature bhi gaya. Jo query submit karte ho wo Google ko jaati hi hai (aapka decision).")
r(A, "Home page par popular-site tiles / doodle / favicon fetch", "Chrome source mein default ON (doodle `GetLogo`, popular sites fetch)", "OFF (patch 0110/0111), NetLog mein 0", S + " (Chrome) + " + M + " (Swiftra)", "Swiftra", "Chrome ka ye behaviour Chromium 155 source se confirm; Chrome 133 par alag se NetLog mein tiles nahi ginaye.")
r(A, "Usage stats / crash report Google ko", "Default ON, Settings mein band kar sakte ho; crash report mein page content/URL aa sakta hai (Google Help)", "Swiftra Personal mein koi Google sign-in/Sync nahi; NetLog mein 0 Google request", S + " (Chrome) + " + M + " (Swiftra)", "Swiftra", "Crash upload ka alag device test nahi kiya; NetLog 0 hai.")
A = "2 Local nishaan (history delete ke baad)"
r(A, "Browse karte waqt kitni files mein URL likha milta hai", "10 files (tabs open) / 13 files (tabs band), jisme page ki poori .mhtml copy + OfflinePages.db", "8 files; .mhtml copy aur OfflinePages.db nahi (patch 0111)", M, "Swiftra", "Synthetic loopback canary URL se test; asli sites nahi.")
r(A, "Delete browsing data (All time) ke baad - tabs khule", "5 files mein URL bacha: ukm_db-wal, tab12, tab13, tab_state0, shared_prefs xml", "5 files mein bacha: multi_instance_data.pb, flatbufferv1_tab1, tab2, tab_state0, tab_statearchived", M, "Barabar", "Dono mein tab/session files URL rakhti hain. Swiftra mein ye abhi FIXED NAHI hai (patch 0112 baaki).")
r(A, "Delete ke baad - saare tabs band", "Is image par measure NAHI ho paya: harness ko Chrome 133 mein 'Delete data' button nahi mila (time-range list dikhi, button nahi)", "Sessions/Tabs_*, flatbufferv1_tab3, tab_statearchived mein URL bacha", M + " (sirf Swiftra)", "Tay nahi (Chrome number nahi)", "Chrome ke liye number nahi hai, isliye winner nahi de raha. Harness fix karke dobara chalane se aa jayega.")
r(A, "Delete ke baad History, cache, Top Sites, Offline copy", "History, OfflinePages, Top Sites, cache saaf; ukm_db-wal bacha", "History, ukm_db, cache, Top Sites saaf; Offline copy bani hi nahi", M, "Swiftra", "Chhota fark: ukm_db Swiftra mein bhi saaf, Chrome mein WAL bacha.")
r(A, "Flash/SSD level recovery (coder deleted blocks nikale)", "Browser ke control mein nahi", "Browser ke control mein nahi (SQLite secure_delete ON hai: Chromium 155 source)", S, "Barabar", "Kisi bhi browser ke haath mein nahi. Phone encryption (FBE) hi asli dhaal hai.")
A = "3 Android/doosre apps mein leak"
r(A, "Web page se copy -> system clipboard", "Canary system clipboard tak pahuncha (K01 FAIL)", "Browser ke andar hi rahta hai (K01 PASS)", M, "Swiftra", "Trade-off: Swiftra se copy karke doosre app mein paste nahi hota.")
r(A, "Address bar copy / Find-in-page copy", "Dono system clipboard mein leak (K03, K04 FAIL)", "Dono contained (K03, K04 PASS)", M, "Swiftra", "Settings ka text field: Chrome LEAK, Swiftra CONTAINED. Dialog/keyboard fields audit nahi hue.")
r(A, "Web page ko system clipboard se paste milna", "Page ko system clipboard ka text mila (K02 FAIL)", "Nahi mila (K02 PASS)", M, "Swiftra", "Kisi doosre app ka copy kiya text page tak nahi jaata.")
r(A, "Download kahan jaata hai", "Shared /Download folder mein (gallery/file manager/doosre apps dekh sakte)", "App ke private folder mein", M, "Swiftra", "Chrome ka shared folder aasani deta hai; privacy mein Swiftra jeeta.")
r(A, "Screenshot / recents mein page dikhna", "Normal tab mein FLAG_SECURE nahi (C05 FAIL)", "FLAG_SECURE laga hai (C05 PASS)", M, "Swiftra", "Sirf flag check hua; asli screenshot try nahi kiya.")
r(A, "Android backup / cloud transfer", "ALLOW_BACKUP flag ON (dumpsys flags)", "Opt-out (C06 PASS)", M, "Swiftra", "Chrome ka C06 'NOT_RUN' tha kyunki backup allowed mila; flag se confirmed, restore test nahi.")
r(A, "Passkey request system credential provider tak jaana", "Pahunchi (C01 FAIL)", "Block (C01 PASS; arm64 mein NotSupportedError)", M, "Swiftra", "Chrome mein passkey kaam karta hai, Swiftra Personal mein nahi: privacy ke liye hatana, convenience ka nuksan.")
r(A, "System autofill service ko form dikhna", "Is test mein request nahi gayi (A01 PASS)", "Request nahi gayi (A01 PASS)", M, "Barabar", "Chrome 133 ke is ek form par; sab situations nahi.")
r(A, "Tel:/market: link se doosra app khulna", "Is harness mein hand-off nahi dikha (C04 PASS)", "Hand-off nahi (C04 PASS)", M, "Barabar", "Test negative-only hai; control (C09) se dialer dikhta hai, yani test andha nahi. Swiftra mein code se band hai (0103), Chrome ka koi code-level block nahi.")
A = "4 Account aur sign-in"
r(A, "Google/Android account browser mein", "Sign-in, Sync, Android accounts import - sab ON", "Sign-in/Sync band, accounts import nahi, Add Account block (C07 PASS)", D, "Swiftra", "Chrome jeetne wala feature (Sync) Swiftra Personal mein hai hi nahi. Gmail login karoge to Swiftra uska isolate nahi karta (container baaki).")
r(A, "Sync (bookmarks/passwords/tabs ek phone se doosre)", "Hai", "Nahi hai", S, "Chrome", "Apne throwaway Gmail ke liye Sync chahiye ho to Swiftra Personal abhi nahi dega.")
r(A, "Password manager", "Google Password Manager", "Local vault bhi nahi bana (0022 unimplemented)", S, "Chrome", "Swiftra mein password save nahi hota.")
A = "5 Speed aur memory (x64 emulator)"
r(A, "Cold start (28 runs har taraf, median)", "1089 ms (min 954, max 2647)", "934 ms (min 799, max 1153)", M, "Swiftra", "Swiftra ~14% tez. Chrome 133 vs Swiftra 155 hai, aur emulator hai; asli phone par alag aa sakta hai.")
r(A, "Memory (PSS, 20 sec baad, saari processes)", "~198 MB (4 processes)", "~306 MB (5 processes)", M, "Chrome", "Chrome ~35% kam memory. Pehle wale 147 MB wale number se alag tareeka hai, un dono ko mix mat karna.")
A = "6 Updates aur security"
r(A, "Engine version", "Android stable 158.0.8127.42 (17-11-2026); emulator wala Chrome 133 hai", "155.0.8059.80 (+.84 fixes)", S, "Chrome", "Swiftra ~3 releases peeche hai: Chrome 156/157/158 ke fix (157 mein 213, 158 mein 204 security bugs) Swiftra mein nahi hain. Ye sabse bada nuksan hai.")
r(A, "Update kaise aata hai", "Play Store se apne-aap", "Manual APK install; Play Store nahi", S, "Chrome", "Private build ka koi auto-update channel verified nahi.")
r(A, "Safe Browsing", "Standard: 4-byte hash Fastly relay se Google ko; Enhanced mein URL/content Google ko", "Local Shield list (phishing mazboot, malware kamzor); Google ko kuch nahi", S + " (public build E2E 13/13)", "Swiftra", "Privacy mein Swiftra, malware pakadne mein Chrome behtar. Personal build par Shield E2E dobara nahi chala.")
r(A, "Ad / tracker blocker", "Sirf Better Ads filter", "Built-in ad+tracker blocker (patch 0012/0013)", S + " (public build ADBLOCK_E2E PASS)", "Swiftra", "Personal build mein wahi patches hain; us APK par adblock test alag se nahi chala.")
r(A, "Third-party cookies", "Regular tab mein default allowed (2026); sirf Incognito mein blocked", "Default mein blocked (patch 0010; public build par emulator + arm64 Redroid E2E mein cross-site cookie nahi gaya)", S + " (Chrome) + " + M + " (Swiftra, public build)", "Swiftra", "Personal APK par ye test alag se nahi chala; patch wahi hai.")
r(A, "Fingerprinting (canvas/WebGL/audio) se bachav", "Built-in nahi (Chrome ke docs/old comparison source)", "Patch 0011 site-based noise, default ON", S + " (Chrome) + " + M + " (Swiftra, public build)", "Swiftra", "Kuch sites toot sakti hain; personal APK par alag test nahi.")
A = "7 Baaki"
r(A, "Incognito jaisi 'device par kuch save nahi' mode", "Hai (history/cookies save nahi; downloads/bookmarks rehte hain; websites aur Google ko activity dikhti hai)", "Alag model: profile save hota hai, par private storage mein; Incognito alag nahi", S + " (Chrome)", "Chrome", "Swiftra Personal har cheez save karta hai (aapka design). Ek tab ke liye 'kuch save nahi' chahiye to Chrome Incognito.")
r(A, "Face Guard (face se lock)", "Nahi hai", "Experimental, owner-only BiometricPrompt; x64 PASS, arm64 mein camera nahi", M, "Swiftra", "Experimental. 'Do chehre' test bahut chhota sample (2 of 2).")
r(A, "Stability (crash)", "Is run mein crash 0 (C01)", "Crash 0 (C01); Hub crash pehle mila tha, mitigate kiya, kaaran sabit nahi", M, "Barabar", "Chrome 133 ke ek run se Chrome ki stability ka dava nahi.")
r(A, "Whole-profile encryption", "Nahi (Android FBE)", "Nahi bana; sirf cookies Keystore se (0021)", S, "Barabar", "Dono par phone encryption hi hai.")
r(A, "IP address / ISP / website ko dikhna", "Dikhta hai", "Dikhta hai", S, "Barabar", "Kisi browser se nahi chhupta; VPN alag cheez hai.")

def tally():
    t = {}
    for x in R:
        t[x[5]] = t.get(x[5], 0) + 1
    return t

def md():
    t = tally()
    o = ["# Chrome vs Swiftra Personal - poori comparison (20-11-2026)", "",
         "**Kya kya compare hua:** Chrome **133.0.6943.137** (emulator image ka pehle se installed Chrome) vs Swiftra Personal **155.0.8059.80**, build 4f18a60, APK sha `d9a89bb5...`. "
         "Chrome ab Android par **158** stable hai; emulator mein Chrome update nahi ho sakta, isliye Chrome ke numbers purane version ke hain.", "",
         "**Proof ka matlab:** MEASURED = device par maapa (CI runs 44712836868 aur 44713040218, evidence/chrome-vs-personal-2026-11-20.json). SOURCE = Chromium source ya Google docs se confirm. "
         "Jo cell measure nahi ho paya wahan 'winner' nahi diya, kyunki andaza lagana galat hota.", "",
         "| " + " | ".join(H) + " |", "|" + "---|" * len(H)]
    for i, x in enumerate(R, 1):
        o.append("| " + " | ".join([str(i), x[0], x[1], x[2], x[3], x[4], "**%s**" % x[5], x[6]]) + " |")
    o += ["", "## Score", ""] + ["- %s: %d" % (k, v) for k, v in sorted(t.items())]
    open("docs/comparison-chrome-vs-swiftra-personal.md", "w", encoding="utf-8").write("\n".join(o) + "\n")

def xl():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook(); ws = wb.active; ws.title = "Comparison"
    ws.append(H)
    for i, x in enumerate(R, 1):
        ws.append([i, x[0], x[1], x[2], x[3], x[4], x[5], x[6]])
    fills = {"Swiftra": "C6EFCE", "Chrome": "FFC7CE", "Barabar": "FFEB9C"}
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F3864")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
        row[6].fill = PatternFill("solid", fgColor=fills.get(row[6].value, "D9D9D9"))
    for col, w in zip("ABCDEFGH", [4, 22, 38, 42, 42, 20, 16, 55]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    wb.save("docs/comparison-chrome-vs-swiftra-personal.xlsx")

if __name__ == "__main__":
    md(); xl(); print(len(R), tally())
