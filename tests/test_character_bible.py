import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.character_bible import parse_characters_response, parse_visual_bible_response


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
