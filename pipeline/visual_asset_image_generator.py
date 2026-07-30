from __future__ import annotations

import asyncio
import re
from pathlib import Path

from pipeline.image_generator import ImageAdapter, ImageGenerationRequest
from pipeline.visual_style import with_reference_negative, with_reference_style
from projects.schema import Character, VisualAsset


class VisualAssetImageGenerator:
    def __init__(self, output_dir: str | Path, adapter: ImageAdapter):
        self.output_dir = Path(output_dir)
        self.adapter = adapter

    async def generate_characters(
        self,
        characters: list[Character],
        aspect_ratio: str,
        limit: int | None = None,
        index: int | None = None,
        img_count: int = 1,
        view: str = "turnaround",
    ) -> list[dict]:
        selected = self._select(characters, limit=limit, index=index)
        tasks = [
            self._generate_character(order, character, aspect_ratio, img_count, view)
            for order, character in selected
        ]
        return await asyncio.gather(*tasks) if tasks else []

    async def generate_assets(
        self,
        assets: list[VisualAsset],
        category: str,
        aspect_ratio: str,
        limit: int | None = None,
        index: int | None = None,
        img_count: int = 1,
    ) -> list[dict]:
        selected_assets = [asset for asset in assets if asset.category == category]
        selected = self._select(selected_assets, limit=limit, index=index)
        tasks = [
            self._generate_asset(order, asset, aspect_ratio, img_count)
            for order, asset in selected
        ]
        return await asyncio.gather(*tasks) if tasks else []

    async def _generate_character(
        self,
        order: int,
        character: Character,
        aspect_ratio: str,
        img_count: int,
        view: str,
    ) -> dict:
        prompt = self._character_prompt(character, view)
        output_path = (
            self.output_dir
            / "characters"
            / f"{order:03d}_{safe_name(character.name)}"
            / f"{view}.png"
        )
        request = ImageGenerationRequest(
            shot_id=order,
            prompt=prompt,
            negative_prompt=with_reference_negative(character.negative_prompt),
            aspect_ratio=aspect_ratio,
            output_path=str(output_path),
            img_count=img_count,
        )
        result = await self.adapter.generate_image(request)
        if result.get("status") == "success":
            character.image_paths[view] = result.get("local_paths") or [result.get("local_path")]
        return result

    async def _generate_asset(
        self,
        order: int,
        asset: VisualAsset,
        aspect_ratio: str,
        img_count: int,
    ) -> dict:
        plural = "scenes" if asset.category == "scene" else "props"
        output_path = self.output_dir / plural / f"{order:03d}_{safe_name(asset.name)}.png"
        request = ImageGenerationRequest(
            shot_id=order,
            prompt=self._asset_prompt(asset),
            negative_prompt=with_reference_negative(asset.negative_prompt),
            aspect_ratio=aspect_ratio,
            output_path=str(output_path),
            img_count=img_count,
        )
        result = await self.adapter.generate_image(request)
        if result.get("status") == "success":
            asset.image_paths = result.get("local_paths") or [result.get("local_path")]
        return result

    @staticmethod
    def _character_prompt(character: Character, view: str) -> str:
        prompts = {
            "turnaround": character.turnaround_prompt,
            "front": character.front_view_prompt,
            "side": character.side_view_prompt,
            "back": character.back_view_prompt,
        }
        prompt = prompts.get(view) or character.turnaround_prompt or character.style_prompt or character.description
        return with_reference_style(prompt, category="character")

    @staticmethod
    def _asset_prompt(asset: VisualAsset) -> str:
        prompt = asset.image_prompt or asset.style_prompt or asset.description
        return with_reference_style(prompt, category=asset.category)

    @staticmethod
    def _select(items: list, limit: int | None = None, index: int | None = None) -> list[tuple[int, object]]:
        numbered = list(enumerate(items, start=1))
        if index is not None:
            return [(order, item) for order, item in numbered if order == index]
        if limit is not None:
            return numbered[: max(0, limit)]
        return numbered


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\\s]+", "_", name.strip())
    return cleaned.strip("_") or "asset"
