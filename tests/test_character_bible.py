import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.character_bible import build_character_prompt, parse_characters_response, parse_visual_bible_response


def test_parse_characters_response_maps_to_character_schema():
    raw = """
```json
{
      "characters": [
    {
      "name": "林晚",
      "description": "25岁女性，黑色长直发，鹅蛋脸，浅色职业套装",
      "style_prompt": "modern short drama, realistic cinematic style",
      "turnaround_prompt": "character turnaround sheet, front side back views",
      "consistency_prompt": "same woman, long straight black hair, oval face, beige suit",
      "negative_prompt": "no short hair, no curly hair, no age change"
    }
  ]
}
```
"""

    characters = parse_characters_response(raw)

    assert len(characters) == 1
    assert characters[0].name == "林晚"
    assert "黑色长直发" in characters[0].description
    assert "same woman" in characters[0].consistency_prompt
    assert "no short hair" in characters[0].negative_prompt


def test_build_character_prompt_requires_chinese_three_view_character_board_format():
    prompt = build_character_prompt("虞清商抱琴出场", aspect_ratio="16:9")

    assert "3D国风动漫，仙侠风格，单人角色设定图" in prompt
    assert "画面从左到右：正面全身、侧面全身、背面全身、面部特写" in prompt
    assert "中文标注名字「角色名」" in prompt
    assert "先确认项目题材与角色定位，再选择对应风格" in prompt
    assert "turnaround_prompt 必须优先使用中文" in prompt


def test_build_character_prompt_distinguishes_turnaround_board_from_single_view_prompts():
    prompt = build_character_prompt("虞清商抱琴出场", aspect_ratio="9:16")

    assert "turnaround_prompt 必须生成一张单人多视图角色设定板" in prompt
    assert "同一张图片内同时包含正面全身、侧面全身、背面全身、面部特写" in prompt
    assert "front_view_prompt、side_view_prompt、back_view_prompt 是单独角度参考图" in prompt
    assert "不要把 turnaround_prompt 写成单张正面图、剧情镜头或普通肖像" in prompt


def test_build_character_prompt_limits_generated_prompt_field_length():
    prompt = build_character_prompt("虞清商抱琴出场", aspect_ratio="9:16")

    assert "所有 prompt 字段必须控制在 200-300 字" in prompt
    assert "任何单个 prompt 字段不得超过 300 字" in prompt


def test_parse_visual_bible_response_maps_characters_scenes_and_props():
    raw = """
{
  "characters": [
    {
      "name": "林辰",
      "description": "18岁清瘦少年，黑色短发束起，灰色杂役袍，胸口药葫芦印记",
      "style_prompt": "xianxia short drama, cinematic, realistic fantasy costume",
      "turnaround_prompt": "full body character turnaround sheet, front view, side view, back view, same face and outfit",
      "front_view_prompt": "front view, Lin Chen, gray servant robe, medicine gourd mark",
      "side_view_prompt": "side view, Lin Chen, same face, same robe",
      "back_view_prompt": "back view, Lin Chen, tied black hair, gray robe",
      "consistency_prompt": "same young man, tied black hair, gray servant robe, medicine gourd chest mark",
      "negative_prompt": "no face drift, no outfit drift"
    }
  ],
  "scenes": [
    {
      "name": "青云宗青石台阶",
      "description": "仙门山门前的宽阔青石台阶，云雾、牌坊、远处深渊黑雾",
      "style_prompt": "xianxia sect gate, cinematic vertical short drama",
      "image_prompt": "wide establishing shot of xianxia sect stone stairs, mist, gate arch, dark abyss fog in background",
      "negative_prompt": "modern city, cars, text watermark"
    }
  ],
  "props": [
    {
      "name": "裂纹废丹",
      "description": "灰色布满裂纹的废丹，表面有暗淡金纹",
      "style_prompt": "macro fantasy prop, cinematic lighting",
      "image_prompt": "macro shot of cracked gray elixir pill with faint golden veins",
      "negative_prompt": "plastic, modern capsule, text"
    }
  ]
}
"""

    bible = parse_visual_bible_response(raw)

    assert bible.characters[0].name == "林辰"
    assert "turnaround sheet" in bible.characters[0].turnaround_prompt
    assert bible.scenes[0].category == "scene"
    assert "青石台阶" in bible.scenes[0].description
    assert bible.props[0].category == "prop"
    assert "cracked gray elixir" in bible.props[0].image_prompt


def test_parse_visual_bible_response_maps_character_variants():
    raw = """
{
  "characters": [
    {
      "name": "林辰",
      "description": "18岁清瘦少年，同一张脸，黑发低马尾",
      "consistency_prompt": "same angular jaw, same dark eyes, same low ponytail",
      "negative_prompt": "no face drift",
      "variants": [
        {
          "name": "初期杂役",
          "story_stage": "第1-6集",
          "description": "灰色粗布杂役袍，麻绳腰带，胸口药葫芦印记暗淡",
          "turnaround_prompt": "turnaround sheet, gray servant robe",
          "front_view_prompt": "front view, gray servant robe",
          "side_view_prompt": "side view, gray servant robe",
          "back_view_prompt": "back view, gray servant robe",
          "consistency_prompt": "same face, gray servant robe, dim medicine gourd mark",
          "negative_prompt": "no black robe"
        },
        {
          "name": "觉醒药师",
          "story_stage": "第7集以后",
          "description": "黑色药师袍，暗红滚边，药葫芦印记发光",
          "turnaround_prompt": "turnaround sheet, black pharmacist robe",
          "front_view_prompt": "front view, black pharmacist robe",
          "side_view_prompt": "side view, black pharmacist robe",
          "back_view_prompt": "back view, black pharmacist robe",
          "consistency_prompt": "same face, black pharmacist robe, glowing medicine gourd mark",
          "negative_prompt": "no gray servant robe"
        }
      ]
    }
  ]
}
"""

    bible = parse_visual_bible_response(raw)

    assert len(bible.characters[0].variants) == 2
    assert bible.characters[0].variants[0].name == "初期杂役"
    assert "gray servant robe" in bible.characters[0].variants[0].turnaround_prompt
    assert "black pharmacist robe" in bible.characters[0].variants[1].front_view_prompt


def test_parse_visual_bible_response_clamps_generated_prompt_fields_to_300_chars():
    long_prompt = "仙侠角色设定" * 80
    raw = f"""
{{
  "characters": [
    {{
      "name": "林辰",
      "description": "18岁清瘦少年",
      "turnaround_prompt": "{long_prompt}",
      "front_view_prompt": "{long_prompt}",
      "consistency_prompt": "{long_prompt}",
      "negative_prompt": "{long_prompt}",
      "variants": [
        {{
          "name": "初期杂役",
          "turnaround_prompt": "{long_prompt}",
          "negative_prompt": "{long_prompt}"
        }}
      ]
    }}
  ],
  "scenes": [
    {{
      "name": "青云宗",
      "description": "宗门大殿",
      "style_prompt": "{long_prompt}",
      "image_prompt": "{long_prompt}",
      "negative_prompt": "{long_prompt}"
    }}
  ],
  "props": [
    {{
      "name": "废丹",
      "description": "裂纹灰丹",
      "image_prompt": "{long_prompt}"
    }}
  ]
}}
"""

    bible = parse_visual_bible_response(raw)
    character = bible.characters[0]

    assert len(character.turnaround_prompt) == 300
    assert len(character.front_view_prompt) == 300
    assert len(character.consistency_prompt) == 300
    assert len(character.negative_prompt) == 300
    assert len(character.variants[0].turnaround_prompt) == 300
    assert len(character.variants[0].negative_prompt) == 300
    assert len(bible.scenes[0].style_prompt) == 300
    assert len(bible.scenes[0].image_prompt) == 300
    assert len(bible.scenes[0].negative_prompt) == 300
    assert len(bible.props[0].image_prompt) == 300
    assert character.description == "18岁清瘦少年"
