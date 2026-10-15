#!/usr/bin/env python3
"""Run experiments/chat-rendering/fixture.html in a real browser via the DevTools protocol
and record its self-reported results + a screenshot.

Desktop:  google-chrome --headless=new --remote-debugging-port=9222 <url>   then  --devtools http://127.0.0.1:9222
Android:  adb reverse tcp:8000 tcp:8000 ; am start -a VIEW -d <url> <pkg> ;
          adb forward tcp:9222 localabstract:chrome_devtools_remote          then  --devtools http://127.0.0.1:9222
Exit code: 0 = all fixture cases passed, 1 = some failed / error, 2 = harness could not reach the page.
"""
import argparse, base64, json, sys, time, urllib.request

import websocket  # websocket-client


def targets(base):
    with urllib.request.urlopen(base + "/json/list", timeout=10) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--devtools", default="http://127.0.0.1:9222")
    ap.add_argument("--match", default="fixture.html")
    ap.add_argument("--out", required=True, help="output prefix (writes .json and .png)")
    ap.add_argument("--platform", required=True)
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args()

    deadline = time.time() + a.timeout
    page, last_err = None, None
    while time.time() < deadline and not page:
        try:
            page = next((t for t in targets(a.devtools) if t.get("type") == "page" and a.match in t.get("url", "")), None)
        except Exception as e:  # devtools socket not up yet
            last_err = e
        if not page: time.sleep(2)
    if not page:
        json.dump({"platform": a.platform, "harness_error": f"page not found: {last_err}"}, open(a.out + ".json", "w"), indent=1)
        print("harness: page not found", last_err); return 2

    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30, suppress_origin=True)
    mid = 0

    def call(method, **params):
        nonlocal mid
        mid += 1; ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid: return m

    res = None
    while time.time() < deadline:
        r = call("Runtime.evaluate", expression="JSON.stringify(window.__chatResults || null)", returnByValue=True)
        v = r.get("result", {}).get("result", {}).get("value")
        if v and v != "null": res = json.loads(v); break
        time.sleep(1)
    shot = call("Page.captureScreenshot", format="png").get("result", {}).get("data")
    if shot: open(a.out + ".png", "wb").write(base64.b64decode(shot))
    ws.close()
    out = {"platform": a.platform, "page_url": page.get("url"), "results": res}
    json.dump(out, open(a.out + ".json", "w"), indent=1)
    if not res: print("harness: no results before timeout"); return 2
    if "error" in res: print("fixture error:", res["error"]); return 1
    print(f"{a.platform}: {res['passed']}/{res['total']} passed; UA={res['userAgent']}")
    for t in res["results"]: print(("ok   " if t["ok"] else "FAIL ") + t["name"], json.dumps(t["detail"]))
    return 0 if res["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
