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


def test_visual_asset_generator_generates_each_character_variant(tmp_path):
    adapter = FakeImageAdapter()
    character = Character(
        name="林辰",
        description="same face anchor",
        variants=[
            {
                "name": "初期杂役",
                "story_stage": "第1-6集：觉醒前与刚觉醒的杂役阶段",
                "turnaround_prompt": "gray servant robe turnaround",
                "consistency_prompt": "same face, gray robe",
                "negative_prompt": "no black robe",
            },
            {
                "name": "觉醒药师",
                "story_stage": "第7-28集：炼丹大会成名至决战前",
                "turnaround_prompt": "black pharmacist robe turnaround",
                "consistency_prompt": "same face, black robe",
                "negative_prompt": "no gray robe",
            },
        ],
    )
    generator = VisualAssetImageGenerator(tmp_path, adapter=adapter)

    results = asyncio.run(
        generator.generate_characters(
            characters=[character],
            aspect_ratio="16:9",
            img_count=1,
        )
    )

    assert len(results) == 2
    assert "gray servant robe turnaround" in adapter.calls[0].prompt
    assert "black pharmacist robe turnaround" in adapter.calls[1].prompt
    assert adapter.calls[0].output_path.endswith("characters/001_林辰/01_初期杂役_第1-6集/turnaround.png")
    assert adapter.calls[1].output_path.endswith("characters/001_林辰/02_觉醒药师_第7-28集/turnaround.png")
    assert character.variants[0]["image_paths"]["turnaround"][0].endswith("turnaround.png")


def test_visual_asset_generator_can_generate_one_character_variant(tmp_path):
    adapter = FakeImageAdapter()
    character = Character(
        name="林辰",
        variants=[
            {"name": "初期杂役", "turnaround_prompt": "gray servant robe turnaround"},
            {"name": "觉醒药师", "turnaround_prompt": "black pharmacist robe turnaround"},
        ],
    )
    generator = VisualAssetImageGenerator(tmp_path, adapter=adapter)

    results = asyncio.run(
        generator.generate_characters(
            characters=[character],
            aspect_ratio="16:9",
            img_count=1,
            index=1,
            variant_index=2,
        )
    )

    assert len(results) == 1
    assert "black pharmacist robe turnaround" in adapter.calls[0].prompt
    assert adapter.calls[0].output_path.endswith("characters/001_林辰/02_觉醒药师/turnaround.png")
    assert "image_paths" not in character.variants[0]
    assert character.variants[1]["image_paths"]["turnaround"][0].endswith("turnaround.png")


def test_character_variant_prompt_stays_under_generation_prompt_limit():
    detailed_costume = " ".join(["silver-white robe embroidery, translucent golden soul particles"] * 25)
    character = Character(
        name="玄丹老祖",
        description="外貌60余岁，清瘦仙风道骨老者，长脸清癯，白眉垂肩，慈目细长，瞳色淡金半透明。"
        "鼻梁挺直，唇薄含笑，长须垂胸纯白如雪。银白长发披散无冠。穿白色宽袖长袍，暗绣丹炉图样，"
        "半透明残魂形态，边缘有金色光晕粒子飘散。",
        consistency_prompt="same face, same beard, same robe, same translucent quality",
        variants=[
            {
                "name": "残魂导师",
                "story_stage": "全剧主要形态",
                "description": "半透明残魂形态，白色宽袖长袍暗绣丹炉，银白披发，金色粒子边缘，慈祥而严苛。",
                "turnaround_prompt": "character turnaround reference sheet, front view, side view, back view, 60+ Chinese immortal elder, long thin kind face, white brows to shoulders, pale gold translucent eyes, long pure white beard, silver-white loose hair, white wide-sleeve robe with alchemy furnace embroidery, semi-transparent soul with golden particle edges, full body, delicate Chinese xianxia anime 3D game character design, "
                + detailed_costume,
                "consistency_prompt": "same exact base face, same facial proportions, same white brows and beard, same translucent soul body, same robe embroidery",
            }
        ],
    )

    prompt = VisualAssetImageGenerator._character_prompt(character, "turnaround", character.variants[0])

    assert len(prompt) <= 1900
    assert "残魂导师" in prompt
    assert "same exact base face" in prompt
