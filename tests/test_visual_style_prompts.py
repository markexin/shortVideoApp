import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.prompt_builder import build_image_prompt
from pipeline.visual_asset_image_generator import VisualAssetImageGenerator
from projects.schema import Character, Shot, VisualAsset


def test_shot_image_prompt_includes_xianxia_cg_reference_style():
    prompt = build_image_prompt(
        Shot(
            shot_id=1,
            scene_description="雪山剑台",
            action="少年拔剑",
            characters=["林辰"],
            image_prompt="close-up sword gesture",
        ),
        [Character(name="林辰", consistency_prompt="same young man, black high ponytail")],
        aspect_ratio="9:16",
    )

    assert "high-end xianxia fantasy CG" in prompt
    assert "glossy black hair" in prompt
    assert "soft blue-white lighting" in prompt
    assert "same young man" in prompt


def test_visual_asset_generator_wraps_character_prompt_with_reference_style():
    character = Character(name="林辰", turnaround_prompt="front side back views")

    prompt = VisualAssetImageGenerator._character_prompt(character, "turnaround")

    assert "high-end xianxia fantasy CG character design" in prompt
    assert "front side back views" in prompt
    assert "porcelain skin" in prompt


def test_visual_asset_generator_wraps_scene_prompt_with_reference_style():
    asset = VisualAsset(category="scene", name="山门", image_prompt="ancient sect gate")

    prompt = VisualAssetImageGenerator._asset_prompt(asset)

    assert "ethereal xianxia fantasy environment" in prompt
    assert "ancient sect gate" in prompt
    assert "soft blue-white mist" in prompt
