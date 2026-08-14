from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agent.state_machine import available_actions


@dataclass(frozen=True)
class Command:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


def parse_command(text: str) -> Command:
    raw = text.strip()
    normalized = raw.lower()

    aliases = {
        "1": "new_project",
        "2": "confirm_script",
        "3": "generate_characters",
        "4": "generate_storyboard",
        "5": "export_image_prompts",
        "6": "switch_project",
        "7": "status",
        "8": "generate_all",
        "9": "assemble_episode",
        "10": "edit_settings",
        "首页": "home",
        "home": "home",
        "返回": "back",
        "back": "back",
        "继续": "continue",
        "continue": "continue",
        "保存": "save",
        "save": "save",
        "切换剧本": "switch_project",
        "打开剧本": "switch_project",
        "查看状态": "status",
        "状态": "status",
        "生成全部": "generate_all",
        "并发生成全部视频": "generate_all",
        "重写脚本": "rewrite_script",
        "重写分镜": "rewrite_storyboard",
        "确认脚本": "confirm_script",
        "查看脚本": "show_script",
        "脚本": "show_script",
        "查看角色": "show_characters",
        "角色": "show_characters",
        "查看分镜": "show_storyboard",
        "分镜": "show_storyboard",
        "修改设定": "edit_settings",
        "编辑设定": "edit_settings",
        "改设定": "edit_settings",
        "生成角色": "generate_characters",
        "生成角色圣经": "generate_characters",
        "生成分镜": "generate_storyboard",
        "导出图片提示词": "export_image_prompts",
        "图片提示词": "export_image_prompts",
        "查看图片任务": "show_image_tasks",
        "图片任务": "show_image_tasks",
        "导入图片目录": "import_image_dir",
        "批量绑定图片": "import_image_dir",
        "合成整集": "assemble_episode",
        "拼接整集": "assemble_episode",
    }
    if raw in aliases:
        return Command(aliases[raw])
    if normalized in aliases:
        return Command(aliases[normalized])

    generate_match = re.search(r"生成第\s*(\d+)\s*镜", raw)
    if generate_match:
        return Command("generate_shot", {"shot_id": int(generate_match.group(1))})

    rewrite_match = re.search(r"重写第\s*(\d+)\s*镜", raw)
    if rewrite_match:
        return Command("rewrite_shot", {"shot_id": int(rewrite_match.group(1))})

    image_match = re.search(r"第\s*(\d+)\s*镜图片[:：]\s*(.+)", raw)
    if image_match:
        return Command(
            "set_shot_image",
            {
                "shot_id": int(image_match.group(1)),
                "image_path": image_match.group(2).strip(),
            },
        )

    return Command("message", {"text": raw})


def parse_contextual_command(text: str, current_step: str | None = None) -> Command:
    raw = text.strip()
    if current_step and raw.isdigit():
        for action in available_actions(current_step):
            if action.number == raw:
                return Command(action.command_name)
    return parse_command(raw)
