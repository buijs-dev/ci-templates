"""Moves the [Unreleased] section of a Keep a Changelog file to a release section.

Usage: release_changelog.py <changelog> <version> <tag> <date> <notes-file>

`## [Unreleased]` becomes `## [<version>] - <date>` below a new, empty `## [Unreleased]`.
When the file has an `[Unreleased]: .../compare/<previous>...HEAD` link, it is moved to the new
tag and a `[<version>]` link is added. The content of the released section is written to
<notes-file>. Fails when the file or the section is missing, the section is empty, or the
version already has a section.
"""

import re
import sys
from pathlib import Path

UNRELEASED = re.compile(r"^## \[Unreleased\]\s*$", re.IGNORECASE)
SECTION = re.compile(r"^## ")
LINK = re.compile(r"^\[[^\]]+\]:\s")
UNRELEASED_LINK = re.compile(r"^\[Unreleased\]:\s*(\S+)/compare/(\S+)\.\.\.HEAD\s*$", re.IGNORECASE)


def fail(message: str) -> None:
    print(f"::error::{message}")
    sys.exit(1)


def main(changelog: str, version: str, tag: str, date: str, notes_file: str) -> None:
    path = Path(changelog)
    if not path.is_file():
        fail(f"No changelog found at '{changelog}'")

    lines = path.read_text(encoding="utf-8").splitlines()

    if any(re.match(rf"^## \[{re.escape(version)}\]", line) for line in lines):
        fail(f"{changelog} already has a section for {version}")

    start = next((i for i, line in enumerate(lines) if UNRELEASED.match(line)), None)
    if start is None:
        fail(f"{changelog} has no '## [Unreleased]' section")

    end = next(
        (i for i in range(start + 1, len(lines)) if SECTION.match(lines[i]) or LINK.match(lines[i])),
        len(lines),
    )
    notes = "\n".join(lines[start + 1 : end]).strip("\n")
    if not notes.strip():
        fail(f"The '## [Unreleased]' section of {changelog} is empty")

    lines[start : start + 1] = ["## [Unreleased]", "", f"## [{version}] - {date}"]

    for i, line in enumerate(lines):
        link = UNRELEASED_LINK.match(line)
        if link:
            base, previous = link.groups()
            lines[i : i + 1] = [
                f"[Unreleased]: {base}/compare/{tag}...HEAD",
                f"[{version}]: {base}/compare/{previous}...{tag}",
            ]
            break

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path(notes_file).write_text(notes + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        fail("Usage: release_changelog.py <changelog> <version> <tag> <date> <notes-file>")
    main(*sys.argv[1:])
