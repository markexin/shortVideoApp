from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class WorkflowRequest:
    shot_id: int
    image_path: str
    prompt: str
    negative_prompt: str
    duration: float
    aspect_ratio: str
    output_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    status: str
    local_path: str | None = None
    provider: str = "custom"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkflowAdapter(Protocol):
    async def generate_shot(self, request: WorkflowRequest) -> WorkflowResult:
        """Generate one video shot from a prepared image and prompt."""
