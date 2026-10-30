"""Prompts for each mode, plus canned whispers for when no model is available."""
from __future__ import annotations

import zlib

from .gitscan import Ghost

RULES = ("Use only the facts given; never invent names, dates or reasons. Copy figures (ages, "
         "dates, counts, hashes) exactly as written in the facts and never convert units. Do not "
         "mention merges unless the facts do, and do not mention anyone not named in the facts. "
         "No emojis, no markdown, no preamble, no quotation marks around your whole reply.")

SYSTEM = {
    "haunt": ("You are the restless spirit of a software repository, whispering about something "
              "that died in it. Write 2 or 3 short, eerie sentences with dry gallows humor. "
              "Mention the concrete details. " + RULES),
    "ofrenda": ("You are writing a short remembrance for an ofrenda, in the spirit of Dia de los "
                "Muertos: warm, grateful and gently funny. Write 2 or 3 sentences honoring the "
                "work and what it gave the project, not mourning it. Mention the concrete details. "
                + RULES),
    "exorcise": ("You are a pragmatic engineer performing an exorcism of dead code. Reply in exactly "
                 "this form: 'VERDICT: DELETE' or 'VERDICT: KEEP' or 'VERDICT: INVESTIGATE', then one "
                 "short sentence of reasoning. " + RULES),
}


def years(days: int) -> str:
    if days < 45:
        n, unit = str(days), "day"
    elif days < 730:
        n, unit = str(days // 30), "month"
    else:
        n, unit = f"{days / 365:.1f}", "year"
    return f"{n} {unit}{'' if n == '1' else 's'}"


def facts(g: Ghost) -> str:
    lines = [f"Kind: {g.kind}", f"Name: {g.name}",
             f"Date of last sign of life: {g.died.strftime('%Y-%m-%d')}",
             f"Age since last sign of life: {years(g.age_days)}",
             f"Last touched by: {g.author}", f"Last words: {g.epitaph}"]
    if g.kind == "branch":
        if "never merged" in g.detail:
            lines.append("Merge status: this branch was NEVER merged into the main branch.")
        else:
            lines.append("Merge status: this branch WAS merged into the main branch; it was just never deleted.")
    elif g.kind == "file":
        lines.append(f"History: {g.detail}")
    else:
        lines.append(f"Note: {g.detail}")
    return "\n".join(lines)


def user_prompt(g: Ghost) -> str:
    return "Here are the facts:\n" + facts(g)


def retry_prompt(g: Ghost, problems) -> str:
    bullets = "\n".join(f"- {p}" for p in problems)
    return (user_prompt(g) + "\n\nYour previous reply was rejected because it contradicted or went "
            "beyond the facts:\n" + bullets + "\nWrite a new reply using ONLY the facts above.")


_CANNED = {
    ("haunt", "file"): [
        "{name} was deleted {age} ago by {author}, with the words \"{epitaph}\". The imports still remember it. Some nights the build almost asks where it went.",
        "Something is missing from the tree. {name}, gone {age}, taken by {author} ({detail}). It does not rest quietly.",
    ],
    ("haunt", "branch"): [
        "{name} has not breathed in {age}. {author} left it with the words \"{epitaph}\", and it is still waiting, {detail}.",
        "Down in the refs, {name} stirs. {age} of silence since {author}'s last commit, and it is {detail}.",
    ],
    ("haunt", "todo"): [
        "{author} promised \"{epitaph}\" {age} ago at {name}. The comment is still there, and so is the debt.",
        "At {name} a promise hangs in the air: \"{epitaph}\". {age} unanswered. {author} has not returned.",
    ],
    ("haunt", "commit"): [
        "Commit {name} by {author} says only \"{epitaph}\". {age} later, nobody knows what it meant. The log keeps it anyway.",
        "{author} wrote \"{epitaph}\" and walked away. {age} on, commit {name} still whispers from the history.",
    ],
    ("ofrenda", "file"): [
        "Here we remember {name}, which served the project until {author} laid it to rest {age} ago (\"{epitaph}\"). Thank you for the work you did while you were here.",
        "For {name}: {detail}. Everything it taught the codebase lives on in what came after. May it rest well.",
    ],
    ("ofrenda", "branch"): [
        "We light a candle for {name}, last tended by {author} {age} ago. Whatever became of it, the work was real ({detail}). Gracias.",
    ],
    ("ofrenda", "todo"): [
        "{author} left a note at {name} {age} ago: \"{epitaph}\". It was an act of hope, and we honor it.",
    ],
    ("ofrenda", "commit"): [
        "Commit {name}, \"{epitaph}\", by {author}. Not every commit is poetry, but every one was somebody trying. We remember it with a smile.",
    ],
}


def canned(mode: str, g: Ghost) -> str:
    if mode == "exorcise":
        if g.kind == "branch":
            if "never merged" in g.detail:
                return f"VERDICT: INVESTIGATE. Unmerged for {years(g.age_days)}; check if {g.author}'s work was superseded before deleting."
            return f"VERDICT: DELETE. Already merged and untouched for {years(g.age_days)}."
        if g.age_days > 365:
            return f"VERDICT: DELETE. This note is {years(g.age_days)} old; do it now or admit it will never happen."
        return f"VERDICT: INVESTIGATE. {years(g.age_days)} old; ask {g.author} whether it still matters."
    options = _CANNED[(mode, g.kind)]
    pick = options[zlib.crc32(g.name.encode()) % len(options)]
    return pick.format(name=g.name, age=years(g.age_days), author=g.author,
                       epitaph=g.epitaph, detail=g.detail)
