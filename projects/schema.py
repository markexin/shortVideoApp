from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


@dataclass
class Character:
    name: str
    description: str = ""
    consistency_prompt: str = ""
    negative_prompt: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Character":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            consistency_prompt=data.get("consistency_prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
        )


@dataclass
class Shot:
    shot_id: int
    scene_description: str = ""
    action: str = ""
    characters: list[str] = field(default_factory=list)
    dialogue: str = ""
    image_prompt: str = ""
    video_prompt: str = ""
    negative_prompt: str = ""
    image_path: str = ""
    video_path: str = ""
    duration: float = 5.0
    status: str = "draft"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Shot":
        return cls(
            shot_id=int(data.get("shot_id", 0)),
            scene_description=data.get("scene_description", ""),
            action=data.get("action", ""),
            characters=list(data.get("characters", [])),
            dialogue=data.get("dialogue", ""),
            image_prompt=data.get("image_prompt", ""),
            video_prompt=data.get("video_prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
            image_path=data.get("image_path", ""),
            video_path=data.get("video_path", ""),
            duration=float(data.get("duration", 5.0)),
            status=data.get("status", "draft"),
        )


@dataclass
class Project:
    project_id: str
    title: str
    premise: str = ""
    genre: str = ""
    platform: str = ""
    episode_count: int = 6
    seconds_per_episode: int = 60
    audience: str = "3-8岁儿童"
    pacing_style: str = "寓教于乐"
    script: str = ""
    script_units: list[dict[str, Any]] = field(default_factory=list)
    script_generation: dict[str, Any] = field(default_factory=dict)
    current_step: str = "home"
    characters: list[Character] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            project_id=data["project_id"],
            title=data.get("title", ""),
            premise=data.get("premise", ""),
            genre=data.get("genre", ""),
            platform=data.get("platform", ""),
            episode_count=int(data.get("episode_count", 6)),
            seconds_per_episode=int(data.get("seconds_per_episode", 60)),
            audience=data.get("audience", "3-8岁儿童"),
            pacing_style=data.get("pacing_style", "寓教于乐"),
            script=data.get("script", ""),
            script_units=list(data.get("script_units", [])),
            script_generation=dict(data.get("script_generation", {})),
            current_step=data.get("current_step", "home"),
            characters=[
                Character.from_dict(item) for item in data.get("characters", [])
            ],
            shots=[Shot.from_dict(item) for item in data.get("shots", [])],
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )
