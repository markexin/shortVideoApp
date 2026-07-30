from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pipeline.prompt_builder import build_image_prompt
from projects.schema import Character, Shot


@dataclass(frozen=True)
class ImageGenerationRequest:
    shot_id: int
    prompt: str
    negative_prompt: str
    aspect_ratio: str
    output_path: str
    img_count: int = 1
    width: int | None = None
    height: int | None = None


class ImageAdapter(Protocol):
    async def generate_image(self, request: ImageGenerationRequest):
        """Generate one image for a storyboard shot."""


class ShotImageGenerator:
    def __init__(self, output_dir: str | Path, adapter: ImageAdapter, img_count: int = 1):
        self.output_dir = Path(output_dir)
        self.adapter = adapter
        self.img_count = img_count

    async def generate_all(
        self,
        shots: list[Shot],
        characters: list[Character],
        aspect_ratio: str,
    ) -> list[dict]:
        tasks = [
            self._generate_one(shot, characters, aspect_ratio)
            for shot in shots
            if not shot.image_path
        ]
        if not tasks:
            return []
        return await asyncio.gather(*tasks)

    async def _generate_one(
        self,
        shot: Shot,
        characters: list[Character],
        aspect_ratio: str,
    ) -> dict:
        output_path = self.output_dir / f"shot_{shot.shot_id:03d}.png"
        prompt = build_image_prompt(shot, characters, aspect_ratio=aspect_ratio)
        request = ImageGenerationRequest(
            shot_id=shot.shot_id,
            prompt=prompt,
            negative_prompt=shot.negative_prompt,
            aspect_ratio=aspect_ratio,
            output_path=str(output_path),
            img_count=self.img_count,
        )
        result = await self.adapter.generate_image(request)
        if result.get("status") == "success":
            shot.image_path = result.get("local_path") or str(output_path)
            shot.status = "image_ready"
        else:
            shot.status = "image_failed"
        return result
