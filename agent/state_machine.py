from __future__ import annotations

from dataclasses import dataclass


FLOW = [
    "home",
    "script_confirm",
    "script_confirmed",
    "characters_ready",
    "storyboard_ready",
    "image_prompts_exported",
    "videos_ready",
    "episode_ready",
]


@dataclass(frozen=True)
class Action:
    number: str
    label: str
    command_name: str
    command_text: str


COMMON_ACTIONS = [
    Action("10", "修改题材/受众/集数等设定", "edit_settings", "修改设定"),
    Action("11", "继续上次脚本生成", "continue", "继续"),
    Action("6", "切换剧本", "switch_project", "切换剧本"),
    Action("7", "查看状态", "status", "查看状态"),
    Action("0", "退出", "exit", "退出"),
]


STEP_ACTIONS = {
    "script_confirm": [
        Action("1", "查看脚本内容", "show_script", "查看脚本"),
        Action("2", "确认脚本，进入角色生成", "confirm_script", "确认脚本"),
    ],
    "script_confirmed": [
        Action("1", "查看脚本内容", "show_script", "查看脚本"),
        Action("3", "生成角色圣经", "generate_characters", "生成角色"),
    ],
    "characters_ready": [
        Action("1", "查看脚本内容", "show_script", "查看脚本"),
        Action("2", "查看角色圣经", "show_characters", "查看角色"),
        Action("4", "生成短剧分镜", "generate_storyboard", "生成分镜"),
    ],
    "storyboard_ready": [
        Action("1", "查看脚本内容", "show_script", "查看脚本"),
        Action("2", "查看角色圣经", "show_characters", "查看角色"),
        Action("3", "查看分镜摘要", "show_storyboard", "查看分镜"),
        Action("5", "导出图片提示词", "export_image_prompts", "导出图片提示词"),
        Action("12", "准备下一段视频入参", "prepare_video_segment", "准备视频片段"),
        Action("13", "查看当前视频入参", "show_video_segment_payload", "查看视频入参"),
    ],
    "image_prompts_exported": [
        Action("1", "查看脚本内容", "show_script", "查看脚本"),
        Action("2", "查看角色圣经", "show_characters", "查看角色"),
        Action("3", "查看分镜摘要", "show_storyboard", "查看分镜"),
        Action("4", "查看/导出图片任务", "show_image_tasks", "查看图片任务"),
        Action("12", "准备下一段视频入参", "prepare_video_segment", "准备视频片段"),
        Action("13", "查看当前视频入参", "show_video_segment_payload", "查看视频入参"),
        Action("15", "批量绑定已生成图片目录", "import_image_dir", "导入图片目录"),
        Action("8", "图片已准备后生成全部视频", "generate_all", "生成全部"),
    ],
    "videos_ready": [
        Action("1", "查看脚本内容", "show_script", "查看脚本"),
        Action("2", "查看角色圣经", "show_characters", "查看角色"),
        Action("3", "查看分镜摘要", "show_storyboard", "查看分镜"),
        Action("13", "查看当前视频入参", "show_video_segment_payload", "查看视频入参"),
        Action("9", "合成整集", "assemble_episode", "合成整集"),
    ],
    "episode_ready": [
        Action("1", "查看脚本内容", "show_script", "查看脚本"),
        Action("2", "查看角色圣经", "show_characters", "查看角色"),
        Action("3", "查看分镜摘要", "show_storyboard", "查看分镜"),
        Action("13", "查看当前视频入参", "show_video_segment_payload", "查看视频入参"),
        Action("9", "重新合成整集", "assemble_episode", "合成整集"),
    ],
}


def can_transition(current_step: str, target_step: str) -> bool:
    if current_step == target_step:
        return True
    if current_step not in FLOW or target_step not in FLOW:
        return False
    return FLOW.index(target_step) <= FLOW.index(current_step) + 1


def next_step(current_step: str) -> str | None:
    if current_step not in FLOW:
        return None
    index = FLOW.index(current_step)
    if index + 1 >= len(FLOW):
        return None
    return FLOW[index + 1]


def available_actions(current_step: str) -> list[Action]:
    actions = list(STEP_ACTIONS.get(current_step, []))
    actions.extend(COMMON_ACTIONS)
    return actions
