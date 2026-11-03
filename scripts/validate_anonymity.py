#!/usr/bin/env python3
"""Double-blind hygiene check. Scans the artifact for things that would break
anonymity: e-mail addresses, personal source-hosting URLs, absolute home paths,
and VCS metadata. Content-pattern based, so it carries no identifying strings
itself. Exits non-zero if anything is found.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".idea"}
TEXT_EXT = {".py", ".md", ".txt", ".csv", ".json", ".sh", ".cff", ".toml",
            ".cfg", ".ini", ".yaml", ".yml", ".html", ".url", ".mjs", ".cjs", ".js", ".ts"}
PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "code-host URL": re.compile(r"https?://(?:github|gitlab|bitbucket)\.com/[^\s\"')]+", re.I),
    "home path": re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/"),
}
# generic placeholders and well-known container/service homes that are fine
ALLOW = re.compile(r"(example\.com|acme\.example|@corp\b|noreply@|anon@example\.com|"
                   r"/(home|Users)/(node|app|appuser|user|ubuntu|runner|runneradmin|"
                   r"frappe|galaxy|odoo|dhis|mayan|elabftw|postgres|mysql)/)")


def main():
    hits = []
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in TEXT_EXT:
                continue
            p = os.path.join(dirpath, fn)
            try:
                text = open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for label, rx in PATTERNS.items():
                for m in rx.findall(text):
                    s = m if isinstance(m, str) else m[0]
                    if ALLOW.search(s):
                        continue
                    hits.append((os.path.relpath(p, ROOT), label, s))
    # VCS metadata
    for dirpath, dirs, files in os.walk(ROOT):
        if ".git" in dirs or any(f == ".DS_Store" for f in files):
            hits.append((os.path.relpath(dirpath, ROOT), "vcs/os metadata", ".git/.DS_Store"))
    if hits:
        print("ANONYMITY CHECK: FAIL")
        for rel, label, s in hits[:50]:
            print(f"  {label:16} {rel}: {s}")
        sys.exit(1)
    print("ANONYMITY CHECK: PASS (no emails, code-host URLs, home paths, or VCS metadata)")


if __name__ == "__main__":
    main()
