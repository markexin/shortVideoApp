from __future__ import annotations

import base64
import mimetypes
import time
from pathlib import Path
from typing import Any

import requests

from workflows.base import WorkflowResult
from workflows.comfyui import build_msr_segment_inputs


MINIMAX_VIDEO_BASE_URL = "https://api.minimaxi.com"
DEFAULT_MINIMAX_VIDEO_MODEL = "MiniMax-H3"
DEFAULT_MINIMAX_RESOLUTION = "1080P"
DEFAULT_MINIMAX_DURATION = 6
MAX_H3_REFERENCE_IMAGES = 9


def encode_image_data_url(image_path: str | Path) -> str:
    path = Path(image_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_minimax_video_request(
    payload: dict[str, Any],
    mode: str = "h3_reference",
    model: str = DEFAULT_MINIMAX_VIDEO_MODEL,
    duration: int = DEFAULT_MINIMAX_DURATION,
    resolution: str = DEFAULT_MINIMAX_RESOLUTION,
) -> dict[str, Any]:
    """Build a MiniMax video_generation request from the ComfyUI-style segment payload."""
    mode = _normalize_minimax_mode(mode)
    model = _normalize_minimax_model(model, mode)
    inputs = build_msr_segment_inputs(payload)
    reference_images = _h3_reference_images(inputs)
    content: list[dict[str, Any]] = [{"type": "text", "text": inputs.prompt}]
    content.extend(
        {
            "type": "image_url",
            "image_url": {"url": encode_image_data_url(path)},
            "role": "reference_image",
        }
        for path in reference_images
    )
    request: dict[str, Any] = {
        "model": model,
        "content": content,
        "duration": duration,
        "resolution": resolution,
        "_metadata": {
            "mode": mode,
            "reference_images_used": bool(reference_images),
            "character_image_count": len(inputs.reference_character_images),
            "reference_image_count": len(reference_images),
            "scene_image_path": inputs.background_image_path,
            "prop_image_count": len(inputs.prop_image_paths),
        },
    }

    if mode != "h3_reference":
        raise ValueError(f"未知 MiniMax 视频模式: {mode}")

    return request


def _normalize_minimax_mode(mode: str) -> str:
    if mode in {"subject_reference", "image_to_video", "text_to_video"}:
        return "h3_reference"
    return mode


def _normalize_minimax_model(model: str, mode: str) -> str:
    if mode == "h3_reference" and model in {"S2V-01", "I2V-01-Director", "MiniMax-Hailuo-2.3"}:
        return DEFAULT_MINIMAX_VIDEO_MODEL
    return model


def _h3_reference_images(inputs) -> list[str]:
    paths: list[str] = []
    paths.extend(inputs.reference_character_images)
    paths.append(inputs.background_image_path)
    paths.extend(inputs.prop_image_paths)
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        if not path or path in seen:
            continue
        seen.add(path)
        unique.append(path)
        if len(unique) >= MAX_H3_REFERENCE_IMAGES:
            break
    return unique


class MiniMaxVideoAdapter:
    def __init__(
        self,
        api_key: str,
        base_url: str = MINIMAX_VIDEO_BASE_URL,
        timeout: int = 3600,
        poll_interval: float = 15.0,
    ):
        if not api_key:
            raise ValueError("缺少 MINIMAX_API_KEY")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def generate_segment(
        self,
        payload: dict[str, Any],
        output_path: str | Path,
        mode: str = "h3_reference",
        model: str = DEFAULT_MINIMAX_VIDEO_MODEL,
        duration: int = DEFAULT_MINIMAX_DURATION,
        resolution: str = DEFAULT_MINIMAX_RESOLUTION,
    ) -> WorkflowResult:
        try:
            request_payload = build_minimax_video_request(
                payload,
                mode=mode,
                model=model,
                duration=duration,
                resolution=resolution,
            )
            metadata = request_payload.pop("_metadata")
            task_id = self._create_task(request_payload)
            query_result = self._wait_for_task(task_id)
            download_url = _extract_h3_download_url(query_result)
            self._download_video(download_url, output_path)
            return WorkflowResult(
                status="success",
                local_path=str(output_path),
                provider="minimax-video",
                metadata={
                    **metadata,
                    "task_id": task_id,
                    "download_url": download_url,
                    "query_result": query_result,
                },
            )
        except Exception as exc:
            return WorkflowResult(status="failed", error=str(exc), provider="minimax-video")

    def _create_task(self, payload: dict[str, Any]) -> str:
        response = self.session.post(
            f"{self.base_url}/v2/video_generation",
            json=payload,
            timeout=60,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"MiniMax /v2/video_generation 失败 {response.status_code}: {response.text}")
        data = response.json()
        task_id = data.get("task_id")
        if not task_id:
            raise RuntimeError(f"MiniMax 创建任务响应缺少 task_id: {data}")
        return task_id

    def _wait_for_task(self, task_id: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            data = self._query_task(task_id)
            task = data.get("task", data)
            status = str(task.get("status", "")).lower()
            if status in {"success", "succeeded", "finished", "completed"}:
                return data
            if status in {"fail", "failed", "error"}:
                raise RuntimeError(f"MiniMax 视频任务失败: {data}")
            time.sleep(self.poll_interval)
        raise TimeoutError(f"等待 MiniMax 视频任务超时: {task_id}")

    def _query_task(self, task_id: str) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/v2/query/video_generation/{task_id}",
            timeout=60,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"MiniMax /v2/query/video_generation 失败 {response.status_code}: {response.text}")
        return response.json()

    def _download_video(self, download_url: str, output_path: str | Path) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        download_session = requests.Session()
        download_session.trust_env = False
        with download_session.get(download_url, stream=True, timeout=300) as response:
            response.raise_for_status()
            with path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)


def _extract_h3_download_url(query_result: dict[str, Any]) -> str:
    task = query_result.get("task", query_result)
    content = task.get("content", {})
    if isinstance(content, dict):
        download_url = content.get("url")
        if download_url:
            return download_url
    raise RuntimeError(f"MiniMax H3 查询响应缺少 task.content.url: {query_result}")
