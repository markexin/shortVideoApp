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
    assert parse_command("查看图片任务").name == "show_image_tasks"
    assert parse_command("图片任务").name == "show_image_tasks"
    assert parse_command("生成图片").name == "generate_images"
    assert parse_command("生成全部图片").name == "generate_images"
    assert parse_command("生成角色图片").name == "generate_character_images"
    assert parse_command("生成场景图片").name == "generate_scene_images"
    assert parse_command("生成道具图片").name == "generate_prop_images"
    assert parse_command("导入图片目录").name == "import_image_dir"
    assert parse_command("批量绑定图片").name == "import_image_dir"
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
    assert parse_contextual_command("4", "image_prompts_exported").name == "show_image_tasks"
    assert parse_contextual_command("5", "image_prompts_exported").name == "generate_images"
    assert parse_contextual_command("12", "image_prompts_exported").name == "generate_character_images"
    assert parse_contextual_command("15", "image_prompts_exported").name == "import_image_dir"


def test_parse_visual_asset_image_generation_commands():
    command = parse_command("生成前5个角色图片")
    assert command.name == "generate_character_images"
    assert command.args["limit"] == 5

    command = parse_command("生成第1个角色图片")
    assert command.name == "generate_character_images"
    assert command.args["index"] == 1

    command = parse_command("生成第1个角色第2个变体图片")
    assert command.name == "generate_character_images"
    assert command.args["index"] == 1
    assert command.args["variant_index"] == 2

    command = parse_command("生成第2个场景图片")
    assert command.name == "generate_scene_images"
    assert command.args["index"] == 2

    command = parse_command("生成第3个道具图片")
    assert command.name == "generate_prop_images"
    assert command.args["index"] == 3


def test_parse_contextual_numbers_fall_back_to_home_menu_without_project_step():
    assert parse_contextual_command("1", None).name == "new_project"
    assert parse_contextual_command("8", None).name == "generate_all"
