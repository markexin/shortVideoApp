"""项目序列化与全流水线阶段概览。

把持久化的 Project 数据 + 状态机 FLOW 转成前端可直接渲染的结构：
- summary: 列表页用的轻量摘要（不含脚本/提示词等大字段）
- detail: 详情页全量数据
- stage_overview: 8 个流水线阶段的全局进度（核心功能）
- actions: 当前阶段可用的下一步操作（直接来自状态机）
"""
from __future__ import annotations

from dataclasses import asdict

from agent.state_machine import FLOW, available_actions
from pipeline.script_validator import validate_script_completeness
from projects.schema import Project

# 阶段 key -> 中文展示名
STAGE_LABELS: dict[str, str] = {
    "home": "项目创建",
    "script_confirm": "脚本生成",
    "script_confirmed": "脚本确认",
    "characters_ready": "角色圣经",
    "storyboard_ready": "分镜生成",
    "image_prompts_exported": "图片准备",
    "videos_ready": "视频生成",
    "episode_ready": "整集合成",
}


def _stage_index(project: Project) -> int:
    try:
        return FLOW.index(project.current_step)
    except ValueError:
        return 0


def summary(project: Project) -> dict:
    shots = len(project.shots)
    image_ready = sum(1 for shot in project.shots if shot.image_path)
    video_ready = sum(1 for shot in project.shots if shot.video_path)
    return {
        "project_id": project.project_id,
        "title": project.title,
        "genre": project.genre,
        "platform": project.platform,
        "aspect_ratio": project.aspect_ratio,
        "episode_count": project.episode_count,
        "seconds_per_episode": project.seconds_per_episode,
        "audience": project.audience,
        "current_step": project.current_step,
        "current_stage_label": STAGE_LABELS.get(project.current_step, project.current_step),
        "stage_index": _stage_index(project),
        "can_edit": True,
        "character_count": len(project.characters),
        "shot_count": shots,
        "image_ready": image_ready,
        "video_ready": video_ready,
        "script_present": bool(project.script),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def stage_overview(project: Project) -> list[dict]:
    """逐个流水线阶段计算进度，供全局概览页渲染。

    每个阶段返回 status: done / active / pending，以及该阶段的关键指标。
    """
    current_idx = _stage_index(project)
    validation = validate_script_completeness(project)
    shots = project.shots
    shot_total = len(shots)
    image_ready = sum(1 for shot in shots if shot.image_path)
    video_ready = sum(1 for shot in shots if shot.video_path)

    stages: list[dict] = []
    for idx, stage in enumerate(FLOW):
        status = "done" if idx < current_idx else ("active" if idx == current_idx else "pending")
        metrics: dict = {}

        if stage == "script_confirm":
            metrics = {
                "script_present": bool(project.script),
                "script_complete": validation.is_complete,
                "episode_count": validation.episode_count,
                "expected_episode_count": validation.expected_episode_count,
                "issues": validation.issues,
            }
        elif stage == "script_confirmed":
            metrics = {"script_complete": validation.is_complete}
        elif stage == "characters_ready":
            metrics = {
                "character_count": len(project.characters),
                "visual_asset_count": len(project.visual_assets),
            }
        elif stage == "storyboard_ready":
            metrics = {
                "shot_count": shot_total,
                "character_count": len(project.characters),
            }
        elif stage in {"image_prompts_exported", "videos_ready"}:
            metrics = {
                "shot_count": shot_total,
                "image_ready": image_ready,
                "video_ready": video_ready,
                "image_progress": _progress(image_ready, shot_total),
                "video_progress": _progress(video_ready, shot_total),
            }
        elif stage == "episode_ready":
            metrics = {"video_ready": video_ready, "shot_count": shot_total}

        stages.append({
            "stage": stage,
            "label": STAGE_LABELS.get(stage, stage),
            "index": idx,
            "status": status,
            "metrics": metrics,
        })
    return stages


def _progress(done: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(done / total, 4)


def actions(project: Project) -> list[dict]:
    return [
        {
            "number": action.number,
            "label": action.label,
            "command_name": action.command_name,
            "command_text": action.command_text,
        }
        for action in available_actions(project.current_step)
    ]


def detail(project: Project) -> dict:
    """详情页全量数据：摘要 + 阶段概览 + 可用操作 + 实体数据。"""
    base = summary(project)
    base.update({
        "premise": project.premise,
        "pacing_style": project.pacing_style,
        "script": project.script,
        "script_units": project.script_units,
        "script_generation_status": project.script_generation.get("status", ""),
        "stage_overview": stage_overview(project),
        "actions": actions(project),
        "characters": [asdict(c) for c in project.characters],
        "visual_assets": [asdict(a) for a in project.visual_assets],
        "shots": [asdict(s) for s in project.shots],
    })
    return base