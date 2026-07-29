#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from pipeline.llm_client import create_llm_client, ensure_llm_config


def main() -> int:
    error = ensure_llm_config()
    if error:
        print(error)
        return 2

    client = create_llm_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": "你是一个接口连通性检查助手。"},
            {"role": "user", "content": "请只回复 OK"},
        ],
        temperature=0,
        max_tokens=8,
    )
    content = response.choices[0].message.content or ""
    print(content.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
