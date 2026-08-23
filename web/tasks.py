"""In-memory task store for long-running pipeline operations.

Each operation (script generation, character generation, etc.) is
represented as a TaskRecord with a unique ID, status, and metadata.
Frontend polls /api/tasks/{task_id} to check progress.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class TaskRecord:
    """Represents a long-running operation."""
    task_id: str
    op: str  # Operation name (e.g., "generate_script", "generate_characters")
    project_id: str
    status: str = "pending"  # pending, running, completed, failed
    progress: float = 0.0  # 0.0 - 1.0
    message: str = ""
    result: dict = field(default_factory=dict)
    error: str = ""


# In-memory task store
_tasks: dict[str, TaskRecord] = {}


def create_task(op: str, project_id: str, message: str = "") -> TaskRecord:
    """Create a new task and return it."""
    task_id = uuid.uuid4().hex[:12]
    task = TaskRecord(
        task_id=task_id,
        op=op,
        project_id=project_id,
        status="pending",
        message=message or f"{op} 任务已创建",
    )
    _tasks[task_id] = task
    return task


def get_task(task_id: str) -> TaskRecord | None:
    """Get a task by ID, or None if not found."""
    return _tasks.get(task_id)


def list_tasks(project_id: str | None = None) -> list[TaskRecord]:
    """List all tasks, optionally filtered by project_id."""
    tasks = list(_tasks.values())
    if project_id:
        tasks = [t for t in tasks if t.project_id == project_id]
    return sorted(tasks, key=lambda t: t.task_id, reverse=True)


def update_task(
    task_id: str,
    status: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    result: dict | None = None,
    error: str | None = None,
) -> TaskRecord | None:
    """Update a task's status/progress/result."""
    task = _tasks.get(task_id)
    if task is None:
        return None
    if status is not None:
        task.status = status
    if progress is not None:
        task.progress = progress
    if message is not None:
        task.message = message
    if result is not None:
        task.result = result
    if error is not None:
        task.error = error
    return task


def complete_task(task_id: str, result: dict | None = None) -> TaskRecord | None:
    """Mark a task as completed with optional result."""
    return update_task(task_id, status="completed", progress=1.0, result=result or {})


def fail_task(task_id: str, error: str) -> TaskRecord | None:
    """Mark a task as failed with error message."""
    return update_task(task_id, status="failed", error=error)


def remove_task(task_id: str) -> bool:
    """Remove a task from the store."""
    if task_id in _tasks:
        del _tasks[task_id]
        return True
    return False