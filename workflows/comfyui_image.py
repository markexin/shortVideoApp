from __future__ import annotations

import asyncio
import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from pipeline.image_generator import ImageGenerationRequest
from workflows.comfyui import pick_output_file


PLACEHOLDERS = {
    "__PROMPT__": "prompt",
    "__NEGATIVE_PROMPT__": "negative_prompt",
    "__OUTPUT_PREFIX__": "output_prefix",
    "__WIDTH__": "width",
    "__HEIGHT__": "height",
}


def apply_image_workflow_placeholders(
    workflow: dict[str, Any],
    prompt: str,
    negative_prompt: str,
    output_prefix: str,
    aspect_ratio: str,
) -> dict[str, Any]:
    width, height = _size_for_ratio(aspect_ratio)
    values = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "output_prefix": output_prefix,
        "width": width,
        "height": height,
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


def validate_image_workflow(workflow: dict[str, Any]) -> str | None:
    class_types = {
        str(node.get("class_type", ""))
        for node in workflow.values()
        if isinstance(node, dict)
    }
    note_text = "\n".join(
        str(node.get("inputs", {}).get("text", ""))
        for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type") == "Note"
    )
    if "not a runnable workflow" in note_text.lower():
        return "当前 JSON 不是可执行的文生图工作流，只是占位示例。请从 ComfyUI 导出 API 格式的真实生图工作流。"
    if "VHS_VideoCombine" in class_types or "LoadImage" in class_types and "__IMAGE_NAME__" in json.dumps(workflow):
        return "当前 JSON 更像图生视频/占位模板，不是可执行的文生图工作流。"
    if "__PROMPT__" not in json.dumps(workflow, ensure_ascii=False):
        return "图片工作流缺少 __PROMPT__ 占位符。"
    if "__OUTPUT_PREFIX__" not in json.dumps(workflow, ensure_ascii=False):
        return "图片工作流缺少 __OUTPUT_PREFIX__ 占位符。"
    return None


def _size_for_ratio(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "16:9":
        return 1280, 720
    return 1080, 1920


class ComfyUIImageAdapter:
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

    async def generate_image(self, request: ImageGenerationRequest) -> dict:
        return await asyncio.to_thread(self._generate_sync, request)

    def _generate_sync(self, request: ImageGenerationRequest) -> dict:
        try:
            workflow = json.loads(self.workflow_path.read_text(encoding="utf-8"))
            validation_error = validate_image_workflow(workflow)
            if validation_error:
                raise ValueError(validation_error)
            output_prefix = f"short_drama_image_{request.shot_id:03d}_{uuid.uuid4().hex[:8]}"
            prompt = apply_image_workflow_placeholders(
                workflow,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                output_prefix=output_prefix,
                aspect_ratio=request.aspect_ratio,
            )
            prompt_id = self._queue_prompt(prompt)
            history_entry = self._wait_for_history(prompt_id)
            output_info = pick_output_file(history_entry)
            self._download_output(output_info, request.output_path)
            return {
                "status": "success",
                "local_path": request.output_path,
                "provider": "comfyui_image",
                "metadata": {"prompt_id": prompt_id, "output": output_info},
            }
        except Exception as exc:
            return {"status": "failed", "error": str(exc), "provider": "comfyui_image"}

    def _queue_prompt(self, prompt: dict[str, Any]) -> str:
        response = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": prompt, "client_id": str(uuid.uuid4())},
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
        while time.time() < deadline:
            response = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=30)
            response.raise_for_status()
            data = response.json()
            if prompt_id in data:
                return data[prompt_id]
            time.sleep(self.poll_interval)
        raise TimeoutError(f"等待 ComfyUI 生图任务超时: {prompt_id}")

    def _download_output(self, output_info: dict[str, Any], output_path: str) -> None:
        response = requests.get(
            f"{self.base_url}/view",
            params={
                "filename": output_info["filename"],
                "subfolder": output_info.get("subfolder", ""),
                "type": output_info.get("type", "output"),
            },
            timeout=120,
        )
        response.raise_for_status()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
