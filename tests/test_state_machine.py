import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.state_machine import available_actions, can_transition, next_step


def test_state_machine_allows_linear_flow():
    assert can_transition("script_confirm", "script_confirmed")
    assert next_step("script_confirmed") == "characters_ready"


def test_state_machine_rejects_skipping_to_episode_ready():
    assert not can_transition("script_confirm", "episode_ready")


def test_available_actions_for_script_confirm():
    actions = available_actions("script_confirm")

    assert actions[0].command_name == "show_script"
    assert actions[1].command_name == "confirm_script"
    assert "确认脚本" in actions[1].label


def test_available_actions_for_storyboard_ready():
    actions = available_actions("storyboard_ready")

    command_names = [action.command_name for action in actions]
    assert "export_image_prompts" in command_names
    assert "prepare_video_segment" in command_names
    assert "show_video_segment_payload" in command_names
    assert "generate_video_segment" in command_names
    assert "status" in command_names
