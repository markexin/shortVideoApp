"""Stage 2: image-path based video generation through a pluggable workflow."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import config
from pipeline.storyboard import _extract_scene_name
from workflows.base import WorkflowAdapter, WorkflowRequest
from workflows.comfyui import ComfyUIWorkflowAdapter
from workflows.http_workflow import HTTPWorkflowAdapter


@dataclass
class ShotResult:
    shot_id: int
    status: str = "pending"
    local_path: Optional[str] = None
    last_frame_url: Optional[str] = None
    character_ref_path: Optional[str] = None
    quality_score: int = 0
    model_used: str = ""
    resolution_used: str = ""
    attempts: int = 0
    errors: list[str] = field(default_factory=list)


class MissingWorkflowAdapter:
    async def generate_shot(self, request: WorkflowRequest):
        raise RuntimeError(
            "未配置视频生成工作流。请设置 WORKFLOW_ENDPOINT，或在代码中传入 WorkflowAdapter。"
        )


class VideoGenerator:
    """Generate storyboard shots using user-provided images and a workflow adapter."""

    def __init__(
        self,
        output_dir: str | Path,
        workflow: WorkflowAdapter | None = None,
        max_concurrency: int | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "shots").mkdir(exist_ok=True)
        (self.output_dir / "character_refs").mkdir(exist_ok=True)
        self.character_refs: dict[str, str] = {}
        self.workflow = workflow or self._build_default_workflow()
        self.max_concurrency = max_concurrency or config.MAX_CONCURRENT_GENERATIONS

    async def generate_all(self, storyboard: dict) -> list[ShotResult]:
        shots = storyboard["shots"]
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def run_one(index: int, shot: dict) -> tuple[int, ShotResult]:
            async with semaphore:
                prev_shot = shots[index - 1] if index > 0 else None
                return index, await self._generate_single_shot(shot, prev_shot, storyboard)

        tasks = [asyncio.create_task(run_one(i, shot)) for i, shot in enumerate(shots)]
        results: list[ShotResult | None] = [None] * len(shots)
        for task in asyncio.as_completed(tasks):
            index, result = await task
            results[index] = result
        return [r for r in results if r is not None]

    async def _generate_single_shot(
        self,
        shot: dict,
        prev_shot: Optional[dict],
        storyboard: dict,
    ) -> ShotResult:
        result = ShotResult(shot_id=shot["shot_id"])
        output_path = self.output_dir / "shots" / f"shot_{shot['shot_id']:03d}.mp4"

        if output_path.exists() and output_path.stat().st_size > 0:
            result.status = "success"
            result.local_path = str(output_path)
            result.model_used = "cached"
            return result

        image_path = shot.get("image_path") or shot.get("source_image")
        if not image_path:
            result.status = "failed"
            result.errors.append("缺少图片路径，请先为该分镜提供 image_path")
            return result

        if not Path(image_path).exists():
            result.status = "failed"
            result.errors.append(f"图片不存在: {image_path}")
            return result

        prompt = self._build_video_prompt(shot, prev_shot, storyboard)
        request = WorkflowRequest(
            shot_id=shot["shot_id"],
            image_path=str(image_path),
            prompt=prompt,
            negative_prompt=shot.get("negative_prompt", ""),
            duration=float(shot.get("duration", config.DEFAULT_DURATION)),
            aspect_ratio=storyboard.get("aspect_ratio", config.DEFAULT_RATIO),
            output_path=str(output_path),
            metadata={
                "characters": shot.get("characters", []),
                "scene_description": shot.get("scene_description", ""),
                "subtitle_text": shot.get("subtitle_text", ""),
            },
        )

        result.attempts = 1
        try:
            workflow_result = await self.workflow.generate_shot(request)
        except Exception as exc:
            result.status = "failed"
            result.errors.append(str(exc))
            return result

        if workflow_result.status not in {"success", "succeeded"}:
            result.status = "failed"
            result.errors.append(workflow_result.error or "工作流生成失败")
            result.model_used = workflow_result.provider
            return result

        local_path = workflow_result.local_path or str(output_path)
        if not Path(local_path).exists():
            result.status = "failed"
            result.errors.append(f"工作流未产出本地视频: {local_path}")
            result.model_used = workflow_result.provider
            return result

        result.status = "success"
        result.local_path = local_path
        result.model_used = workflow_result.provider
        result.quality_score = 100
        return result

    def _build_video_prompt(
        self,
        shot: dict,
        prev_shot: Optional[dict],
        storyboard: dict,
    ) -> str:
        prompt = shot.get("video_prompt") or shot.get("prompt_en") or shot.get("prompt") or ""
        prompt = self._inject_character_description(prompt, shot, storyboard)
        prompt = self._inject_scene_continuity(prompt, shot, prev_shot)
        return prompt

    @staticmethod
    def _build_default_workflow() -> WorkflowAdapter:
        if getattr(config, "WORKFLOW_PROVIDER", "") == "comfyui":
            workflow_path = getattr(config, "COMFYUI_WORKFLOW_PATH", "")
            if workflow_path:
                return ComfyUIWorkflowAdapter(
                    base_url=config.COMFYUI_BASE_URL,
                    workflow_path=workflow_path,
                    timeout=config.GENERATION_TIMEOUT,
                )
            return MissingWorkflowAdapter()

        endpoint = getattr(config, "WORKFLOW_ENDPOINT", "")
        if endpoint:
            return HTTPWorkflowAdapter(endpoint, timeout=config.GENERATION_TIMEOUT)
        return MissingWorkflowAdapter()

    @staticmethod
    def _shot_has_character(shot: dict) -> bool:
        return bool(
            shot.get("extract_character_ref")
            or shot.get("characters")
            or shot.get("has_character")
        )

    def _build_image_refs(
        self,
        shot: dict,
        prev_last_frame: Optional[str],
    ) -> tuple[list[str], Optional[str]]:
        """Legacy helper kept for existing reference-selection tests."""
        shot_chars = shot.get("characters", [])
        char_ref_paths = []
        for char_name in shot_chars:
            if char_name in self.character_refs:
                path = self.character_refs[char_name]
                if os.path.isfile(path):
                    char_ref_paths.append(path)

        if char_ref_paths:
            refs = list(char_ref_paths)
            if prev_last_frame and not os.path.isfile(prev_last_frame):
                refs.append(prev_last_frame)
            return refs, "reference_image"

        if prev_last_frame and not os.path.isfile(prev_last_frame):
            return [prev_last_frame], "first_frame"

        return [], None

    def _inject_character_description(
        self,
        prompt: str,
        shot: dict,
        storyboard: dict,
    ) -> str:
        characters = storyboard.get("characters", [])
        shot_chars = shot.get("characters", [])
        if not characters or not shot_chars:
            return prompt

        char_descs = []
        for char in characters:
            if char.get("name") in shot_chars and char.get("description"):
                char_descs.append(f'{char["name"]}: {char["description"]}')

        if char_descs:
            desc_block = "; ".join(char_descs)
            return f"[Character consistency: {desc_block}] {prompt}"

        return prompt

    @staticmethod
    def _inject_scene_continuity(
        prompt: str,
        current_shot: dict,
        prev_shot: Optional[dict],
    ) -> str:
        if prev_shot is None:
            return prompt

        prev_scene = _extract_scene_name(prev_shot.get("scene_description", ""))
        curr_scene = _extract_scene_name(current_shot.get("scene_description", ""))
        if prev_scene != curr_scene:
            return prompt

        continuity_parts: list[str] = []
        prev_lighting = prev_shot.get("lighting", "")
        if prev_lighting:
            continuity_parts.append(f"maintaining {' '.join(prev_lighting.split()[:5])}")

        prev_props = {p.lower().strip() for p in prev_shot.get("key_props", [])}
        curr_props = {p.lower().strip() for p in current_shot.get("key_props", [])}
        shared_props = prev_props & curr_props
        if shared_props:
            continuity_parts.append(f"{', '.join(list(shared_props)[:3])} still present")

        if not continuity_parts:
            return prompt

        return f"[Scene continuity: {'; '.join(continuity_parts)}] {prompt}"
