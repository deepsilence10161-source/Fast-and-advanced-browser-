"""Host guard for a real Android compile failure (run 43862245579): patch-added Java used
PostTask/TaskTraits without imports. Heuristic only; NOT an Android compile PASS."""
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/personal_browser"))
import source_fixture as F  # noqa: E402

JAVA_LANG = {'String', 'Object', 'Integer', 'Long', 'Boolean', 'Math', 'System', 'Runnable', 'Exception',
             'Override', 'Throwable', 'Class', 'Thread', 'Double', 'Float', 'Character', 'StringBuilder',
             'IllegalArgumentException', 'IllegalStateException', 'RuntimeException', 'SuppressWarnings',
             'Deprecated', 'Void', 'Number', 'Byte', 'Short', 'CharSequence', 'Iterable', 'Comparable',
             'AutoCloseable', 'Error', 'NullPointerException', 'SecurityException', 'FunctionalInterface',
             'SafeVarargs', 'Process', 'Enum', 'InterruptedException', 'AssertionError',
             'UnsupportedOperationException', 'IndexOutOfBoundsException'}
# New same-package classes created by the personal patches (no import needed).
SAME_PACKAGE_NEW = {'BrowserContainedAccountManagerFacade', 'BrowserContainedClipboard', 'FaceGuardLockState'}


def idents(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'//[^\n]*', '', text)
    text = re.sub(r'"(\\.|[^"\\])*"', '""', text)
    imported = set(re.findall(r'^import (?:static )?[\w.]*?\.(\w+);', text, re.M))
    declared = set(re.findall(r'\b(?:class|interface|enum|record|@interface)\s+(\w+)', text))
    generics = set(re.findall(r'\b([A-Z])\b', text))
    used = set(re.findall(r'(?<![\w.])([A-Z][A-Za-z0-9]*)(?=\s*[.(<\[]|\s+\w+\s*[=;,)])', text))
    return {u for u in used if u not in imported | declared | JAVA_LANG | generics and not u.isupper()}


def test_patch_added_java_symbols_are_imported_or_qualified():
    sources = F.load_sources()
    root = Path(tempfile.mkdtemp())
    for name, text in sources.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    F.apply_strict(root)
    problems = {}
    for name, before in sources.items():
        if name.endswith('.java'):
            new = idents((root / name).read_text()) - idents(before) - SAME_PACKAGE_NEW
            if new:
                problems[name] = sorted(new)
    assert not problems, problems
