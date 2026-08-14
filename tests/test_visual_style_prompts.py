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
    character = Character(
        name="林辰",
        description="18 year old Chinese male, angular jaw, black half-tied ponytail, gray robe",
        turnaround_prompt="front side back views",
        consistency_prompt="same angular jaw, same black half-tied ponytail, same gray robe",
    )

    prompt = VisualAssetImageGenerator._character_prompt(character, "turnaround")

    assert "high-end xianxia fantasy CG character design" in prompt
    assert "front side back views" in prompt
    assert "porcelain skin" in prompt
    assert "STRICT CHARACTER IDENTITY LOCK" in prompt
    assert "same angular jaw" in prompt
    assert "Do not redesign the character between views" in prompt
    assert len(prompt) <= 1900


def test_character_turnaround_prompt_is_expanded_to_chinese_three_view_sheet():
    character = Character(
        name="虞清商",
        description="青年女性乐修仙君，25岁左右，凤眸微垂，瞳色如琉璃清透微紫，墨黑长发及膝，月白渐变淡紫广袖纱袍，怀抱焦桐古琴。",
        turnaround_prompt="仙侠乐修角色设定",
        consistency_prompt="same elegant face, same translucent purple eyes, same long black hair, same pale purple hanfu, same guqin",
    )

    prompt = VisualAssetImageGenerator._character_prompt(character, "turnaround")

    assert "3D国风动漫，仙侠风格，单人角色设定图" in prompt
    assert "高精度人物三视图设定板" in prompt
    assert "画面从左到右：正面全身、侧面全身、背面全身、面部特写" in prompt
    assert "中文标注名字「虞清商」" in prompt
    assert "次世代PBR材质渲染" in prompt
    assert "same elegant face" in prompt
    assert len(prompt) <= 1900


def test_shot_prompt_includes_strict_identity_lock_for_characters():
    prompt = build_image_prompt(
        Shot(
            shot_id=2,
            scene_description="药谷",
            action="林辰回头",
            characters=["林辰"],
            image_prompt="medium close-up",
        ),
        [
            Character(
                name="林辰",
                description="18 year old Chinese male, angular jaw, black half-tied ponytail, gray robe",
                consistency_prompt="same angular jaw, same black half-tied ponytail, same gray robe",
            )
        ],
        aspect_ratio="9:16",
    )

    assert "STRICT CHARACTER IDENTITY LOCK" in prompt
    assert "same angular jaw" in prompt
    assert "same skull structure" in prompt


def test_character_prompt_stays_under_generation_prompt_limit_for_long_identity():
    character = Character(
        name="林辰（主角·废灵根杂役→药神体觉醒者）",
        description=(
            "18-20岁清瘦少年，棱角分明的长脸，浓黑剑眉，眼窝略深，瞳色深褐透倔强光芒。"
            "黑色短发齐耳后半束起低马尾，额前有几缕碎发。初期穿灰色粗布杂役袍，袖口扎紧，腰系麻绳；"
            "觉醒后换黑色药师袍，立领宽袖，暗红滚边，腰束黑色皮质束带，左胸口处有一枚药葫芦形印记。"
            "身形清瘦但肌肉线条紧实，皮肤偏冷白，常带伤疤与灰尘。气质隐忍、机敏。"
        ),
        turnaround_prompt=(
            "Character turnaround sheet of a slim 18-20 year old Chinese male cultivator, same face, hair and outfit "
            "across all views. Front view, three-quarter left view, side profile left, three-quarter right view, back view. "
            "Black short hair half tied in low ponytail, gray coarse cloth servant robe with rope belt, slim athletic build, "
            "angular jaw, deep-set determined dark brown eyes, prominent brow. White neutral background, full body."
        ),
        consistency_prompt=(
            "Slim 18-20 year old Chinese male, angular jaw, deep-set determined dark brown eyes, prominent brow, "
            "black short hair half-tied in low ponytail with loose forehead strands, slim athletic build. "
            "Gray coarse cloth servant robe or black pharmacist robe with dark red trim and leather belt. "
            "Left chest medicine gourd mark visible. Same face shape, same eye color, same hairstyle, same age."
        ),
    )

    prompt = VisualAssetImageGenerator._character_prompt(character, "turnaround")

    assert len(prompt) <= 1900
    assert "STRICT CHARACTER IDENTITY LOCK" in prompt
    assert "same skull structure" in prompt


def test_visual_asset_generator_wraps_scene_prompt_with_reference_style():
    asset = VisualAsset(category="scene", name="山门", image_prompt="ancient sect gate")

    prompt = VisualAssetImageGenerator._asset_prompt(asset)

    assert "ethereal xianxia fantasy environment" in prompt
    assert "ancient sect gate" in prompt
    assert "soft blue-white mist" in prompt
