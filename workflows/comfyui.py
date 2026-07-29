from __future__ import annotations

import asyncio
import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from workflows.base import WorkflowRequest, WorkflowResult


PLACEHOLDERS = {
    "__IMAGE_NAME__": "image_name",
    "__IMAGE_PATH__": "image_name",
    "__PROMPT__": "prompt",
    "__NEGATIVE_PROMPT__": "negative_prompt",
    "__OUTPUT_PREFIX__": "output_prefix",
    "__DURATION__": "duration",
}


def apply_workflow_placeholders(
    workflow: dict[str, Any],
    image_name: str,
    prompt: str,
    negative_prompt: str,
    output_prefix: str,
    duration: float,
) -> dict[str, Any]:
    values = {
        "image_name": image_name,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "output_prefix": output_prefix,
        "duration": int(duration) if float(duration).is_integer() else duration,
    }

    def replace(value):
        if isinstance(value, str):
            return values[PLACEHOLDERS[value]] if value in PLACEHOLDERS else value
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    return replace(copy.deepcopy(workflow))


def pick_output_file(history_entry: dict[str, Any]) -> dict[str, Any]:
    outputs = history_entry.get("outputs", {})
    for key in ("videos", "gifs", "images"):
        for node_output in outputs.values():
            files = node_output.get(key, [])
            if files:
                return files[0]
    raise ValueError("ComfyUI history 中没有找到视频或图片输出")


class ComfyUIWorkflowAdapter:
    def __init__(
        self,
        base_url: str,
        workflow_path: str | Path,
        timeout: int = 600,
        poll_interval: float = 2.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.workflow_path = Path(workflow_path)
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def generate_shot(self, request: WorkflowRequest) -> WorkflowResult:
        return await asyncio.to_thread(self._generate_sync, request)

    def _generate_sync(self, request: WorkflowRequest) -> WorkflowResult:
        try:
            workflow = self._load_workflow()
            image_name = self._upload_image(request.image_path)
            output_prefix = f"short_drama_shot_{request.shot_id:03d}_{uuid.uuid4().hex[:8]}"
            prompt = apply_workflow_placeholders(
                workflow,
                image_name=image_name,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                output_prefix=output_prefix,
                duration=request.duration,
            )
            prompt_id = self._queue_prompt(prompt)
            history_entry = self._wait_for_history(prompt_id)
            output_info = pick_output_file(history_entry)
            self._download_output(output_info, request.output_path)
            return WorkflowResult(
                status="success",
                local_path=request.output_path,
                provider="comfyui",
                metadata={"prompt_id": prompt_id, "output": output_info},
            )
        except Exception as exc:
            return WorkflowResult(status="failed", error=str(exc), provider="comfyui")

    def _load_workflow(self) -> dict[str, Any]:
        return json.loads(self.workflow_path.read_text(encoding="utf-8"))

    def _upload_image(self, image_path: str) -> str:
        path = Path(image_path)
        with path.open("rb") as f:
            response = requests.post(
                f"{self.base_url}/upload/image",
                files={"image": (path.name, f)},
                data={"type": "input", "overwrite": "true"},
                timeout=60,
            )
        response.raise_for_status()
        data = response.json()
        return data.get("name") or data.get("filename") or path.name

    def _queue_prompt(self, prompt: dict[str, Any]) -> str:
        client_id = str(uuid.uuid4())
        response = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": prompt, "client_id": client_id},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI /prompt 响应缺少 prompt_id: {data}")
        return prompt_id

    def _wait_for_history(self, prompt_id: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout
        last_error = None
        while time.time() < deadline:
            response = requests.get(
                f"{self.base_url}/history/{prompt_id}",
                timeout=30,
            )
            if response.status_code >= 500:
                last_error = response.text
                time.sleep(self.poll_interval)
                continue
            response.raise_for_status()
            data = response.json()
            if prompt_id in data:
                return data[prompt_id]
            time.sleep(self.poll_interval)
        raise TimeoutError(f"等待 ComfyUI 任务超时: {prompt_id}; last_error={last_error}")

    def _download_output(self, output_info: dict[str, Any], output_path: str) -> None:
        params = {
            "filename": output_info["filename"],
            "subfolder": output_info.get("subfolder", ""),
            "type": output_info.get("type", "output"),
        }
        response = requests.get(f"{self.base_url}/view", params=params, timeout=120)
        response.raise_for_status()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
