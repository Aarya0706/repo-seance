# Repo Séance

Summon the ghosts of your git repo. Repo Séance reads your history for **deleted files, stale branches, abandoned TODOs and regrettable commit messages**, then has a **local open-weight model** narrate each one. Everything runs on your machine through [Ollama](https://ollama.com): no API key, no network, and your code never leaves the laptop. Pure Python standard library, no dependencies.

```
  †  THE SEANCE BEGINS  †
  repo: haunted

  † feature/auth-v2
    branch · 21 months dead · last seen with Ana Rivera
    feature/auth-v2 has not breathed in 21 months. Ana Rivera left it with
    the words "start oauth rewrite", and it is still waiting, never merged.
```

Built for the DEV "Ghost in the Machine" challenge. Benchmark data and raw model outputs live in a separate repo: [seance-local-llm-benchmark](https://github.com/Aarya0706/seance-local-llm-benchmark).

## Modes

| Mode | What you get |
|------|--------------|
| `haunt` (default) | Eerie whispers with dry humor about dead files, branches, TODOs and commits |
| `ofrenda` | Warm Día de los Muertos remembrances; add `--author "name"` to honor one person's work |
| `exorcise` | `VERDICT: DELETE / KEEP / INVESTIGATE` for stale branches and old TODOs |

## Quick start

Requires Python 3.9+, git, and [Ollama](https://ollama.com).

```bash
ollama pull llama3.2:3b          # or qwen2.5:3b, llama3.2:1b, anything you like
python -m seance /path/to/repo   # must be a git repo with history
```

Windows: `winget install Ollama.Ollama`, then open a **new** terminal so `ollama` is on your PATH.

Try it on a deliberately haunted sample repo first:

```bash
python -m seance.demo ./haunted
python -m seance ./haunted
```

More examples:

```bash
python -m seance . -m ofrenda --author ana     # tribute to one contributor
python -m seance . -m exorcise --stale-days 90 # what to clean up
python -m seance . --model qwen2.5:3b --slow   # swap models; typewriter effect
python -m seance . --no-llm                    # canned whispers, no model needed
```

PowerShell sets an environment variable like this: `$env:SEANCE_MODEL = "qwen2.5:3b"` (or just pass `--model`). Install as a command with `pip install -e .`, then run `seance`.

If Ollama isn't running or the model isn't pulled, Séance falls back to canned whispers instead of crashing.

## Options

| Flag | Meaning |
|------|---------|
| `-m, --mode` | `haunt`, `ofrenda` or `exorcise` |
| `-n, --limit` | how many spirits to summon (default 6) |
| `--stale-days` | branches older than this count as ghosts (default 180) |
| `--author` | only spirits last touched by this author (substring match) |
| `--model`, `--host` | Ollama model and host (env: `SEANCE_MODEL`, `OLLAMA_HOST`) |
| `--no-llm` | skip the model; use canned whispers |
| `--verify`, `--retries` | grounding check with regeneration (see below) |
| `--warmup` | load the model before timing starts |
| `--stats-json FILE` | write per-ghost timings and checks as JSON |
| `--slow` | typewriter effect (adds delay; don't benchmark with it) |

## Grounding check (`--verify`)

Small models invent details. Séance checks every whisper against the facts git actually reported and prints a yellow `!` line under anything that isn't supported. The check covers:

- durations (`21 months`, `a year`), bare numbers, dates, years and months
- commit hashes and over-long gibberish tokens
- merge status (a merged branch described as "failed to merge", and vice versa)
- mentions of people who aren't in the facts
- the `VERDICT:` format in `exorcise` mode

```bash
python -m seance ./haunted --model llama3.2:1b --verify
```

With `--verify`, a flagged whisper is regenerated up to `--retries` times (default 2, at lower temperature, told what it got wrong). If it still fails, that ghost falls back to a canned whisper, which is consistent with the facts by construction.

**What it can't do:** the check is regex-based and strict about *checkable* claims. It cannot tell whether vague prose is true ("a reminder of a promise not fulfilled"), and an invented number that happens to match a number in the facts will pass. Treat flagged rates as lower bounds.

## Benchmarking

```bash
python -m seance ./haunted --model qwen2.5:3b --warmup --stats-json results/out.json
python bench/run_bench.py ./haunted --models qwen2.5:3b llama3.2:1b --runs 2 -n 8
```

`--warmup` loads the model before timing so run 1 isn't penalised. `--stats-json` records seconds per ghost, attempts, and the problems found on the first try versus the final text. `bench/run_bench.py` runs each model with verification off and on and prints a markdown table (unsupported claims on the first try, still unsupported after `--verify`, fallbacks, seconds per finding). The first-try rate doesn't depend on `--verify`, so pool the on/off rows when comparing models.

## How it works

`git log / for-each-ref / grep / blame` → `Ghost` records → prompt per mode → Ollama (`/api/generate`) → grounding check → terminal renderer. The model only ever sees the facts git reported (name, date, age, author, last words, merge status), and the prompts forbid inventing details.

## Known limitations

- TODO scanning is text-based, so a TODO inside a string literal counts.
- Age figures are approximate (months = days // 30).
- Findings name real people from a repo's history. Use `ofrenda` mode when sharing output from repos that aren't yours.
- Small samples: model comparisons here are indicative, not a leaderboard.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Why open

- Works with the Wi-Fi off, and private repos never touch a third-party server.
- Swap models with one flag and the ghost's voice (and error rate) changes.
- Zero per-commit API cost, which made the benchmark possible.

## License

MIT. Add a `LICENSE` file to the repo root if you haven't yet.
