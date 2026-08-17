from __future__ import annotations

import asyncio
import re
from pathlib import Path

from pipeline.image_generator import ImageAdapter, ImageGenerationRequest
from pipeline.visual_style import (
    character_view_board_prompt,
    compact_character_identity_lock,
    with_reference_negative,
    with_reference_style,
)
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
        variant_index: int | None = None,
        img_count: int = 1,
        view: str = "turnaround",
        width: int | None = None,
        height: int | None = None,
    ) -> list[dict]:
        selected = self._select(characters, limit=limit, index=index)
        tasks = [
            task
            for order, character in selected
            for task in self._character_tasks(order, character, aspect_ratio, img_count, view, width, height, variant_index)
        ]
        return await asyncio.gather(*tasks) if tasks else []

    def _character_tasks(
        self,
        order: int,
        character: Character,
        aspect_ratio: str,
        img_count: int,
        view: str,
        width: int | None,
        height: int | None,
        variant_index: int | None,
    ) -> list:
        if not character.variants:
            return [self._generate_character(order, character, None, 0, aspect_ratio, img_count, view, width, height)]
        variants = list(enumerate(character.variants, start=1))
        if variant_index is not None:
            variants = [(order, variant) for order, variant in variants if order == variant_index]
        return [
            self._generate_character(order, character, variant, variant_index, aspect_ratio, img_count, view, width, height)
            for variant_index, variant in variants
        ]

    async def generate_assets(
        self,
        assets: list[VisualAsset],
        category: str,
        aspect_ratio: str,
        limit: int | None = None,
        index: int | None = None,
        img_count: int = 1,
        width: int | None = None,
        height: int | None = None,
    ) -> list[dict]:
        selected_assets = [asset for asset in assets if asset.category == category]
        selected = self._select(selected_assets, limit=limit, index=index)
        tasks = [
            self._generate_asset(order, asset, aspect_ratio, img_count, width, height)
            for order, asset in selected
        ]
        return await asyncio.gather(*tasks) if tasks else []

    async def _generate_character(
        self,
        order: int,
        character: Character,
        variant: dict | None,
        variant_index: int,
        aspect_ratio: str,
        img_count: int,
        view: str,
        width: int | None,
        height: int | None,
    ) -> dict:
        prompt = self._character_prompt(character, view, variant=variant)
        character_dir = self.output_dir / "characters" / f"{order:03d}_{safe_name(character.name)}"
        if variant:
            character_dir = character_dir / f"{variant_index:02d}_{safe_name(_variant_dir_name(variant))}"
        output_path = character_dir / f"{view}.png"
        request = ImageGenerationRequest(
            shot_id=order,
            prompt=prompt,
            negative_prompt=with_reference_negative(self._character_negative_prompt(character, variant)),
            aspect_ratio=aspect_ratio,
            output_path=str(output_path),
            img_count=img_count,
            width=width,
            height=height,
        )
        result = await self.adapter.generate_image(request)
        if result.get("status") == "success":
            if variant is not None:
                _variant_image_paths(variant)[view] = result.get("local_paths") or [result.get("local_path")]
            else:
                character.image_paths[view] = result.get("local_paths") or [result.get("local_path")]
        return result

    async def _generate_asset(
        self,
        order: int,
        asset: VisualAsset,
        aspect_ratio: str,
        img_count: int,
        width: int | None,
        height: int | None,
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
            width=width,
            height=height,
        )
        result = await self.adapter.generate_image(request)
        if result.get("status") == "success":
            asset.image_paths = result.get("local_paths") or [result.get("local_path")]
        return result

    @staticmethod
    def _character_prompt(character: Character, view: str, variant: dict | None = None) -> str:
        source = variant
        prompts = {
            "turnaround": _variant_get(source, "turnaround_prompt") or character.turnaround_prompt,
            "front": _variant_get(source, "front_view_prompt") or character.front_view_prompt,
            "side": _variant_get(source, "side_view_prompt") or character.side_view_prompt,
            "back": _variant_get(source, "back_view_prompt") or character.back_view_prompt,
        }
        prompt = prompts.get(view) or character.turnaround_prompt or character.style_prompt or character.description
        board_prompt = character_view_board_prompt(
            character_name=character.name,
            prompt=prompt,
            description=character.description,
            view=view,
        )
        variant_description = _variant_get(source, "description")
        variant_consistency = _variant_get(source, "consistency_prompt")
        locked_prompt = " ".join(
            [
                f"Variant: {_variant_get(source, 'name')}. Story stage: {_variant_get(source, 'story_stage')}." if source else "",
                board_prompt,
                f"Variant-specific visual anchor: {variant_description}" if variant_description else "",
                compact_character_identity_lock(
                    character_name=character.name,
                    description=character.description,
                    consistency_prompt="; ".join(
                        part for part in [character.consistency_prompt, variant_consistency] if part
                    ),
                ),
            ]
        )
        return _clip_generation_prompt(with_reference_style(locked_prompt, category="character"))

    @staticmethod
    def _character_negative_prompt(character: Character, variant: dict | None = None) -> str:
        parts = [character.negative_prompt]
        if variant:
            parts.append(str(_variant_get(variant, "negative_prompt", "")))
        return ", ".join(part for part in parts if part)

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


def _variant_get(variant, key: str, default: str = ""):
    if variant is None:
        return default
    if isinstance(variant, dict):
        return variant.get(key, default)
    return getattr(variant, key, default)


def _variant_dir_name(variant) -> str:
    name = str(_variant_get(variant, "name", "variant"))
    story_stage = str(_variant_get(variant, "story_stage", ""))
    match = re.search(r"第\s*\d+\s*[-至到—~～]\s*\d+\s*集", f"{name} {story_stage}")
    if not match:
        match = re.search(r"第\s*\d+\s*集(?:以后|之后|起)?", f"{name} {story_stage}")
    if not match:
        return name
    stage = re.sub(r"\s+", "", match.group(0))
    return f"{name}_{stage}" if stage not in name else name


def _variant_image_paths(variant) -> dict[str, list[str]]:
    if isinstance(variant, dict):
        return variant.setdefault("image_paths", {})
    if not getattr(variant, "image_paths", None):
        variant.image_paths = {}
    return variant.image_paths


def _clip_generation_prompt(prompt: str, max_chars: int = 1900) -> str:
    if len(prompt) <= max_chars:
        return prompt
    head_chars = max_chars - 650
    tail_chars = 620
    return f"{prompt[:head_chars].rstrip()} ... {prompt[-tail_chars:].lstrip()}"
