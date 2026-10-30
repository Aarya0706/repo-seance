"""Find the dead things in a git repository. Stdlib + the git binary only."""
from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence

SEP = "\x1f"
PROTECTED_BRANCHES = {"main", "master", "develop", "dev", "trunk", "origin"}


class GitError(RuntimeError):
    pass


@dataclass
class Ghost:
    kind: str  # "file" | "branch" | "todo" | "commit"
    name: str
    died: datetime
    author: str
    epitaph: str  # the last words: commit subject, TODO text, ...
    detail: str = ""

    @property
    def age_days(self) -> int:
        return max(0, (datetime.now(timezone.utc) - self.died).days)


def _git(repo: Path, *args: str, ok: Sequence[int] = (0,)) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode not in ok:
        raise GitError(r.stderr.strip() or f"git {args[0]} failed")
    return r.stdout


def _ts(value: str) -> datetime:
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def check_repo(repo: Path) -> None:
    try:
        _git(repo, "rev-parse", "--git-dir")
    except (GitError, FileNotFoundError) as exc:
        raise GitError(f"{repo} is not a git repository (or git is not installed): {exc}")


def find_deleted_files(repo: Path, limit: int = 8) -> List[Ghost]:
    out = _git(repo, "log", "--diff-filter=D", "--name-only", "--no-renames",
               f"--pretty=format:@@{SEP}%H{SEP}%an{SEP}%at{SEP}%s")
    alive = set(_git(repo, "ls-files").splitlines())
    ghosts: List[Ghost] = []
    seen = set()
    cur = None
    for line in out.splitlines():
        if line.startswith("@@" + SEP):
            _, sha, author, at, subject = line.split(SEP, 4)
            cur = (sha, author, _ts(at), subject)
        elif line.strip() and cur and line not in seen and line not in alive:
            seen.add(line)
            sha, author, died, subject = cur
            ghosts.append(Ghost("file", line, died, author, subject,
                                f"deleted in {sha[:7]}"))
    ghosts = ghosts[: max(limit * 3, limit)]
    for g in ghosts:  # how long did it live?
        born = _git(repo, "log", "--diff-filter=A", "--format=%at", "--", g.name).split()
        if born:
            lived = (g.died - _ts(born[-1])).days
            g.detail += f", lived {max(lived, 0)} days"
    return ghosts


def find_stale_branches(repo: Path, stale_days: int = 180) -> List[Ghost]:
    fmt = SEP.join(["%(refname:short)", "%(committerdate:unix)", "%(authorname)", "%(subject)"])
    refs = ("refs/heads", "refs/remotes")
    out = _git(repo, "for-each-ref", f"--format={fmt}", *refs)
    unmerged = set(_git(repo, "for-each-ref", "--no-merged", "HEAD",
                        "--format=%(refname:short)", *refs).split())
    now = time.time()
    ghosts: List[Ghost] = []
    for line in out.splitlines():
        name, at, author, subject = line.split(SEP, 3)
        short = name.split("/", 1)[-1] if name.startswith("origin/") else name
        if name.endswith("/HEAD") or short in PROTECTED_BRANCHES or name in PROTECTED_BRANCHES:
            continue
        if (now - int(at)) / 86400 < stale_days:
            continue
        detail = "never merged" if name in unmerged else "merged, but never laid to rest"
        ghosts.append(Ghost("branch", name, _ts(at), author, subject, detail))
    return sorted(ghosts, key=lambda g: g.died)


_TODO_RE = r"\b(TODO|FIXME|HACK|XXX)\b"


def find_todos(repo: Path, limit: int = 8) -> List[Ghost]:
    out = _git(repo, "grep", "-n", "-I", "-E", _TODO_RE, ok=(0, 1))
    ghosts: List[Ghost] = []
    for line in out.splitlines()[:80]:
        parts = line.split(":", 2)
        if len(parts) < 3 or parts[0].startswith("seance/") and "TODO|FIXME" in parts[2]:
            continue
        path, lineno, text = parts
        try:
            blame = _git(repo, "blame", "-L", f"{lineno},{lineno}", "--porcelain", "--", path)
        except GitError:
            continue
        author, at = "unknown", None
        for b in blame.splitlines():
            if b.startswith("author "):
                author = b[7:]
            elif b.startswith("author-time "):
                at = _ts(b[12:])
        if at is None:
            continue
        ghosts.append(Ghost("todo", f"{path}:{lineno}", at, author, text.strip()[:120],
                            "a promise never kept"))
    return sorted(ghosts, key=lambda g: g.died)[:limit]


_STRONG = re.compile(r"\b(wip|fix later|please work|asdf+|idk|oops|hopefully|works now)\b", re.I)
_WEAK = re.compile(r"^(temp|tmp|hack|stuff|misc|test(ing)?|final\d*|final_final|update|fix|changes|more)\W*$", re.I)


def find_regrettable_commits(repo: Path, limit: int = 8) -> List[Ghost]:
    out = _git(repo, "log", "--no-merges", f"--pretty=format:%h{SEP}%an{SEP}%at{SEP}%s")
    ghosts: List[Ghost] = []
    for line in out.splitlines():
        sha, author, at, subject = line.split(SEP, 3)
        s = subject.strip()
        if _STRONG.search(s) or (len(s.split()) <= 3 and _WEAK.match(s)) or len(s) <= 2:
            ghosts.append(Ghost("commit", sha, _ts(at), author, s, "a commit message that haunts the log"))
    return sorted(ghosts, key=lambda g: g.died)[:limit]


def summon(repo: Path, stale_days: int = 180, limit: int = 8) -> Dict[str, List[Ghost]]:
    check_repo(repo)
    return {
        "file": find_deleted_files(repo, limit),
        "branch": find_stale_branches(repo, stale_days),
        "todo": find_todos(repo, limit),
        "commit": find_regrettable_commits(repo, limit),
    }


def interleave(by_kind: Dict[str, List[Ghost]], kinds: Sequence[str], limit: int,
               author: str = "") -> List[Ghost]:
    """Round-robin across kinds, oldest ghosts first, so the seance has variety."""
    pools = []
    for k in kinds:
        items = by_kind.get(k, [])
        if author:
            items = [g for g in items if author.lower() in g.author.lower()]
        pools.append(sorted(items, key=lambda g: g.died))
    picked: List[Ghost] = []
    while len(picked) < limit and any(pools):
        for p in pools:
            if p and len(picked) < limit:
                picked.append(p.pop(0))
    return picked
