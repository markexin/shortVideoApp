from __future__ import annotations

from pathlib import Path

from projects.schema import Project
from tools import ffmpeg_ops


def collect_video_paths(project: Project) -> list[str]:
    paths = []
    for shot in sorted(project.shots, key=lambda item: item.shot_id):
        if not shot.video_path:
            raise ValueError(f"第 {shot.shot_id} 镜还没有视频路径")
        paths.append(shot.video_path)
    return paths


def assemble_episode(project: Project, output_path: str | Path) -> str:
    video_paths = collect_video_paths(project)
    if not video_paths:
        raise ValueError("项目没有可拼接的视频镜头")
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_ops.concat_simple(video_paths, output_path)
    return output_path
