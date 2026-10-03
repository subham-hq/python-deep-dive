#!/usr/bin/env python3
"""Regenerate the auto-managed Projects index in the root README.

Scans top-level project folders and rebuilds ONLY the block between
<!-- PROJECTS:START --> and <!-- PROJECTS:END -->. Everything outside those
markers is left untouched — that prose is yours.

Each project's title and one-line blurb are pulled from that project's OWN
README.md (its first '# ' heading and its first real line of text), so the
description lives with the project and you control it. Add a folder + a README,
push, and this index updates itself. Folders without a README.md are skipped.
HTML comments (such as TODO notes) and fenced code blocks are ignored when
picking the title and blurb.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
START, END = "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->"
IGNORE = {
    ".git",
    ".github",
    "scripts",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
}
HTML_COMMENT = re.compile(r"<!--.*?-->", flags=re.DOTALL)
CODE_FENCE = re.compile(r"^\s*```.*?^\s*```[^\n]*$", flags=re.DOTALL | re.MULTILINE)


def project_dirs() -> list[Path]:
    return sorted(
        p
        for p in ROOT.iterdir()
        if p.is_dir()
        and not p.name.startswith(".")
        and p.name not in IGNORE
        and (p / "README.md").is_file()
    )


def title_and_blurb(folder: Path) -> tuple[str, str]:
    """(title, one-line blurb) taken from the folder's own README.md."""
    title, blurb = folder.name, ""
    readme = folder / "README.md"
    if readme.exists():
        # Strip comments and code blocks first, so a line inside one can never
        # become the title or the blurb.
        text = HTML_COMMENT.sub("", readme.read_text(encoding="utf-8"))
        text = CODE_FENCE.sub("", text)
        if m := re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE):
            title = m.group(1).strip()
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith(("#", "!", "<", "[!", ">", "-", "|", "`")):
                continue
            blurb = s
            break
    # A literal "|" would end the table cell early.
    return title.replace("|", "\\|"), blurb.replace("|", "\\|")


def build_table() -> str:
    rows = ["| Project | What it covers |", "| --- | --- |"]
    for folder in project_dirs():
        title, blurb = title_and_blurb(folder)
        link = f"[{title}](./{quote(folder.name)})"
        rows.append(
            f"| {link} | {blurb or '_add a one-line description to its README_'} |"
        )
    return "\n".join(rows)


def main() -> None:
    content = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), flags=re.DOTALL)
    if not pattern.search(content):
        raise SystemExit(f"Markers not found. Add {START} and {END} to README.md.")
    block = f"{START}\n\n{build_table()}\n\n{END}"
    new = pattern.sub(lambda _: block, content)
    if new != content:
        README.write_text(new, encoding="utf-8")
        print("README project index updated.")
    else:
        print("README already up to date.")


if __name__ == "__main__":
    main()
