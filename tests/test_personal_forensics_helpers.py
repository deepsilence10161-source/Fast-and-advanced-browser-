import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/ci"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import personal_forensics_e2e as F  # noqa: E402


def test_parse_grep_files_keeps_names_only_and_drops_errors():
    out = ("/data/data/com.x/app_chrome/Default/History\n"
           "/data/data/com.x/cache/Cache/Cache_Data/abc_0\n"
           "grep: /data/data/com.x/foo: Permission denied\n"
           "/sdcard/Download/a.txt\n\n"
           "/data/data/com.x/app_chrome/Default/History\n")
    assert F.parse_grep_files(out, "com.x") == [
        "/sdcard/Download/a.txt", "app_chrome/Default/History", "cache/Cache/Cache_Data/abc_0"]


def test_summarize_hits_counts_per_pattern_and_unions_files():
    s = F.summarize_hits({"url_path": ["a", "b"], "title": ["b"], "url_query": []})
    assert s["files"] == ["a", "b"] and s["by_pattern"] == {"url_path": 2, "title": 1, "url_query": 0}


def test_data_dirs_cover_private_and_shared_locations():
    d = F.data_dirs("com.x")
    assert "/data/data/com.x" in d and "/sdcard/Download" in d and "/sdcard/Android/data/com.x" in d
