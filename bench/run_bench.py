"""Benchmark models with verification off and on; print a markdown table.

    python bench/run_bench.py C:\\path\\to\\repo --models qwen2.5:3b llama3.2:3b --runs 3
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def one_run(repo, model, verify, mode, n):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "stats.json"
        cmd = [sys.executable, "-m", "seance", repo, "--model", model, "--mode", mode,
               "-n", str(n), "--warmup", "--stats-json", str(out)]
        if verify:
            cmd.append("--verify")
        subprocess.run(cmd, check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
        return json.loads(out.read_text(encoding="utf-8"))["summary"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("repo")
    p.add_argument("--models", nargs="+", default=["qwen2.5:3b", "llama3.2:3b"])
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--mode", default="haunt")
    p.add_argument("-n", type=int, default=6)
    a = p.parse_args()

    rows = []
    for model in a.models:
        for verify in (False, True):
            tot = {"ghosts": 0, "first": 0, "final": 0, "fell": 0, "secs": []}
            for _ in range(a.runs):
                s = one_run(a.repo, model, verify, a.mode, a.n)
                tot["ghosts"] += s["model_ghosts"]
                tot["first"] += s["first_try_flagged"]
                tot["final"] += s["final_flagged"]
                tot["fell"] += s["fell_back"]
                if s["avg_seconds_per_ghost"] is not None:
                    tot["secs"].append(s["avg_seconds_per_ghost"])
            avg = sum(tot["secs"]) / len(tot["secs"]) if tot["secs"] else float("nan")
            rows.append((model, "on" if verify else "off", tot["ghosts"], tot["first"],
                         tot["final"], tot["fell"], avg))

    print("| Model | Verify | Findings | Contradicted git (1st try) | Still contradicting (final) | Fell back to canned | Avg s/finding |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for m, v, n, f, fin, fell, avg in rows:
        print(f"| {m} | {v} | {n} | {f} ({f / n:.0%}) | {fin} ({fin / n:.0%}) | {fell} | {avg:.1f} |")


if __name__ == "__main__":
    main()
