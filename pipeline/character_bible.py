from __future__ import annotations

import json
import re

import config
from pipeline.llm_client import create_llm_client
from projects.schema import Character


SYSTEM_PROMPT = """你是短剧角色设定师。
目标是从短剧脚本中提取可稳定复用的人物设定，服务于后续图片生成和图生视频。
必须强调人物一致性，不要写会导致每个镜头变化的模糊描述。"""


def build_character_prompt(script: str) -> str:
    return f"""请从下面短剧脚本生成角色圣经。

脚本:
{script}

输出严格 JSON:
{{
  "characters": [
    {{
      "name": "角色名",
      "description": "中文外观锚点，包含年龄段、性别、脸型、发型、服装、气质、标志物",
      "consistency_prompt": "English image/video consistency prompt, stable face, hair, outfit, age, temperament",
      "negative_prompt": "English negative prompt, forbid hairstyle changes, age changes, outfit drift, face drift"
    }}
  ]
}}

要求:
- 只输出主要角色和反复出现的重要角色
- 外观锚点必须具体、可画面化、可重复
- 不要包含剧情评价
- 不要输出 JSON 之外的解释
"""


def generate_character_bible(script: str) -> list[Character]:
    client = create_llm_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_character_prompt(script)},
        ],
        temperature=0.4,
    )
    return parse_characters_response(response.choices[0].message.content or "")


def parse_characters_response(text: str) -> list[Character]:
    data = _parse_json_response(text)
    return [Character.from_dict(item) for item in data.get("characters", [])]


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

    raise json.JSONDecodeError("无法从角色圣经响应中提取 JSON", text[:200], 0)
