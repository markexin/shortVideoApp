import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.drama_storyboard import parse_storyboard_response


def test_parse_storyboard_response_maps_to_shots():
    raw = """
{
  "shots": [
    {
      "shot_id": 1,
      "scene_description": "办公室门口",
      "action": "林晚被老板当众羞辱",
      "characters": ["林晚", "周总"],
      "dialogue": "你以为你是谁？",
      "image_prompt": "vertical medium shot, office doorway, tense confrontation",
      "video_prompt": "slow push-in, tense short drama rhythm",
      "negative_prompt": "no face drift",
      "duration": 5
    }
  ]
}
"""

    shots = parse_storyboard_response(raw)

    assert len(shots) == 1
    assert shots[0].shot_id == 1
    assert shots[0].characters == ["林晚", "周总"]
    assert "office doorway" in shots[0].image_prompt
    assert "slow push-in" in shots[0].video_prompt
    assert shots[0].duration == 5
