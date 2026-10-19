"""Releases the [Unreleased] section of a Keep a Changelog file, or reads a released section.

Usage: release_changelog.py release <changelog> <version> <tag> <date> <notes-file>
       release_changelog.py notes <changelog> <version> <notes-file>

release: `## [Unreleased]` becomes `## [<version>] - <date>` below a new, empty `## [Unreleased]`.
When the file has an `[Unreleased]: .../compare/<previous>...HEAD` link, it is moved to the new
tag and a `[<version>]` link is added. The content of the released section is written to
<notes-file>. Fails when the file or the section is missing, the section is empty, or the
version already has a section.

notes: writes the content of the `## [<version>]` section to <notes-file>. Fails when the file or
the section is missing, or the section is empty.
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


def read_lines(changelog: str) -> list[str]:
    path = Path(changelog)
    if not path.is_file():
        fail(f"No changelog found at '{changelog}'")
    return path.read_text(encoding="utf-8").splitlines()


def section_end(lines: list[str], start: int) -> int:
    return next(
        (i for i in range(start + 1, len(lines)) if SECTION.match(lines[i]) or LINK.match(lines[i])),
        len(lines),
    )


def notes(changelog: str, version: str, notes_file: str) -> None:
    lines = read_lines(changelog)
    heading = re.compile(rf"^## \[{re.escape(version)}\]")
    start = next((i for i, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        fail(f"{changelog} has no section for {version}")

    content = "\n".join(lines[start + 1 : section_end(lines, start)]).strip("\n")
    if not content.strip():
        fail(f"The section for {version} in {changelog} is empty")

    Path(notes_file).write_text(content + "\n", encoding="utf-8")


def release(changelog: str, version: str, tag: str, date: str, notes_file: str) -> None:
    path = Path(changelog)
    lines = read_lines(changelog)

    if any(re.match(rf"^## \[{re.escape(version)}\]", line) for line in lines):
        fail(f"{changelog} already has a section for {version}")

    start = next((i for i, line in enumerate(lines) if UNRELEASED.match(line)), None)
    if start is None:
        fail(f"{changelog} has no '## [Unreleased]' section")

    released = "\n".join(lines[start + 1 : section_end(lines, start)]).strip("\n")
    if not released.strip():
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
    Path(notes_file).write_text(released + "\n", encoding="utf-8")


USAGE = (
    "Usage: release_changelog.py release <changelog> <version> <tag> <date> <notes-file> | "
    "notes <changelog> <version> <notes-file>"
)

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 6 and args[0] == "release":
        release(*args[1:])
    elif len(args) == 4 and args[0] == "notes":
        notes(*args[1:])
    else:
        fail(USAGE)
