import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.terminal_input import normalize_prompt_text


def test_normalize_prompt_text_adds_leading_newline_for_command_prompt():
    assert normalize_prompt_text("> ") == "\n> "


def test_normalize_prompt_text_keeps_labeled_prompt():
    assert normalize_prompt_text("剧名: ") == "剧名: "
