"""Grounding check: does the model's prose agree with what git actually reported?

Deliberately strict and cheap (regexes, no second model). It catches the failure modes
small models actually show: invented hashes, dates and durations, wrong merge status,
and the wrong person. It cannot prove prose is true, only that it contradicts or goes
beyond the facts we handed over.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Set, Tuple

from .gitscan import Ghost

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
WORDNUM = {w: i + 1 for i, w in enumerate(
    "one two three four five six seven eight nine ten eleven twelve".split())}
_UNIT = r"(day|week|month|year)s?"
_NUM_UNIT = re.compile(r"\b(\d+(?:\.\d+)?)\s*-?\s*" + _UNIT + r"\b", re.I)
_WORD_UNIT = re.compile(r"\b(" + "|".join(WORDNUM) + r")\s*-?\s*" + _UNIT + r"\b", re.I)
_HASH = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_MONTH = re.compile(r"\b(" + "|".join(m for m in MONTHS if m != "May") + r")\b")
_MAY = re.compile(r"\bMay\s+\d|\b(?:in|of|on|since|during|last|next|early|late)\s+May\b")  # not the verb
_ISO = re.compile(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b")
_NUM = re.compile(r"(?<![\w/.-])\d+(?:\.\d+)?(?![\w/-])")
_LONGTOKEN = re.compile(r"\b(?=\w*\d)\w{20,}\b")
_A_UNIT = re.compile(r"\b(?:a|an)\s+" + _UNIT + r"\b", re.I)
_VERDICT = re.compile(r"\s*VERDICT:\s*(DELETE|KEEP|INVESTIGATE)\b")
_CLAIMS_MERGED = re.compile(
    r"(?<!never )(?<!not )\b(was merged|were merged|merged (?:in|into|to|back|with)|"
    r"successfully merged|merge succeeded)\b")
_CLAIMS_UNMERGED = re.compile(
    r"\b(never merged|unmerged|not (?:been )?merged|failed (?:to )?merge|merge (?:failed|conflict)|"
    r"merge attempt|conflict)")


def _quantities(text: str) -> Set[Tuple[str, str]]:
    found: Set[Tuple[str, str]] = set()
    for num, unit in _NUM_UNIT.findall(text):
        found.add((f"{float(num):g}", unit.lower()))
    for word, unit in _WORD_UNIT.findall(text):
        found.add((str(WORDNUM[word.lower()]), unit.lower()))
    for unit in re.findall(r"\b(?:a|an)\s+(day|week|month|year)s?\b", text, re.I):
        found.add(("1", unit.lower()))
    return found


def _nums(text: str) -> Set[str]:
    return {f"{float(n):g}" for n in re.findall(r"\d+(?:\.\d+)?", text)}


def check(text: str, g: Ghost, facts_text: str, mode: str = "haunt",
          authors: Iterable[str] = ()) -> List[str]:
    """Return a list of problems; empty means the text is consistent with the facts."""
    probs: List[str] = []
    low, flow = text.lower(), facts_text.lower()

    if mode == "exorcise" and not _VERDICT.match(text):
        probs.append("reply must start with 'VERDICT: DELETE', 'VERDICT: KEEP' or 'VERDICT: INVESTIGATE'")

    for num, unit in sorted(_quantities(text) - _quantities(facts_text)):
        probs.append(f"'{num} {unit}(s)' does not appear in the facts")
    for h in sorted(set(_HASH.findall(text))):
        if h not in flow and h[:7] not in flow:
            probs.append(f"hash '{h}' does not appear in the facts")
    for y in sorted(set(_YEAR.findall(text))):
        if y not in facts_text:
            probs.append(f"year {y} does not appear in the facts")
    months = set(_MONTH.findall(text)) | ({"May"} if _MAY.search(text) else set())
    for m in sorted(months):
        if m != g.died.strftime("%B") and m not in facts_text:
            probs.append(f"month '{m}' contradicts the date {g.died.strftime('%Y-%m-%d')}")

    fact_date = g.died.strftime("%Y-%m-%d")
    for d in sorted(set(_ISO.findall(text))):
        if d.replace("/", "-") != fact_date:
            probs.append(f"date {d} does not match the date in the facts ({fact_date})")

    # Bare numbers (counts, days of the month, digit soup) must come from the facts.
    allowed_nums, covered = _nums(facts_text), {n for n, _ in _quantities(text)}
    for raw in _NUM.findall(text):
        n = f"{float(raw):g}"
        if len(raw) == 4 and raw.startswith(("19", "20")):
            continue  # years are checked separately
        if n not in allowed_nums and n not in covered:
            probs.append(f"number {raw} does not appear in the facts")

    for tok in sorted(set(_LONGTOKEN.findall(text))):
        if tok not in facts_text:
            probs.append(f"gibberish token '{tok[:24]}...'")

    if "merg" in low and "merg" not in flow:
        probs.append("mentions merging, but the facts say nothing about merges")
    if g.kind == "branch":
        if "never merged" in g.detail and _CLAIMS_MERGED.search(low):
            probs.append("claims the branch was merged; the facts say it was NEVER merged")
        elif "never merged" not in g.detail and _CLAIMS_UNMERGED.search(low):
            probs.append("claims the merge failed or never happened; the facts say it WAS merged")

    mine = set(re.findall(r"\w+", g.author))
    fact_tokens = set(re.findall(r"\w+", facts_text))
    for other in authors:
        if other == g.author:
            continue
        for tok in re.findall(r"\w+", other):
            if (len(tok) >= 3 and tok not in mine and tok not in fact_tokens
                    and re.search(rf"\b{re.escape(tok)}\b", text)):
                probs.append(f"mentions '{tok}', who is not the person named in the facts")
    return list(dict.fromkeys(probs))
