import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.visual_asset_image_generator import VisualAssetImageGenerator
from projects.schema import Character, VisualAsset


class FakeImageAdapter:
    def __init__(self):
        self.calls = []

    async def generate_image(self, request):
        self.calls.append(request)
        path = Path(request.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
        return {"status": "success", "local_path": str(path), "local_paths": [str(path)]}


def test_visual_asset_generator_limits_character_count_and_binds_paths(tmp_path):
    adapter = FakeImageAdapter()
    characters = [
        Character(name="甲", turnaround_prompt="turnaround A", negative_prompt="bad"),
        Character(name="乙", turnaround_prompt="turnaround B"),
        Character(name="丙", turnaround_prompt="turnaround C"),
    ]
    generator = VisualAssetImageGenerator(tmp_path, adapter=adapter)

    results = asyncio.run(
        generator.generate_characters(
            characters=characters,
            aspect_ratio="9:16",
            limit=2,
            img_count=1,
        )
    )

    assert len(results) == 2
    assert len(adapter.calls) == 2
    assert "turnaround A" in adapter.calls[0].prompt
    assert "high-end xianxia fantasy CG character design" in adapter.calls[0].prompt
    assert "bad" in adapter.calls[0].negative_prompt
    assert "western medieval style" in adapter.calls[0].negative_prompt
    assert adapter.calls[0].output_path.endswith("characters/001_甲/turnaround.png")
    assert characters[0].image_paths["turnaround"][0].endswith("turnaround.png")
    assert characters[2].image_paths == {}


def test_visual_asset_generator_can_generate_one_scene_by_index(tmp_path):
    adapter = FakeImageAdapter()
    scenes = [
        VisualAsset(category="scene", name="山门", image_prompt="gate"),
        VisualAsset(category="scene", name="丹房", image_prompt="room"),
    ]
    generator = VisualAssetImageGenerator(tmp_path, adapter=adapter)

    results = asyncio.run(
        generator.generate_assets(
            assets=scenes,
            category="scene",
            aspect_ratio="16:9",
            index=2,
            img_count=1,
        )
    )

    assert len(results) == 1
    assert "room" in adapter.calls[0].prompt
    assert "ethereal xianxia fantasy environment" in adapter.calls[0].prompt
    assert adapter.calls[0].aspect_ratio == "16:9"
    assert scenes[0].image_paths == []
    assert scenes[1].image_paths[0].endswith("scenes/002_丹房.png")
