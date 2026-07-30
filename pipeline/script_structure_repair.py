from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class HeadingMatch:
    start: int
    end: int
    line: str
    episode: int


HEADING_PATTERN = re.compile(
    r"(?m)^\s*(?:#{1,4}\s*[^\n#]{0,30}?(?:【)?第\s*([一二三四五六七八九十百千万\d]+)\s*集[^\n]*|(?:【)?第?\s*([一二三四五六七八九十百千万\d]+)\s*集\s*[:：][^\n]*)$"
)


def repair_episode_numbering(script: str, expected_episode_count: int) -> str:
    headings = _script_headings(script)
    if not headings:
        return script
    counter = Counter(heading.episode for heading in headings)
    duplicates = [episode for episode, count in counter.items() if count > 1]
    missing = [episode for episode in range(1, expected_episode_count + 1) if episode not in counter]
    if len(duplicates) != 1 or len(missing) != 1:
        return script

    duplicate_episode = duplicates[0]
    missing_episode = missing[0]
    duplicate_indexes = [
        index for index, heading in enumerate(headings) if heading.episode == duplicate_episode
    ]
    if len(duplicate_indexes) != 2 or missing_episode <= duplicate_episode:
        return script

    start_index = duplicate_indexes[1]
    affected = headings[start_index:]
    expected_numbers = list(range(duplicate_episode + 1, duplicate_episode + 1 + len(affected)))
    if expected_numbers[-1] != missing_episode:
        return script

    repaired = script
    for heading, new_episode in reversed(list(zip(affected, expected_numbers))):
        repaired_line = _replace_episode_number(heading.line, new_episode)
        repaired = repaired[: heading.start] + repaired_line + repaired[heading.end :]
    return repaired


def _script_headings(script: str) -> list[HeadingMatch]:
    return [
        HeadingMatch(
            start=match.start(),
            end=match.end(),
            line=match.group(0),
            episode=_episode_number(match.group(1) or match.group(2)),
        )
        for match in HEADING_PATTERN.finditer(script)
        if _is_script_episode_heading(match.group(0))
    ]


def _is_script_episode_heading(line: str) -> bool:
    heading = line.strip().strip("#").strip()
    excluded_terms = ("大纲", "总表", "规划", "列表", "Checklist", "checklist")
    return not any(term in heading for term in excluded_terms)


def _replace_episode_number(line: str, episode: int) -> str:
    return re.sub(
        r"(第?\s*)([一二三四五六七八九十百千万\d]+)(\s*集)",
        rf"\g<1>{episode}\g<3>",
        line,
        count=1,
    )


def _episode_number(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + digits.get(value[-1], 0)
    if value.endswith("十"):
        return digits.get(value[0], 0) * 10
    if "十" in value:
        left, right = value.split("十", 1)
        return digits.get(left, 1) * 10 + digits.get(right, 0)
    return digits.get(value, 0)
