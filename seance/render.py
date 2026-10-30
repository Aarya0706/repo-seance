"""Terminal rendering: candles, tombstones and a slow typewriter."""
from __future__ import annotations

import os
import re
import sys
import textwrap
import time

from .gitscan import Ghost
from .prompts import years

if os.name == "nt":
    os.system("")  # enables ANSI escape codes in Windows terminals
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


PALETTE = {
    "haunt": ("35", "90"),     # purple, dim grey
    "ofrenda": ("33", "38;5;208"),  # marigold, orange
    "exorcise": ("31", "90"),  # red, dim grey
}
ICON = {"haunt": "\u2020", "ofrenda": "\u273f", "exorcise": "\u2620"}
TITLE = {
    "haunt": "THE SEANCE BEGINS",
    "ofrenda": "OFRENDA",
    "exorcise": "THE EXORCISM",
}


def typewriter(text: str, slow: bool) -> None:
    if not slow or not sys.stdout.isatty():
        print(text)
        return
    # Write whole words with their trailing whitespace in one go: lone spaces
    # written one at a time can get dropped by some Windows consoles.
    for chunk in re.findall(r"\S+\s*|\s+", text):
        sys.stdout.write(chunk)
        sys.stdout.flush()
        word = chunk.rstrip()
        time.sleep(0.02 * max(len(word), 1) + (0.15 if word[-1:] in ".,;:" else 0))
    print()


def banner(mode: str, repo_name: str, who: str = "") -> None:
    main, dim = PALETTE[mode]
    title = TITLE[mode] + (f" for {who}" if who else "")
    print()
    print(c(main, f"  {ICON[mode]}  {title}  {ICON[mode]}"))
    print(c(dim, f"  repo: {repo_name}"))
    print()


def ghost(mode: str, g: Ghost, text: str, slow: bool = False, flags=()) -> None:
    main, dim = PALETTE[mode]
    print(c(main, f"  {ICON[mode]} {g.name}"))
    print(c(dim, f"    {g.kind} \u00b7 {years(g.age_days)} dead \u00b7 last seen with {g.author}"))
    body = textwrap.fill(text, width=76, initial_indent="    ", subsequent_indent="    ")
    typewriter(body, slow)
    for f in flags:
        print(c("33", f"    ! {f}"))
    print()


def footer(mode: str, channel: str, count: int, seconds: float, lines=()) -> None:
    _, dim = PALETTE[mode]
    print(c(dim, f"  {count} spirit{'' if count == 1 else 's'} consulted in {seconds:.1f}s \u00b7 channel: {channel}"))
    for line in lines:
        print(c(dim, f"  {line}"))
    print()


def note(msg: str) -> None:
    print(c("90", f"  {msg}"), file=sys.stderr)
