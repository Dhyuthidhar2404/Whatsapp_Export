"""Static safety gate — the pre-push / CI guard for the core invariants.

Statically asserts, over ``wae/`` and ``export.py``:

1. **No network anywhere** — no import of a networking module.
2. **The key is never logged/printed** — ``key`` is never a direct argument to
   ``print`` or a logging call (a redacted wrapper like ``_redacted(cmd, key)``
   is allowed, since the key itself does not reach the sink).
3. **`.gitignore` is complete** — every required secret/output pattern is present.

Run directly (``python scripts/safety_gate.py``); exits non-zero on any
violation. The check functions are importable for unit testing.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Networking modules that must never be imported by the tool.
FORBIDDEN_MODULES = {
    "socket", "ssl", "http", "urllib", "urllib2", "httplib", "requests",
    "aiohttp", "httpx", "ftplib", "telnetlib", "smtplib", "poplib", "imaplib",
    "xmlrpc", "websocket", "websockets", "asyncio",
}

#: Logger method names that emit records.
_LOGGING_METHODS = {"debug", "info", "warning", "error", "critical", "exception", "log"}

#: Variable names that hold the secret key.
_KEY_NAMES = {"key"}

#: Patterns that must appear in .gitignore from the first commit.
REQUIRED_GITIGNORE = [
    "key", "*.key", "key.txt", "*.crypt12", "*.crypt14", "*.crypt15",
    "msgstore.db", "wa.db", "*.vcf", "/output/", "/.tmp/", "*.zip", ".env",
]


def network_violations(name: str, source: str) -> list[str]:
    """Return network-import violations found in ``source``."""
    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                    out.append(f"{name}:{node.lineno}: forbidden import '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in FORBIDDEN_MODULES:
                out.append(f"{name}:{node.lineno}: forbidden import from '{node.module}'")
    return out


def _is_log_or_print(func: ast.AST) -> bool:
    if isinstance(func, ast.Name) and func.id == "print":
        return True
    if isinstance(func, ast.Attribute) and func.attr in _LOGGING_METHODS:
        value = func.value
        if isinstance(value, ast.Name) and value.id in {"log", "logger", "logging"}:
            return True
        if isinstance(value, ast.Attribute) and value.attr in {"log", "logger", "logging"}:
            return True
    return False


def _arg_is_key(arg: ast.AST) -> bool:
    """True if ``arg`` passes the key *directly* (bare name or ``f"{key}"``)."""
    if isinstance(arg, ast.Name) and arg.id in _KEY_NAMES:
        return True
    if isinstance(arg, ast.JoinedStr):
        for value in arg.values:
            if (
                isinstance(value, ast.FormattedValue)
                and isinstance(value.value, ast.Name)
                and value.value.id in _KEY_NAMES
            ):
                return True
    return False


def key_logging_violations(name: str, source: str) -> list[str]:
    """Return places where the key is passed directly to print/logging."""
    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and _is_log_or_print(node.func):
            args = list(node.args) + [kw.value for kw in node.keywords]
            if any(_arg_is_key(a) for a in args):
                out.append(f"{name}:{node.lineno}: key passed to log/print")
    return out


def gitignore_violations(text: str) -> list[str]:
    """Return required .gitignore patterns that are missing."""
    present = {line.strip() for line in text.splitlines()}
    return [
        f".gitignore: missing required entry '{pat}'"
        for pat in REQUIRED_GITIGNORE
        if pat not in present
    ]


def _scanned_paths(root: Path) -> list[Path]:
    paths = [root / "export.py", *sorted((root / "wae").rglob("*.py"))]
    return [p for p in paths if p.exists()]


def run(root: Path = REPO_ROOT) -> list[str]:
    """Run every check against the repo and return all violations."""
    violations: list[str] = []
    for path in _scanned_paths(root):
        source = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(root))
        violations += network_violations(rel, source)
        violations += key_logging_violations(rel, source)
    violations += gitignore_violations((root / ".gitignore").read_text(encoding="utf-8"))
    return violations


def main() -> int:
    violations = run()
    if violations:
        print("Safety gate FAILED:")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("Safety gate passed: no network imports, no key logging, .gitignore complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
