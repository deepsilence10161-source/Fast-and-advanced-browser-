#!/usr/bin/env python3
"""Swiftra Shield: attribution for the threat-feed data in the shipped "Open source licenses" page.

The Shield threat list (scripts/shield/build_shield_db.py, published by .github/workflows/shield-db.yml and downloaded
by the app) is derived from Phishing.Database (MIT) and TweetFeed (CC0-1.0). MIT requires its copyright and permission
notice in every copy, so the app carries it in chrome://credits (generate_about_credits = true in args.gn:
tools/licenses/licenses.py lists every third_party/* directory that has a README.chromium, the same mechanism as
0013 for the ad-block lists). The same text is uploaded next to the list as NOTICE.txt
(build_shield_db.FEED_NOTICE; tests/test_licences.py keeps the two identical).
Tranco (build-time guard only) is not redistributed and therefore not listed.
"""
import os
import sys

README = """Name: Swiftra Shield threat-feed data (Phishing.Database, TweetFeed)
Short Name: swiftra_shield_feeds
URL: https://github.com/Phishing-Database/Phishing.Database
Version: N/A
License: MIT, CC0-1.0
License File: LICENSE
Security Critical: no
Shipped: yes

Description:
Phishing and malware URL/domain lists converted to 64-bit hashes for Swiftra Shield's on-device lookup. The list
is built by Swiftra's shield-db workflow and downloaded by the browser; no browsing data is sent anywhere.
"""

LICENSE = """Swiftra Shield threat-feed data

Phishing.Database (https://github.com/Phishing-Database/Phishing.Database)
  Used: phishing-links-ACTIVE.txt, phishing-domains-ACTIVE.txt (converted to 64-bit hashes)

MIT License

Copyright (c) 2018-2025 Mitchell Krog - github.com/mitchellkrogza
Copyright (c) 2018-2025 Nissar Chababy - github.com/funilrys
Copyright (c) 2018-2025 Phishing.Database Contributors - github.com/Phishing-Database

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

TweetFeed (https://github.com/0xDanielLopez/TweetFeed)
  Used: blocklist urls.txt and domains.txt (converted to 64-bit hashes)
  Licence: Creative Commons Zero v1.0 Universal (CC0-1.0), public domain dedication
           https://creativecommons.org/publicdomain/zero/1.0/
  Attribution is not required by CC0; it is given here as a courtesy.
"""


def main():
    src = sys.argv[1]
    tp = os.path.join(src, "third_party", "swiftra_shield_feeds")
    os.makedirs(tp, exist_ok=True)
    for name, text in (("README.chromium", README), ("LICENSE", LICENSE)):
        with open(os.path.join(tp, name), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"TOUCHED third_party/swiftra_shield_feeds/{name}")


if __name__ == "__main__":
    main()
