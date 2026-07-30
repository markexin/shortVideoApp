REFERENCE_STYLE = (
    "high-end xianxia fantasy CG, refined Chinese anime 3D game cinematic style, "
    "beautiful immortal drama aesthetic, porcelain skin, delicate facial features, "
    "glossy black hair, elegant flowing hanfu or polished silver-white fantasy armor, "
    "soft blue-white lighting, luminous rim light, shallow depth of field, "
    "sparkling particles, crystal highlights, ultra-detailed hair strands, "
    "clean cool color palette, ethereal immortal aura"
)

CHARACTER_REFERENCE_STYLE = (
    "high-end xianxia fantasy CG character design, refined Chinese anime 3D game style, "
    "porcelain skin, delicate face, sharp elegant eyes, glossy black hair, "
    "luxury hanfu or silver-white fantasy costume, luminous fabric details, "
    "soft blue-white lighting, sparkling particles, ultra-detailed hair strands, "
    "clean face, elegant immortal aura"
)

CHARACTER_IDENTITY_LOCK = (
    "STRICT CHARACTER IDENTITY LOCK: this must be the exact same character across all generated images "
    "and all camera angles. Preserve the same skull structure, face shape, eye shape, eye color, eyebrow shape, "
    "nose bridge, lips, age, body proportions, hairstyle, hairline, hair accessories, outfit cut, outfit colors, "
    "fabric details, belt, signature marks, scars, tattoos, props and temperament. "
    "Do not redesign the character between views. Do not change age, gender, face, hairstyle, costume, body type, "
    "color palette, accessories, scars or symbolic marks. For turnaround sheets, front view, side view and back view "
    "must describe one identical person in one identical outfit, only the camera angle changes."
)

COMPACT_CHARACTER_IDENTITY_LOCK = (
    "STRICT CHARACTER IDENTITY LOCK: exact same character across all angles. "
    "Preserve same skull structure, face shape, eyes, eyebrows, nose, lips, age, body proportions, "
    "hairstyle, hairline, outfit cut, outfit colors, belt, accessories, scars, tattoos, signature marks and props. "
    "Do not redesign the character between views. Only camera angle changes."
)

SCENE_REFERENCE_STYLE = (
    "ethereal xianxia fantasy environment, refined Chinese anime 3D game cinematic style, "
    "soft blue-white mist, luminous spiritual light, jade stone, silver-white highlights, "
    "floating particles, elegant immortal realm atmosphere, clean cool color palette, "
    "high detail, cinematic depth"
)

PROP_REFERENCE_STYLE = (
    "premium xianxia fantasy prop design, refined Chinese anime 3D game cinematic style, "
    "polished jade, silver metal, crystal glow, delicate engraved patterns, "
    "soft blue-white lighting, sparkling particles, high detail, clean luxury finish"
)

REFERENCE_NEGATIVE_PROMPT = (
    "low quality, lowres, blurry, noisy, watermark, logo, text, UI overlay, "
    "western medieval style, modern city objects unless required by script, flat cartoon, chibi, "
    "ugly face, face drift, inconsistent identity, outfit drift, deformed hands, extra fingers, "
    "bad anatomy, distorted body, overexposed skin, harsh dirty colors"
)


def style_for_asset(category: str) -> str:
    if category == "character":
        return CHARACTER_REFERENCE_STYLE
    if category == "scene":
        return SCENE_REFERENCE_STYLE
    if category == "prop":
        return PROP_REFERENCE_STYLE
    return REFERENCE_STYLE


def with_reference_style(prompt: str, category: str = "shot") -> str:
    style = style_for_asset(category)
    base = prompt.strip()
    if style in base:
        return base
    return f"{style}. {base}" if base else style


def character_identity_lock(character_name: str = "", description: str = "", consistency_prompt: str = "") -> str:
    parts = [CHARACTER_IDENTITY_LOCK]
    if character_name:
        parts.append(f"Character name: {character_name}.")
    if description:
        parts.append(f"Fixed visual anchor: {description.strip()}")
    if consistency_prompt:
        parts.append(f"Must preserve exactly: {consistency_prompt.strip()}")
    return " ".join(parts)


def compact_character_identity_lock(
    character_name: str = "",
    description: str = "",
    consistency_prompt: str = "",
    max_description_chars: int = 80,
    max_consistency_chars: int = 360,
) -> str:
    parts = [COMPACT_CHARACTER_IDENTITY_LOCK]
    if character_name:
        parts.append(f"Character name: {character_name}.")
    if description:
        parts.append(f"Fixed visual anchor: {_clip_text(description.strip(), max_description_chars)}")
    if consistency_prompt:
        parts.append(f"Must preserve exactly: {_clip_text(consistency_prompt.strip(), max_consistency_chars)}")
    return " ".join(parts)


def _clip_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip(" ,.;，。；、") + "..."


def with_reference_negative(negative_prompt: str) -> str:
    base = negative_prompt.strip()
    if not base:
        return REFERENCE_NEGATIVE_PROMPT
    if REFERENCE_NEGATIVE_PROMPT in base:
        return base
    return f"{base}, {REFERENCE_NEGATIVE_PROMPT}"
