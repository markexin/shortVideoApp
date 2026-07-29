import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.script_writer import build_script_prompt


def test_build_script_prompt_contains_short_drama_constraints():
    prompt = build_script_prompt(
        premise="女主被老板羞辱后逆袭",
        genre="都市逆袭",
        platform="douyin",
        episode_count=3,
        seconds_per_episode=60,
    )

    assert "都市逆袭" in prompt
    assert "douyin" in prompt
    assert "3集" in prompt
    assert "60秒" in prompt
    assert "角色表" in prompt
    assert "结尾钩子" in prompt
