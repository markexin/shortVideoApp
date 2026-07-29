from __future__ import annotations

from openai import OpenAI

import config


def ensure_llm_config(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> str | None:
    api_key = config.LLM_API_KEY if api_key is None else api_key
    base_url = config.LLM_BASE_URL if base_url is None else base_url
    model = config.LLM_MODEL if model is None else model

    if not api_key:
        return "缺少 LLM_API_KEY 或 MINIMAX_API_KEY，请在 .env 中配置。"
    if not base_url:
        return "缺少 LLM_BASE_URL 或 MINIMAX_BASE_URL。"
    if not model:
        return "缺少 LLM_MODEL。"
    return None


def create_llm_client() -> OpenAI:
    error = ensure_llm_config()
    if error:
        raise RuntimeError(error)
    return OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
