"""Prepare multi-image + text video API payloads for script time ranges."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from projects.schema import Character, Project, Shot, VisualAsset


TIME_BLOCK_RE = re.compile(
    r"(?P<header>\*\*【(?P<start>\d+)\s*-\s*(?P<end>\d+)秒[^】]*】\*\*)",
    re.MULTILINE,
)
VIDEO_SEGMENT_PAYLOAD_GLOB = "video_segment_*_payload.json"


def prepare_video_segment_payload(
    project: Project,
    episode: int,
    start_sec: float,
    end_sec: float,
    project_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build a provider-neutral payload for all shots overlapping a time range."""
    if end_sec <= start_sec:
        raise ValueError("end_sec must be greater than start_sec")

    selected_shots = _select_overlapping_shots(project.shots, start_sec, end_sec)
    base_images = _base_images(project.characters, project.visual_assets, project_dir)
    reference_images = _flatten_base_images(base_images)
    has_prompt = any(
        shot.video_prompt or shot.image_prompt or shot.scene_description
        for shot, _, _ in selected_shots
    )

    return {
        "project_id": project.project_id,
        "title": project.title,
        "aspect_ratio": project.aspect_ratio,
        "episode": episode,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "script_excerpt": _extract_script_excerpt(project, episode, start_sec, end_sec),
        "shots": [
            _shot_payload(shot, shot_start, shot_end, project_dir)
            for shot, shot_start, shot_end in selected_shots
        ],
        "images": [],
        "base_images": base_images,
        "reference_images": reference_images,
        "missing_images": [],
        "api_ready": len(selected_shots) > 0 and bool(reference_images) and has_prompt,
    }


def prepare_next_video_segment_payload(
    project: Project,
    project_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Prepare the first script time block that still overlaps unfinished shots."""
    for episode, block_start, block_end in _script_time_blocks(project):
        selected = _select_overlapping_shots(project.shots, block_start, block_end)
        if selected and any(not shot.video_path for shot, _, _ in selected):
            return prepare_video_segment_payload(
                project,
                episode=episode,
                start_sec=block_start,
                end_sec=block_end,
                project_dir=project_dir,
            )
    raise ValueError("未找到可准备的视频片段")


def find_latest_video_segment_payload(project_dir: str | Path) -> Path | None:
    """Return the newest prepared video segment payload for a project."""
    prompt_dir = Path(project_dir) / "prompts"
    payloads = sorted(prompt_dir.glob(VIDEO_SEGMENT_PAYLOAD_GLOB))
    return payloads[-1] if payloads else None


def _script_time_blocks(project: Project) -> list[tuple[int, float, float]]:
    blocks: list[tuple[int, float, float]] = []
    for unit in project.script_units:
        try:
            episode = int(unit.get("episode", 0))
        except (TypeError, ValueError):
            continue
        content = str(unit.get("content", ""))
        for match in TIME_BLOCK_RE.finditer(content):
            blocks.append(
                (
                    episode,
                    float(match.group("start")),
                    float(match.group("end")),
                )
            )
    return blocks


def _select_overlapping_shots(
    shots: list[Shot],
    start_sec: float,
    end_sec: float,
) -> list[tuple[Shot, float, float]]:
    selected: list[tuple[Shot, float, float]] = []
    cursor = 0.0
    for shot in shots:
        duration = float(shot.duration)
        shot_start = cursor
        shot_end = cursor + duration
        if shot_start < end_sec and shot_end > start_sec:
            selected.append((shot, _clean_second(shot_start), _clean_second(shot_end)))
        cursor = shot_end
    return selected


def _extract_script_excerpt(
    project: Project,
    episode: int,
    start_sec: float,
    end_sec: float,
) -> str:
    content = _episode_content(project, episode)
    if not content:
        return ""

    matches = list(TIME_BLOCK_RE.finditer(content))
    if not matches:
        return content.strip()

    blocks: list[str] = []
    for index, match in enumerate(matches):
        block_start = float(match.group("start"))
        block_end = float(match.group("end"))
        if not (block_start < end_sec and block_end > start_sec):
            continue
        body_start = match.start()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        blocks.append(content[body_start:body_end].strip())
    return "\n\n".join(blocks)


def _episode_content(project: Project, episode: int) -> str:
    for unit in project.script_units:
        try:
            unit_episode = int(unit.get("episode", 0))
        except (TypeError, ValueError):
            continue
        if unit_episode == episode:
            return str(unit.get("content", ""))
    return ""


def _shot_payload(
    shot: Shot,
    shot_start: float,
    shot_end: float,
    project_dir: str | Path | None,
) -> dict[str, Any]:
    return {
        "shot_id": shot.shot_id,
        "start_sec": shot_start,
        "end_sec": shot_end,
        "duration": shot.duration,
        "scene_description": shot.scene_description,
        "action": shot.action,
        "dialogue": shot.dialogue,
        "characters": list(shot.characters),
        "video_prompt": shot.video_prompt,
        "image_prompt": shot.image_prompt,
        "negative_prompt": shot.negative_prompt,
        "image_path": _normalize_path(shot.image_path, project_dir) if shot.image_path else "",
        "status": shot.status,
    }


def _base_images(
    characters: list[Character],
    visual_assets: list[VisualAsset],
    project_dir: str | Path | None,
) -> dict[str, list[str]]:
    character_images: list[str] = []
    scene_images: list[str] = []
    prop_images: list[str] = []
    for character in characters:
        for paths in character.image_paths.values():
            character_images.extend(paths)
        for variant in character.variants:
            for paths in variant.image_paths.values():
                character_images.extend(paths)
    for asset in visual_assets:
        category = asset.category.lower()
        if category == "scene":
            scene_images.extend(asset.image_paths)
        elif category == "prop":
            prop_images.extend(asset.image_paths)
        else:
            prop_images.extend(asset.image_paths)
    discovered = _discover_base_images(project_dir)
    character_images.extend(discovered["characters"])
    scene_images.extend(discovered["scenes"])
    prop_images.extend(discovered["props"])
    return {
        "characters": [_normalize_path(path, project_dir) for path in _unique_non_empty(character_images)],
        "scenes": [_normalize_path(path, project_dir) for path in _unique_non_empty(scene_images)],
        "props": [_normalize_path(path, project_dir) for path in _unique_non_empty(prop_images)],
    }


def _flatten_base_images(base_images: dict[str, list[str]]) -> list[str]:
    return _unique_non_empty(
        base_images.get("characters", [])
        + base_images.get("scenes", [])
        + base_images.get("props", [])
    )


def _discover_base_images(project_dir: str | Path | None) -> dict[str, list[str]]:
    if project_dir is None:
        return {"characters": [], "scenes": [], "props": []}
    root = Path(project_dir) / "images" / "assets"
    return {
        "characters": _image_files(root / "characters"),
        "scenes": _image_files(root / "scenes"),
        "props": _image_files(root / "props"),
    }


def _image_files(root: Path) -> list[str]:
    if not root.exists():
        return []
    suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    return [
        str(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in suffixes
    ]


def _unique_non_empty(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        if not path or path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _normalize_path(path: str, project_dir: str | Path | None) -> str:
    if not path:
        return ""
    path_obj = Path(path)
    if path_obj.is_absolute():
        return str(path_obj)
    if project_dir is None:
        return str(path_obj)

    project_path = Path(project_dir)
    candidates = [Path.cwd() / path_obj, project_path / path_obj]
    candidates.extend(parent / path_obj for parent in project_path.parents)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return str((project_path / path_obj).resolve())


def _clean_second(value: float) -> int | float:
    return int(value) if value.is_integer() else value
