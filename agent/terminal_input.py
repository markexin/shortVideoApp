from __future__ import annotations


def normalize_prompt_text(prompt_text: str) -> str:
    if prompt_text == "> ":
        return "\n> "
    return prompt_text


def read_text(prompt_text: str = "> ") -> str:
    prompt_text = normalize_prompt_text(prompt_text)
    try:
        from prompt_toolkit import prompt
    except ImportError:
        return input(prompt_text)

    return prompt(
        prompt_text,
        multiline=False,
        wrap_lines=False,
        mouse_support=False,
    )
