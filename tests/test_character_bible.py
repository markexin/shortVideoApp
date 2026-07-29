import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.character_bible import parse_characters_response


def test_parse_characters_response_maps_to_character_schema():
    raw = """
```json
{
  "characters": [
    {
      "name": "林晚",
      "description": "25岁女性，黑色长直发，鹅蛋脸，浅色职业套装",
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
