# Personal build: Google ko jaane wala data kam karna (20 Nov 2026)

User ka nirdesh: login ke liye ek alag faltu Gmail chalega, Google sync se dikkat nahi, lekin Google ke paas jitna kam data jaye utna behtar.
Isliye pehle MAAPA (NetLog), phir band karna. Naap na ho to "band" nahi likhte.

## Maapa (run 44690100652, x64 emulator, APK 3b4eae8c..., commit 0a4f6bd)
Chromium ke network stack se, har cold start par, koi page khole bina:

| Request | Kya hai | Login ke baad kya hota |
|---|---|---|
| POST accounts.google.com/ListAccounts | cookie-jar ke Google accounts ki list | Gmail cookie ke saath jaata |
| GET www.google.com/async/folae (har start, 2x idle me) | AI Mode eligibility check | Google cookie ke saath: "yeh browser is account se zinda hai" |
| GET http://clients2.google.com/time/1/current | network time tracker (plain http, cookie nahi) | sirf IP + samay |

browse/search phase is run me BEKAAR hai: first-run screen ne navigation roka (example.org ki koi request nahi dikhi).
`--disable-fre` jodkar dobara chalana hoga.

## Kya badla (0110 guard + 0111 patch, source layer, device par ABHI NAPA NAHI)
- `omnibox::kAimEnabled` default OFF: eligibility service shuru hi nahi hoti -> folae aur uske saath ListAccounts nahi. AI Mode button bhi nahi.
- `network_time::kNetworkTimeServiceQuerying` default OFF har platform par: clients2 time query nahi; device ki ghadi par bharosa.

Dono sirf default hain (BASE_FEATURE); koi nayi logic nahi. Hal-fil ghadi galat ho to cert-error ki clock-skew pehchaan kamzor hogi.

## Abhi bhi Google ko jaata (jaanbujh kar, ya browser ke bas ke bahar)
- Jo website user khud kholta hai (google.com, Gmail, YouTube) - wahan login cookie jaayegi hi. Isliye Gmail wala login alag rakho.
- Default search engine agar Google hai: omnibox me likha hua query + suggestions Google ko jaate. Chhote badlav ka vikalp: DuckDuckGo/Brave default (user se poochna hai).
- NetLog Java HttpURLConnection (update channel -> GitHub), Android system (Gboard, Play Protect, backup) nahi dekhta.
- IP address: sirf VPN/Tor chhupata hai.

## Download "can't open file" (user ne bataya)
Yeh design hai, bug nahi: 0103 ne DownloadUtils se bahar ke app me file kholna hataya, aur download app-private storage me jaate hain.
APK ko system installer tak pahunchane ka koi rasta nahi. Naya APK doosre browser/GitHub release se lo, ya (user manjoor kare to) sirf .apk ke liye
ek explicit "Install update" button banaya jaa sakta hai - containment me jaanbujh kar chhed, isliye puchhe bina nahi.
