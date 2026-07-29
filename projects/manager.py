from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import uuid4

from projects.schema import Project


class ProjectManager:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def create_project(
        self,
        title: str,
        genre: str = "",
        platform: str = "",
    ) -> Project:
        prefix = self._slugify(title) or "project"
        project = Project(
            project_id=f"{prefix}-{uuid4().hex[:8]}",
            title=title,
            genre=genre,
            platform=platform,
        )
        project_dir = self.project_dir(project.project_id)
        (project_dir / "prompts").mkdir(parents=True, exist_ok=True)
        (project_dir / "images").mkdir(exist_ok=True)
        (project_dir / "videos").mkdir(exist_ok=True)
        (project_dir / "logs").mkdir(exist_ok=True)
        self.save_project(project)
        return project

    def save_project(self, project: Project) -> None:
        project_dir = self.project_dir(project.project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / "project.json"
        path.write_text(
            json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if project.script:
            script_path = project_dir / "script.md"
            script_path.write_text(
                f"# {project.title}\n\n{project.script}\n",
                encoding="utf-8",
            )

    def load_project(self, project_id: str) -> Project:
        path = self.project_dir(project_id) / "project.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return Project.from_dict(data)

    def list_projects(self) -> list[Project]:
        projects = []
        for path in self.root_dir.glob("*/project.json"):
            try:
                projects.append(Project.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, KeyError):
                continue
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)

    def project_dir(self, project_id: str) -> Path:
        return self.root_dir / project_id

    @staticmethod
    def _slugify(value: str) -> str:
        cleaned = re.sub(r"\s+", "-", value.strip().lower())
        cleaned = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", cleaned)
        return cleaned.strip("-")[:32]
