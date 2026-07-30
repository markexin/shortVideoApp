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


def with_reference_negative(negative_prompt: str) -> str:
    base = negative_prompt.strip()
    if not base:
        return REFERENCE_NEGATIVE_PROMPT
    if REFERENCE_NEGATIVE_PROMPT in base:
        return base
    return f"{base}, {REFERENCE_NEGATIVE_PROMPT}"
