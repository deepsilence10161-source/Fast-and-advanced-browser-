"""Verified, offline PUBLIC source slices for personal-layer host tests.

Not an Android checkout or build. Hashes bind fixture bytes to the recorded
pinned public sources; no APK/device/profile or runtime containment is checked.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).resolve().parent
FIXTURES = (
    ("upstream-index.json", "upstream-155.0.8059.80.json.gz"),
    ("egress-upstream-index.json", "egress-upstream-155.0.8059.80.json.gz"),
    ("face-guard-upstream-index.json", "face-guard-upstream-155.0.8059.80.json.gz"),
    ("signin-message-upstream-index.json", "signin-message-upstream-155.0.8059.80.json.gz"),
    ("omnibox-clipboard-upstream-index.json", "omnibox-clipboard-upstream-155.0.8059.80.json.gz"),
    ("google-egress-upstream-index.json", "google-egress-upstream-155.0.8059.80.json.gz"),
)


def load_sources() -> dict[str, str]:
    out = {}
    for index_name, data_name in FIXTURES:
        index = json.loads((DIRECTORY / index_name).read_text())
        raw = (DIRECTORY / data_name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != index["fixture_gzip_sha256"]:
            raise ValueError("fixture_hash_mismatch")
        with gzip.open(DIRECTORY / data_name, "rb") as stream:
            data = stream.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("fixture_too_large")
        sources = json.loads(data)
        if set(sources) != set(index["fixture_paths"]):
            raise ValueError("fixture_path_set_mismatch")
        hashes = {entry["path"]: entry["sha256"] for entry in index["files"]
                  if entry["status"] in ("READ", "FETCHED")}
        for name, text in sources.items():
            path = PurePosixPath(name)
            if (path.is_absolute() or ".." in path.parts or "\\" in name
                    or "\0" in name or not isinstance(text, str)):
                raise ValueError("unsafe_fixture_path_or_text")
            if hashlib.sha256(text.encode()).hexdigest() != hashes[name]:
                raise ValueError("fixture_source_hash_mismatch")
            if name in out and out[name] != text:
                raise ValueError("fixture_source_conflict")
            out[name] = text
    return out


def series() -> list[str]:
    return [line for raw in (ROOT / "patches/personal/series").read_text().splitlines()
            if (line := raw.strip()) and not line.startswith("#")]


def apply_strict(src: Path) -> list[dict]:
    """Apply ONLY to caller-owned synthetic source tree; fail on drift/offset/fuzz."""
    results = []
    for name in series():
        file = ROOT / "patches/personal" / name
        if file.suffix == ".py":
            run = subprocess.run([sys.executable, str(file), str(src)],
                                 text=True, capture_output=True, timeout=20)
            if run.returncode:
                raise ValueError("source_guard_failed:" + name + ":" + run.stderr)
            results.append({"entry": name, "guard_exit": 0})
        else:
            command = ["patch", "-p1", "--fuzz=0", "--batch", "--forward",
                       "--no-backup-if-mismatch", "-i", str(file)]
            for mode in (["--dry-run"], []):
                run = subprocess.run(command + mode, cwd=src, text=True,
                                     capture_output=True, timeout=20)
                if (run.returncode or "offset" in run.stdout.lower()
                        or "fuzz" in run.stdout.lower()):
                    raise ValueError("strict_patch_failed:" + name + ":" + run.stdout + run.stderr)
            results.append({"entry": name, "dry_run_exit": 0, "apply_exit": 0,
                            "fuzz": 0, "offset": 0})
    return results
