import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.commands import parse_command, parse_contextual_command


def test_parse_global_navigation_commands():
    assert parse_command("首页").name == "home"
    assert parse_command("返回").name == "back"
    assert parse_command("继续").name == "continue"


def test_parse_generation_commands_with_shot_number():
    command = parse_command("生成第3镜")
    assert command.name == "generate_shot"
    assert command.args["shot_id"] == 3


def test_parse_unknown_text_as_message():
    command = parse_command("我要做一个都市逆袭短剧")
    assert command.name == "message"
    assert command.args["text"] == "我要做一个都市逆袭短剧"


def test_parse_short_drama_flow_commands():
    assert parse_command("确认脚本").name == "confirm_script"
    assert parse_command("查看脚本").name == "show_script"
    assert parse_command("查看角色").name == "show_characters"
    assert parse_command("查看分镜").name == "show_storyboard"
    assert parse_command("修改设定").name == "edit_settings"
    assert parse_command("生成角色").name == "generate_characters"
    assert parse_command("生成分镜").name == "generate_storyboard"
    assert parse_command("导出图片提示词").name == "export_image_prompts"
    assert parse_command("合成整集").name == "assemble_episode"


def test_parse_home_menu_numbers():
    assert parse_command("1").name == "new_project"
    assert parse_command("2").name == "confirm_script"
    assert parse_command("3").name == "generate_characters"
    assert parse_command("4").name == "generate_storyboard"
    assert parse_command("5").name == "export_image_prompts"
    assert parse_command("6").name == "switch_project"
    assert parse_command("7").name == "status"
    assert parse_command("8").name == "generate_all"
    assert parse_command("9").name == "assemble_episode"
    assert parse_command("10").name == "edit_settings"


def test_parse_contextual_numbers_use_current_project_menu_first():
    assert parse_contextual_command("1", "script_confirm").name == "show_script"
    assert parse_contextual_command("2", "script_confirm").name == "confirm_script"
    assert parse_contextual_command("1", "characters_ready").name == "show_script"
    assert parse_contextual_command("2", "characters_ready").name == "show_characters"
    assert parse_contextual_command("4", "characters_ready").name == "generate_storyboard"


def test_parse_contextual_numbers_fall_back_to_home_menu_without_project_step():
    assert parse_contextual_command("1", None).name == "new_project"
    assert parse_contextual_command("8", None).name == "generate_all"
