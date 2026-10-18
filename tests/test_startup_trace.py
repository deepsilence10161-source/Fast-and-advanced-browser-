"""scripts/ci/startup_trace.py: trace parsing and the per-thread summary (self time, top level, milestones)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
import startup_trace as st  # noqa: E402


def ev(name, ts, dur, tid=1, pid=10, ph="X"):
    return {"name": name, "ts": ts, "dur": dur, "tid": tid, "pid": pid, "ph": ph, "cat": "toplevel"}


EVENTS = [
    {"ph": "M", "name": "process_name", "pid": 10, "args": {"name": "Browser"}},
    {"ph": "M", "name": "thread_name", "pid": 10, "tid": 1, "args": {"name": "CrBrowserMain"}},
    {"ph": "M", "name": "thread_name", "pid": 10, "tid": 2, "args": {"name": "Chrome_IOThread"}},
    ev("BrowserMainRunnerImpl::Initialize", 0, 100000),
    ev("ProfileManager::CreateProfile", 10000, 60000),
    ev("KeyedServiceFactory::GetServiceForContext", 20000, 30000),
    ev("ChromeTabbedActivity.onCreate", 150000, 40000),
    {"ph": "B", "name": "RunTask", "ts": 200000, "tid": 2, "pid": 10},
    {"ph": "E", "ts": 205000, "tid": 2, "pid": 10},
]


def test_parse_tolerates_truncation():
    raw = json.dumps({"traceEvents": EVENTS}).encode()
    assert len(st.parse_trace(raw)) == len(EVENTS)
    cut = json.dumps({"traceEvents": EVENTS})[:-2].encode()        # lost the closing "]}"
    assert len(st.parse_trace(cut)) == len(EVENTS)
    assert st.parse_trace(b"garbage") == []


def test_summary_self_time_and_milestones():
    r = st.summarize(EVENTS)
    m = r["threads"]["Browser/CrBrowserMain"]
    assert r["span_ms"] == 205.0
    assert m["busy_ms"] == 140.0                                   # two top-level slices: 100 + 40 ms
    self_t = {n: v for n, v, _ in m["self"]}
    assert self_t["BrowserMainRunnerImpl::Initialize"] == 40.0     # 100 - 60 (child)
    assert self_t["ProfileManager::CreateProfile"] == 30.0         # 60 - 30 (child)
    assert self_t["KeyedServiceFactory::GetServiceForContext"] == 30.0
    names = [n for n, _, _ in m["milestones"]]
    assert "ChromeTabbedActivity.onCreate" in names and "ProfileManager::CreateProfile" in names
    assert r["threads"]["Browser/Chrome_IOThread"]["self"] == [["RunTask", 5.0, 1]]   # B/E pair


def test_wired_into_run_capture():
    s = open(os.path.join(ROOT, "scripts", "ci", "run_capture.sh"), encoding="utf-8").read()
    assert s.index("speed_e2e.py") < s.index("startup_trace.py")
    assert "--trace-startup-format=json" in open(os.path.join(ROOT, "scripts", "ci", "startup_trace.py")).read()
