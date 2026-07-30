from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ScriptValidationResult:
    is_complete: bool
    issues: list[str]
    fragment_count: int
    episode_count: int
    expected_episode_count: int
    present_episodes: list[int]
    missing_episodes: list[int]
    duplicate_episodes: list[int]


def split_script_units(script: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"(?m)^\s*(?:#{1,4}\s*[^\n#]{0,30}?(?:【)?第\s*([一二三四五六七八九十百千万\d]+)\s*集[^\n]*|(?:【)?第?\s*([一二三四五六七八九十百千万\d]+)\s*集\s*[:：][^\n]*)$"
    )
    matches = [match for match in pattern.finditer(script) if _is_script_episode_heading(match.group(0))]
    units: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(script)
        episode = _episode_number(match.group(1) or match.group(2))
        if episode < 1:
            continue
        units.append(
            {
                "episode": episode,
                "title": match.group(0).strip("# 【】").strip(),
                "content": script[start:end].strip(),
            }
        )
    return units


def _is_script_episode_heading(line: str) -> bool:
    heading = line.strip().strip("#").strip()
    excluded_terms = ("大纲", "总表", "规划", "列表", "Checklist", "checklist")
    return not any(term in heading for term in excluded_terms)


def validate_script_completeness(project: Any) -> ScriptValidationResult:
    script = project.script or ""
    visible_script = re.sub(r"<think>.*?</think>", "", script, flags=re.DOTALL | re.IGNORECASE)
    units = project.script_units or split_script_units(script)
    episode_counter = Counter(unit["episode"] for unit in units)
    present_episodes = sorted(episode_counter)
    missing_episodes = [
        episode for episode in range(1, project.episode_count + 1) if episode not in present_episodes
    ]
    duplicate_episodes = sorted(
        episode for episode, count in episode_counter.items() if count > 1
    )
    issues: list[str] = []

    if not script.strip():
        issues.append("脚本为空")
    if "<think>" in script or "</think>" in script:
        issues.append("包含模型思考内容")
    if _declares_mismatched_episode_count(visible_script or script, project.episode_count):
        issues.append("脚本集数与项目设定不一致")
    if _declares_mismatched_duration(visible_script or script, project.seconds_per_episode):
        issues.append("脚本单集时长与项目设定不一致")
    if project.episode_count > 1 and len(present_episodes) < project.episode_count:
        issues.append("分集内容不足")
    if duplicate_episodes:
        issues.append("存在重复集数")

    return ScriptValidationResult(
        is_complete=not issues,
        issues=issues,
        fragment_count=len(units),
        episode_count=len(present_episodes),
        expected_episode_count=project.episode_count,
        present_episodes=present_episodes,
        missing_episodes=missing_episodes,
        duplicate_episodes=duplicate_episodes,
    )


def _declares_mismatched_episode_count(script: str, expected: int) -> bool:
    matches = [int(value) for value in re.findall(r"(\d+)\s*集", script[:1200])]
    return any(value != expected for value in matches)


def _declares_mismatched_duration(script: str, expected_seconds: int) -> bool:
    expected_minutes = expected_seconds / 60
    seconds_patterns = [
        r"(?:单集(?:时长)?|每集(?:时长)?)[^\d]{0,8}(\d+(?:\.\d+)?)\s*秒",
        r"\d+\s*集\s*[·・]\s*(\d+(?:\.\d+)?)\s*秒",
        r"脚本[（(][^）)]*?(\d+(?:\.\d+)?)\s*秒",
    ]
    for pattern in seconds_patterns:
        for value in re.findall(pattern, script[:1200]):
            if int(float(value)) != expected_seconds:
                return True
    minutes_patterns = [
        r"(?:单集(?:时长)?|每集(?:时长)?)[^\d]{0,8}(\d+(?:\.\d+)?)\s*分钟",
        r"\d+\s*集\s*[·・]\s*(\d+(?:\.\d+)?)\s*分钟",
        r"脚本[（(][^）)]*?(\d+(?:\.\d+)?)\s*分钟",
    ]
    for pattern in minutes_patterns:
        for value in re.findall(pattern, script[:1200]):
            if int(float(value) * 60) != expected_seconds:
                return True
    return False


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
