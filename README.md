# Repo Séance

Summon the ghosts of your git repo. Repo Séance reads your history for deleted files, stale branches, abandoned TODOs and regrettable commit messages, then has a **local open-weight model** narrate each one. Everything runs on your machine through [Ollama](https://ollama.com): no API key, no network, and your code never leaves the laptop.

```
  †  THE SEANCE BEGINS  †
  repo: haunted

  † feature/auth-v2
    branch · 21 months dead · last seen with Ana Rivera
    ...
```

## Modes

| Mode | What you get |
|------|--------------|
| `haunt` (default) | Eerie whispers about dead files, branches, TODOs and commits |
| `ofrenda` | Warm Día de los Muertos remembrances; add `--author "name"` to honor one person's work |
| `exorcise` | `VERDICT: DELETE / KEEP / INVESTIGATE` for stale branches and old TODOs |

## Run it

```bash
ollama pull llama3.2:3b          # or qwen2.5:3b, gemma2:2b, anything you like
python -m seance /path/to/repo   # no install needed; stdlib only
python -m seance . -m ofrenda --author ana --slow
python -m seance . -m exorcise --stale-days 90
SEANCE_MODEL=qwen2.5:7b python -m seance .   # swap models freely
```

No Ollama running? It falls back to canned whispers (`--no-llm` forces that), so the tool never just breaks.

Try it on a deliberately haunted sample repo:

```bash
python -m seance.demo /tmp/haunted && python -m seance /tmp/haunted
```

Install as a command with `pip install -e .`, then just `seance`.

## How it works

`git log / for-each-ref / grep / blame` → `Ghost` records → prompt per mode → Ollama (`/api/generate`) → terminal renderer. The model only ever gets the facts git reported (name, age, author, last words), and the prompts forbid inventing details.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Why open

- Works with the Wi-Fi off, and private repos never touch a third-party server.
- Swap models with one flag and the ghost's voice changes.
- Zero per-commit API cost.
