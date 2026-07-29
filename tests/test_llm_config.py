import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.llm_client import ensure_llm_config


def test_ensure_llm_config_rejects_missing_key():
    error = ensure_llm_config(api_key="", base_url="https://api.minimax.io/v1", model="MiniMax-M3")
    assert "LLM_API_KEY" in error


def test_ensure_llm_config_accepts_minimax_defaults():
    error = ensure_llm_config(
        api_key="sk-test",
        base_url="https://api.minimax.io/v1",
        model="MiniMax-M3",
    )
    assert error is None
