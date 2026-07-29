from __future__ import annotations

from projects.schema import Character, Shot


def build_image_prompt(
    shot: Shot,
    characters: list[Character],
    aspect_ratio: str = "9:16",
) -> str:
    character_map = {character.name: character for character in characters}
    consistency_parts = []
    negative_parts = []

    for name in shot.characters:
        character = character_map.get(name)
        if not character:
            continue
        if character.description:
            consistency_parts.append(f"{name}: {character.description}")
        if character.consistency_prompt:
            consistency_parts.append(character.consistency_prompt)
        if character.negative_prompt:
            negative_parts.append(character.negative_prompt)

    if shot.negative_prompt:
        negative_parts.append(shot.negative_prompt)

    prompt_parts = [
        f"Shot {shot.shot_id}",
        f"Scene: {shot.scene_description}",
        f"Action: {shot.action}",
        f"Composition prompt: {shot.image_prompt}",
        f"Aspect ratio: {aspect_ratio}",
        "Style: realistic vertical short drama, cinematic lighting, high detail",
    ]

    if consistency_parts:
        prompt_parts.append("Character consistency: " + "; ".join(consistency_parts))

    if negative_parts:
        prompt_parts.append("Negative prompt: " + "; ".join(negative_parts))

    return "\n".join(part for part in prompt_parts if part.strip())
