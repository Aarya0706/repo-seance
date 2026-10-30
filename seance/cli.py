from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__, render
from .gitscan import GitError, interleave, summon
from .llm import DEFAULT_MODEL, Medium
from .prompts import SYSTEM, canned, facts, retry_prompt, user_prompt
from .verify import check

KINDS = {
    "haunt": ["file", "branch", "todo", "commit"],
    "ofrenda": ["file", "branch", "todo", "commit"],
    "exorcise": ["branch", "todo"],  # only things you can actually delete
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="seance", description="Summon the ghosts of your git repo.")
    p.add_argument("path", nargs="?", default=".", help="path to a git repo (default: .)")
    p.add_argument("-m", "--mode", choices=list(KINDS), default="haunt",
                   help="haunt = eerie, ofrenda = loving remembrance, exorcise = what to delete")
    p.add_argument("-n", "--limit", type=int, default=6, help="how many spirits to summon")
    p.add_argument("--stale-days", type=int, default=180, help="branches older than this are ghosts")
    p.add_argument("--author", default="", help="only spirits last touched by this author (substring)")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model (env SEANCE_MODEL)")
    p.add_argument("--host", default=None, help="Ollama host (env OLLAMA_HOST)")
    p.add_argument("--no-llm", action="store_true", help="skip the model; use canned whispers")
    p.add_argument("--verify", action="store_true",
                   help="reject whispers that contradict git; regenerate, then fall back to canned")
    p.add_argument("--retries", type=int, default=2, help="regeneration attempts with --verify")
    p.add_argument("--warmup", action="store_true", help="load the model before timing starts")
    p.add_argument("--stats-json", metavar="FILE", help="write per-ghost timings and checks as JSON")
    p.add_argument("--slow", action="store_true", help="typewriter effect (adds delay; don't benchmark with it)")
    p.add_argument("--version", action="version", version=f"seance {__version__}")
    return p


def narrate(args, medium, g, authors):
    """Return (text, flags, record) for one ghost."""
    rec = {"kind": g.kind, "name": g.name, "source": "canned", "attempts": 0,
           "first_try_problems": [], "final_problems": [], "fell_back": False, "seconds": 0.0}
    if medium is None:
        return canned(args.mode, g), [], rec

    facts_text = facts(g)
    prompt, text, probs = user_prompt(g), None, []
    max_attempts = 1 + (max(args.retries, 0) if args.verify else 0)
    t0 = time.time()
    try:
        for attempt in range(1, max_attempts + 1):
            text = medium.channel(SYSTEM[args.mode], prompt,
                                  temperature=0.9 if attempt == 1 else 0.4)
            probs = check(text, g, facts_text, args.mode, authors)
            rec["attempts"] = attempt
            if attempt == 1:
                rec["first_try_problems"] = list(probs)
            if not probs or not args.verify:
                break
            prompt = retry_prompt(g, probs)
    except Exception as exc:  # a model hiccup should never kill the seance
        rec["error"] = str(exc)
        text = None
    rec["seconds"] = round(time.time() - t0, 2)

    if not text or not text.strip():
        return canned(args.mode, g), [f"the spirit would not speak ({rec.get('error', 'empty reply')}); canned whisper"], rec
    if args.verify and probs:
        rec["fell_back"] = True
        return (canned(args.mode, g),
                [f"grounded fallback: model contradicted git on all {rec['attempts']} attempts"], rec)

    rec["source"], rec["text"], rec["final_problems"] = "model", text, probs
    flags = [f"unverified: {p}" for p in probs]
    if rec["attempts"] > 1:
        flags.append(f"regenerated {rec['attempts'] - 1}x after contradicting git")
    return text, flags, rec


def summarize(recs):
    model = [r for r in recs if r["source"] == "model" or r.get("fell_back")]
    n = len(model)
    return {
        "ghosts": len(recs),
        "model_ghosts": n,
        "first_try_flagged": sum(1 for r in model if r["first_try_problems"]),
        "regenerated": sum(1 for r in model if r["source"] == "model" and r["attempts"] > 1 and not r["final_problems"]),
        "fell_back": sum(1 for r in model if r.get("fell_back")),
        "final_flagged": sum(1 for r in model if r["final_problems"]),
        "avg_seconds_per_ghost": round(sum(r["seconds"] for r in model) / n, 2) if n else None,
    }


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.path).resolve()
    try:
        by_kind = summon(repo, args.stale_days, max(args.limit, 8))
    except (GitError, FileNotFoundError) as exc:
        render.note(f"The veil will not part: {exc}")
        return 2

    ghosts = interleave(by_kind, KINDS[args.mode], args.limit, args.author)
    if not ghosts:
        render.note("Silence. No restless spirits here (try --stale-days 30 or drop --author).")
        return 0
    authors = {g.author for gs in by_kind.values() for g in gs}

    medium, channel = None, "candles only (no model, canned whispers)"
    if not args.no_llm:
        m = Medium(args.model, args.host)
        ready, msg = m.check()
        if ready:
            medium, channel = m, msg + " (local)"
            if args.warmup:
                try:
                    m.channel("Reply with one word.", "Say OK.", max_tokens=2)
                except Exception as exc:
                    render.note(f"Warm-up failed: {exc}")
        else:
            render.note(f"Falling back to canned whispers: {msg}")
    if args.verify and medium is None:
        render.note("--verify has no effect without a model.")

    render.banner(args.mode, repo.name, args.author)
    start, recs = time.time(), []
    for g in ghosts:
        text, flags, rec = narrate(args, medium, g, authors)
        recs.append(rec)
        render.ghost(args.mode, g, text, args.slow, flags)

    lines = []
    if medium:
        s = summarize(recs)
        lines.append(f"avg {s['avg_seconds_per_ghost']}s per spirit \u00b7 contradicted git on first try: "
                     f"{s['first_try_flagged']}/{s['model_ghosts']}")
        if args.verify:
            lines.append(f"verify: {s['regenerated']} regenerated, {s['fell_back']} fell back to canned, "
                         f"{s['final_flagged']} still flagged")
    render.footer(args.mode, channel, len(ghosts), time.time() - start, lines)

    if args.stats_json:
        Path(args.stats_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.stats_json).write_text(json.dumps({
            "repo": repo.name, "mode": args.mode, "model": args.model if medium else None,
            "verify": args.verify, "summary": summarize(recs), "ghosts": recs,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
