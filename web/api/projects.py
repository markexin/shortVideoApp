"""项目相关 API 路由。

Phase 1 提供项目总览与详情读取、项目创建。
所有响应使用统一的 {success, data} / {success, error} 结构。
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

import config
from projects.manager import ProjectManager
from web import serializers
from web.deps import get_project_manager, load_project_or_404

router = APIRouter(tags=["projects"])


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _ok(data) -> dict:
    return {"success": True, "data": data}


class CreateProjectRequest(BaseModel):
    title: str = Field(..., min_length=1, description="剧名")
    premise: str = Field("", description="创意/前提描述")
    genre: str = Field("儿童教育短剧", description="题材")
    platform: str = Field("manual", description="发布平台")
    aspect_ratio: str = Field("9:16", description="画幅 9:16 / 16:9")
    episode_count: int = Field(6, ge=1, le=50, description="集数")
    seconds_per_episode: int = Field(60, ge=15, le=600, description="单集秒数")
    audience: str = Field("3-8岁儿童", description="目标受众")
    pacing_style: str = Field("寓教于乐，单集有起承转合", description="节奏风格")


@router.get("/projects")
def list_projects() -> dict:
    manager = get_project_manager()
    projects = manager.list_projects()
    return _ok([serializers.summary(p) for p in projects])


@router.post("/projects")
def create_project(payload: CreateProjectRequest) -> dict:
    manager: ProjectManager = get_project_manager()
    project = manager.create_project(
        title=payload.title,
        premise=payload.premise,
        genre=payload.genre,
        platform=payload.platform,
        aspect_ratio=payload.aspect_ratio,
        episode_count=payload.episode_count,
        seconds_per_episode=payload.seconds_per_episode,
        audience=payload.audience,
        pacing_style=payload.pacing_style,
    )
    project.current_step = "script_confirm"
    manager.save_project(project)
    return _ok(serializers.summary(project))


class _StructuralChange:
    """判断编辑是否触及会令脚本/角色/分镜失效的结构性字段。"""

    STRUCTURAL = {"genre", "aspect_ratio", "episode_count", "seconds_per_episode", "audience", "pacing_style"}

    @classmethod
    def detect(cls, before: dict, after: dict) -> bool:
        return any(after.get(k) != before.get(k) for k in cls.STRUCTURAL)


@router.patch("/projects/{project_id}")
def update_project(project_id: str, payload: CreateProjectRequest) -> dict:
    manager: ProjectManager = get_project_manager()
    existing = load_project_or_404(project_id)

    before = {
        "genre": existing.genre,
        "aspect_ratio": existing.aspect_ratio,
        "episode_count": existing.episode_count,
        "seconds_per_episode": existing.seconds_per_episode,
        "audience": existing.audience,
        "pacing_style": existing.pacing_style,
    }
    reset_pipeline = _StructuralChange.detect(before, {
        "genre": payload.genre,
        "aspect_ratio": payload.aspect_ratio,
        "episode_count": payload.episode_count,
        "seconds_per_episode": payload.seconds_per_episode,
        "audience": payload.audience,
        "pacing_style": payload.pacing_style,
    })

    manager.update_project(
        project_id,
        title=payload.title,
        premise=payload.premise,
        genre=payload.genre,
        platform=payload.platform,
        aspect_ratio=payload.aspect_ratio,
        episode_count=payload.episode_count,
        seconds_per_episode=payload.seconds_per_episode,
        audience=payload.audience,
        pacing_style=payload.pacing_style,
        reset_pipeline=reset_pipeline,
    )
    return _ok(serializers.summary(manager.load_project(project_id)))


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    project = load_project_or_404(project_id)
    return _ok(serializers.detail(project))


@router.get("/projects/{project_id}/stages")
def get_project_stages(project_id: str) -> dict:
    """全流水线阶段概览（全局总览核心数据）。"""
    project = load_project_or_404(project_id)
    return _ok({
        "project_id": project.project_id,
        "title": project.title,
        "current_step": project.current_step,
        "stages": serializers.stage_overview(project),
    })


@router.get("/projects/{project_id}/actions")
def get_project_actions(project_id: str) -> dict:
    project = load_project_or_404(project_id)
    return _ok(serializers.actions(project))