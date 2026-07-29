from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import requests

from workflows.base import WorkflowRequest, WorkflowResult


def normalize_workflow_response(data: dict[str, Any], output_path: str) -> WorkflowResult:
    if data.get("status") not in {"success", "succeeded"}:
        return WorkflowResult(
            status="failed",
            error=str(data.get("error", "workflow failed")),
            provider="http",
            metadata=data,
        )

    local_path = data.get("local_path")
    if local_path:
        return WorkflowResult(
            status="success",
            local_path=local_path,
            provider="http",
            metadata=data,
        )

    video_url = data.get("video_url")
    if video_url:
        return WorkflowResult(
            status="success",
            local_path=output_path,
            provider="http",
            metadata=data,
        )

    return WorkflowResult(
        status="failed",
        error="workflow response missing local_path or video_url",
        provider="http",
        metadata=data,
    )


class HTTPWorkflowAdapter:
    """Generic adapter for an external image-to-video workflow endpoint.

    The endpoint receives JSON and should return either:
    - {"status": "success", "local_path": "/path/to/video.mp4"}
    - {"status": "success", "video_url": "https://.../video.mp4"}
    - {"status": "failed", "error": "..."}
    """

    def __init__(self, endpoint: str, timeout: int = 600):
        self.endpoint = endpoint
        self.timeout = timeout

    async def generate_shot(self, request: WorkflowRequest) -> WorkflowResult:
        return await asyncio.to_thread(self._generate_sync, request)

    def _generate_sync(self, request: WorkflowRequest) -> WorkflowResult:
        payload: dict[str, Any] = {
            "shot_id": request.shot_id,
            "image_path": request.image_path,
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "duration": request.duration,
            "aspect_ratio": request.aspect_ratio,
            "output_path": request.output_path,
            "metadata": request.metadata,
        }
        try:
            resp = requests.post(self.endpoint, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return WorkflowResult(status="failed", error=str(exc), provider="http")

        normalized = normalize_workflow_response(data, request.output_path)
        if normalized.status != "success":
            return normalized
        if data.get("local_path"):
            return normalized

        video_url = data["video_url"]

        try:
            Path(request.output_path).parent.mkdir(parents=True, exist_ok=True)
            with requests.get(video_url, stream=True, timeout=self.timeout) as video_resp:
                video_resp.raise_for_status()
                with open(request.output_path, "wb") as f:
                    for chunk in video_resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
        except Exception as exc:
            return WorkflowResult(status="failed", error=str(exc), provider="http", metadata=data)

        return WorkflowResult(
            status="success",
            local_path=request.output_path,
            provider="http",
            metadata=data,
        )
