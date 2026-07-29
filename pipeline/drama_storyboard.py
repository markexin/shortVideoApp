from __future__ import annotations

import json
import re

import config
from pipeline.llm_client import create_llm_client
from projects.schema import Character, Shot


SYSTEM_PROMPT = """你是短剧导演和分镜师。
目标是把短剧脚本拆成可生产的竖屏分镜，每个镜头都要适合先生成图片，再图生视频。
必须把角色一致性约束体现在 image_prompt 和 video_prompt 中。"""


def build_storyboard_prompt(
    script: str,
    characters: list[Character],
    aspect_ratio: str = "9:16",
) -> str:
    character_block = "\n".join(
        f"- {char.name}: {char.description}; {char.consistency_prompt}; negative: {char.negative_prompt}"
        for char in characters
    )
    return f"""请将下面短剧脚本拆成分镜。

画面比例: {aspect_ratio}

角色圣经:
{character_block}

脚本:
{script}

输出严格 JSON:
{{
  "shots": [
    {{
      "shot_id": 1,
      "scene_description": "中文场景地点",
      "action": "中文动作描述",
      "characters": ["角色名"],
      "dialogue": "台词或旁白，没有则空字符串",
      "image_prompt": "English prompt for image generation, include composition, lighting, scene, character consistency",
      "video_prompt": "English prompt for image-to-video, include camera movement and action",
      "negative_prompt": "English negative prompt, include no face drift, no outfit drift, no text, no watermark",
      "duration": 4
    }}
  ]
}}

分镜规则:
- 每个镜头 3-8 秒
- 单镜头最多 2 个主要角色近景互动
- 每个含角色镜头必须继承角色圣经中的外观锚点
- image_prompt 用于用户手动生成首帧图，必须能独立复制使用
- video_prompt 用于图生视频，聚焦动作、运镜、情绪
- 不要要求画面中出现文字、Logo、字幕
- 只输出 JSON，不要解释
"""


def generate_drama_storyboard(
    script: str,
    characters: list[Character],
    aspect_ratio: str = "9:16",
) -> list[Shot]:
    client = create_llm_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_storyboard_prompt(
                    script=script,
                    characters=characters,
                    aspect_ratio=aspect_ratio,
                ),
            },
        ],
        temperature=0.5,
    )
    return parse_storyboard_response(response.choices[0].message.content or "")


def parse_storyboard_response(text: str) -> list[Shot]:
    data = _parse_json_response(text)
    return [Shot.from_dict(item) for item in data.get("shots", [])]


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise json.JSONDecodeError("无法从分镜响应中提取 JSON", text[:200], 0)
