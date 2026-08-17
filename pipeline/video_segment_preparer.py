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
    selected_characters = _selected_character_names(selected_shots)
    base_images = _base_images(
        project.characters,
        project.visual_assets,
        project_dir,
        episode=episode,
        selected_character_names=selected_characters,
    )
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
        "selected_characters": selected_characters,
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


def video_segment_windows(
    project: Project,
    episode: int,
    window_seconds: float,
    start_sec: float | None = None,
    end_sec: float | None = None,
    limit: int | None = None,
) -> list[tuple[int, int | float, int | float]]:
    """Split an episode into fixed-size video generation windows."""
    if window_seconds <= 0:
        raise ValueError("window_seconds must be greater than 0")

    episode_blocks = [
        (block_start, block_end)
        for block_episode, block_start, block_end in _script_time_blocks(project)
        if block_episode == episode
    ]
    if not episode_blocks and start_sec is None and end_sec is None:
        raise ValueError(f"未找到第 {episode} 集脚本时间块")

    start = float(start_sec) if start_sec is not None else min(block[0] for block in episode_blocks)
    end = float(end_sec) if end_sec is not None else max(block[1] for block in episode_blocks)
    if end <= start:
        raise ValueError("end_sec must be greater than start_sec")

    windows: list[tuple[int, int | float, int | float]] = []
    cursor = start
    while cursor < end:
        window_end = min(cursor + window_seconds, end)
        windows.append((episode, _clean_second(cursor), _clean_second(window_end)))
        if limit is not None and len(windows) >= limit:
            break
        cursor = window_end
    return windows


def prepare_video_segment_window_payloads(
    project: Project,
    episode: int,
    window_seconds: float,
    project_dir: str | Path | None = None,
    start_sec: float | None = None,
    end_sec: float | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Prepare provider-neutral payloads for fixed-size episode windows."""
    payloads: list[dict[str, Any]] = []
    for index, (_, window_start, window_end) in enumerate(
        video_segment_windows(
            project,
            episode=episode,
            window_seconds=window_seconds,
            start_sec=start_sec,
            end_sec=end_sec,
            limit=limit,
        ),
        start=1,
    ):
        payload = prepare_video_segment_payload(
            project,
            episode=episode,
            start_sec=float(window_start),
            end_sec=float(window_end),
            project_dir=project_dir,
        )
        payload["window_seconds"] = _clean_second(float(window_seconds))
        payload["window_index"] = index
        payload["windowed"] = True
        payloads.append(payload)
    return payloads


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


def _selected_character_names(selected_shots: list[tuple[Shot, float, float]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for shot, _, _ in selected_shots:
        for name in shot.characters:
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


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
    episode: int,
    selected_character_names: list[str],
) -> dict[str, list[str]]:
    character_images: list[str] = []
    scene_images: list[str] = []
    prop_images: list[str] = []
    selected_set = set(selected_character_names)
    resolved_character_names: set[str] = set()
    for character in characters:
        if selected_set and character.name not in selected_set:
            continue
        resolved_character_names.add(character.name)
        images = _character_images_for_episode(character, episode)
        if not images:
            images = _discover_character_images(project_dir, character.name, episode)
        character_images.extend(images)
    for character_name in selected_character_names:
        if character_name not in resolved_character_names:
            character_images.extend(_discover_character_images(project_dir, character_name, episode))
    for asset in visual_assets:
        category = asset.category.lower()
        if category == "scene":
            scene_images.extend(asset.image_paths)
        elif category == "prop":
            prop_images.extend(asset.image_paths)
        else:
            prop_images.extend(asset.image_paths)
    discovered = _discover_base_images(project_dir)
    scene_images.extend(discovered["scenes"])
    prop_images.extend(discovered["props"])
    return {
        "characters": [_normalize_path(path, project_dir) for path in _unique_non_empty(character_images)],
        "scenes": [_normalize_path(path, project_dir) for path in _unique_non_empty(scene_images)],
        "props": [_normalize_path(path, project_dir) for path in _unique_non_empty(prop_images)],
    }


def _character_images_for_episode(character: Character, episode: int) -> list[str]:
    images: list[str] = []
    matching_variants = [
        variant
        for variant in character.variants
        if _variant_matches_episode(variant, episode)
    ]
    if matching_variants:
        for variant in matching_variants:
            for paths in variant.image_paths.values():
                images.extend(paths)
        return images

    for paths in character.image_paths.values():
        images.extend(paths)
    if not images and len(character.variants) == 1:
        for paths in character.variants[0].image_paths.values():
            images.extend(paths)
    return images


def _variant_matches_episode(variant, episode: int) -> bool:
    text = f"{getattr(variant, 'name', '')} {getattr(variant, 'story_stage', '')}"
    for start, end in _episode_ranges(text):
        if start <= episode <= end:
            return True
    return False


def _episode_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in re.finditer(r"第\s*(\d+)\s*[-至到—~～]\s*(\d+)\s*集", text):
        start = int(match.group(1))
        end = int(match.group(2))
        ranges.append((min(start, end), max(start, end)))
    for match in re.finditer(r"第\s*(\d+)\s*集(?:以后|之后|起)", text):
        ranges.append((int(match.group(1)), 10_000))
    return ranges


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
        "characters": [],
        "scenes": _image_files(root / "scenes"),
        "props": _image_files(root / "props"),
    }


def _discover_character_images(
    project_dir: str | Path | None,
    character_name: str,
    episode: int,
) -> list[str]:
    if project_dir is None:
        return []
    root = Path(project_dir) / "images" / "assets" / "characters"
    if not root.exists():
        return []
    character_dirs = [
        path
        for path in sorted(root.iterdir())
        if path.is_dir() and character_name in path.name
    ]
    images: list[str] = []
    for character_dir in character_dirs:
        variant_dirs = [path for path in sorted(character_dir.iterdir()) if path.is_dir()]
        matching_dirs = [
            path
            for path in variant_dirs
            if _text_matches_episode(path.name, episode)
        ]
        if matching_dirs:
            for path in matching_dirs:
                images.extend(_image_files(path))
        elif not variant_dirs:
            images.extend(_image_files(character_dir))
        elif len(variant_dirs) == 1:
            images.extend(_image_files(variant_dirs[0]))
    return images


def _text_matches_episode(text: str, episode: int) -> bool:
    return any(start <= episode <= end for start, end in _episode_ranges(text))


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
