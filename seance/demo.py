"""Build a deliberately haunted sample repo for demos, screenshots and tests.

    python -m seance.demo /tmp/haunted-repo
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ANA = ("Ana Rivera", "ana@example.com")
BEN = ("Ben Okafor", "ben@example.com")
CARA = ("Cara Lindqvist", "cara@example.com")


def _git(repo: Path, *args: str, days_ago=None, who=ANA) -> None:
    env = os.environ.copy()
    env.update(GIT_AUTHOR_NAME=who[0], GIT_AUTHOR_EMAIL=who[1],
               GIT_COMMITTER_NAME=who[0], GIT_COMMITTER_EMAIL=who[1])
    if days_ago is not None:
        when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", "-C", str(repo), *args], check=True, env=env,
                   capture_output=True, text=True)


def _commit(repo, days_ago, who, msg, write=None, remove=None):
    for rel, text in (write or {}).items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    for rel in remove or []:
        _git(repo, "rm", "-q", rel)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg, days_ago=days_ago, who=who)


def build_demo_repo(path) -> Path:
    repo = Path(path)
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit(repo, 900, ANA, "initial commit", {
        "README.md": "# Haunted Shop\n", "auth_v1.py": "def login(): ...\n",
        "legacy/cobol_bridge.py": "# talks to the mainframe\n"})
    _commit(repo, 800, BEN, "add payments", {
        "src/payments.py": "# TODO: handle refunds\n# FIXME: race condition here\n"})
    _commit(repo, 700, ANA, "wip", {"src/auth_v2.py": "def login_v2(): ...\n"})
    _git(repo, "checkout", "-q", "-b", "feature/auth-v2", days_ago=650, who=ANA)
    _commit(repo, 640, ANA, "start oauth rewrite", {"src/oauth.py": "# unfinished\n"})
    _git(repo, "checkout", "-q", "main")
    _commit(repo, 600, BEN, "fix later", {"src/payments.py": "# TODO: handle refunds\n# FIXME: race condition here\nTAX = 0.2\n"})
    _commit(repo, 500, CARA, "remove cobol bridge, nobody knows how it worked",
            remove=["legacy/cobol_bridge.py"])
    _commit(repo, 400, BEN, "asdf", {"notes.txt": "asdf\n"})
    _commit(repo, 300, CARA, "retire v1 auth", remove=["auth_v1.py"])
    _git(repo, "checkout", "-q", "-b", "hotfix/friday-deploy", days_ago=230, who=BEN)
    _commit(repo, 220, BEN, "friday deploy hotfix", {"hotfix.txt": "it was friday\n"})
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "hotfix/friday-deploy", "-m", "Merge hotfix",
         days_ago=200, who=BEN)
    _commit(repo, 100, CARA, "add dashboard", {"src/dash.py": "# HACK: hardcoded timezone\n"})
    _commit(repo, 10, ANA, "final2", {"CHANGELOG.md": "final\n"})
    return repo


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "haunted-repo"
    print(build_demo_repo(target))
