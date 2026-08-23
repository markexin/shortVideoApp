"""Web 层共享依赖：ProjectManager 单例与项目加载。

ProjectManager 以进程级惰性单例提供，指向 config.PROJECTS_DIR，
与 CLI 共享同一份 projects_data 存储，保证 Web 与 CLI 看到相同项目。
"""
from __future__ import annotations

import config
from projects.manager import ProjectManager
from projects.schema import Project

from web.errors import ProjectNotFoundError

_manager: ProjectManager | None = None


def get_project_manager() -> ProjectManager:
    global _manager
    if _manager is None:
        _manager = ProjectManager(config.PROJECTS_DIR)
    return _manager


def load_project_or_404(project_id: str) -> Project:
    manager = get_project_manager()
    try:
        return manager.load_project(project_id)
    except FileNotFoundError as exc:
        raise ProjectNotFoundError(f"项目不存在: {project_id}") from exc