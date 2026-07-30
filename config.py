"""全局配置 — 所有 API Key 和默认参数集中管理"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ───
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"
PROJECTS_DIR = PROJECT_ROOT / "projects_data"
MUSIC_DIR = PROJECT_ROOT / "music"
LUTS_DIR = PROJECT_ROOT / "luts"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# ─── LLM (OpenAI-compatible) ───
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("MINIMAX_API_KEY")
LLM_BASE_URL = (
    os.getenv("LLM_BASE_URL")
    or os.getenv("MINIMAX_BASE_URL")
    or "https://api.minimax.io/v1"
)
LLM_MODEL = os.getenv("LLM_MODEL", "MiniMax-M3")

# ─── 自定义视频工作流 ───
# 接收 image_path/prompt/duration/aspect_ratio/output_path 的 HTTP 工作流入口。
# 不配置时, 生成器会提示传入 WorkflowAdapter 或设置该环境变量。
WORKFLOW_PROVIDER = os.getenv("WORKFLOW_PROVIDER", "http")
WORKFLOW_ENDPOINT = os.getenv("WORKFLOW_ENDPOINT", "")

# ComfyUI 本地服务默认地址: http://127.0.0.1:8188
COMFYUI_BASE_URL = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
COMFYUI_WORKFLOW_PATH = os.getenv("COMFYUI_WORKFLOW_PATH", "")
COMFYUI_IMAGE_WORKFLOW_PATH = os.getenv("COMFYUI_IMAGE_WORKFLOW_PATH", "")

# 图片生成工作流: comfyui | liblib
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "comfyui").lower()

# liblib.art OpenAPI 文生图配置
LIBLIB_ACCESS_KEY = os.getenv("LIBLIB_ACCESS_KEY", "")
LIBLIB_SECRET_KEY = os.getenv("LIBLIB_SECRET_KEY", "")
LIBLIB_BASE_URL = os.getenv("LIBLIB_BASE_URL", "https://openapi.liblibai.cloud")
LIBLIB_IMAGE_ENDPOINT = os.getenv("LIBLIB_IMAGE_ENDPOINT", "/api/generate/webui/text2img/ultra")
LIBLIB_STATUS_ENDPOINT = os.getenv("LIBLIB_STATUS_ENDPOINT", "/api/generate/webui/status")
LIBLIB_TEMPLATE_UUID = os.getenv("LIBLIB_TEMPLATE_UUID", "")
LIBLIB_POLL_INTERVAL = float(os.getenv("LIBLIB_POLL_INTERVAL", "3"))
LIBLIB_CHECKPOINT_ID = os.getenv("LIBLIB_CHECKPOINT_ID", "")
LIBLIB_LORA_MODEL_ID = os.getenv("LIBLIB_LORA_MODEL_ID", "")
LIBLIB_LORA_WEIGHT = float(os.getenv("LIBLIB_LORA_WEIGHT", "0.8"))
LIBLIB_SAMPLER = int(os.getenv("LIBLIB_SAMPLER", "15"))
LIBLIB_STEPS = int(os.getenv("LIBLIB_STEPS", "24"))
LIBLIB_CFG_SCALE = float(os.getenv("LIBLIB_CFG_SCALE", "7"))
LIBLIB_CLIP_SKIP = int(os.getenv("LIBLIB_CLIP_SKIP", "2"))
LIBLIB_IMG_COUNT = int(os.getenv("LIBLIB_IMG_COUNT", "1"))


def liblib_task_config(task_type: str) -> dict:
    prefix = f"LIBLIB_{task_type.upper()}_"
    def env_or(name: str, default: str) -> str:
        return os.getenv(name) or default

    return {
        "endpoint": env_or(f"{prefix}IMAGE_ENDPOINT", LIBLIB_IMAGE_ENDPOINT),
        "template_uuid": env_or(f"{prefix}TEMPLATE_UUID", LIBLIB_TEMPLATE_UUID),
        "checkpoint_id": env_or(f"{prefix}CHECKPOINT_ID", LIBLIB_CHECKPOINT_ID),
        "lora_model_id": env_or(f"{prefix}LORA_MODEL_ID", LIBLIB_LORA_MODEL_ID),
        "lora_weight": float(env_or(f"{prefix}LORA_WEIGHT", str(LIBLIB_LORA_WEIGHT))),
        "sampler": int(env_or(f"{prefix}SAMPLER", str(LIBLIB_SAMPLER))),
        "steps": int(env_or(f"{prefix}STEPS", str(LIBLIB_STEPS))),
        "cfg_scale": float(env_or(f"{prefix}CFG_SCALE", str(LIBLIB_CFG_SCALE))),
        "clip_skip": int(env_or(f"{prefix}CLIP_SKIP", str(LIBLIB_CLIP_SKIP))),
        "img_count": int(env_or(f"{prefix}IMG_COUNT", str(LIBLIB_IMG_COUNT))),
        "aspect_ratio": env_or(f"{prefix}ASPECT_RATIO", ""),
        "width": int(env_or(f"{prefix}WIDTH", "0")),
        "height": int(env_or(f"{prefix}HEIGHT", "0")),
    }

# ─── 默认生成参数 ───
DEFAULT_RESOLUTION = "1080p"
DEFAULT_RATIO = "16:9"
DEFAULT_DURATION = 5          # 秒 (每镜头)
DEFAULT_FPS = 24
DEFAULT_GENERATE_AUDIO = True

# ─── 调色 LUT 映射 ───
MOOD_LUT_MAP = {
    "cinematic": "IWLTBAP Coronado - Standard.cube",      # 电影感 (Kodak 风格)
    "premium": "IWLTBAP Coronado - Standard.cube",        # 高端质感
    "energetic": "Cliff-SLog3.cube",                      # 活力 (高对比)
    "dramatic": "Bat-SLog3.cube",                         # 戏剧化 (暗调)
    "warm": "Arrakis-SLog3.cube",                         # 暖色调
    "cold": "Cliff-SLog3.cube",                           # 冷色调
    "futuristic": "Bat-SLog3.cube",                       # 未来感
    "documentary": "IWLTBAP Coronado - LOG.cube",         # 纪录片
    "vintage": "Arrakis-SLog3.cube",                      # 复古
    "modern_tech": "Cliff-SLog3.cube",                    # 科技感
}
# 注: 以上映射基于你下载的 LUT 包。默认按 Rec709 标准色彩空间处理,
# 优先使用 "Standard" 或 "BMDFilm" 后缀的 LUT (非 Log 输入)。

# ─── 音乐库映射 ───
MUSIC_LIBRARY = {
    "cinematic": "tunetank-inspiring-cinematic-music-409347.mp3",
    "epic": "the_mountain-epic-508009.mp3",
    "upbeat": "jonasblakewood-upbeat-corporate-533853.mp3",
    "energetic": "jonasblakewood-upbeat-rock-524145.mp3",
    "ambient": "paulyudin-ambient-ambient-music-482398.mp3",
    "calm": "paulyudin-ambient-ambient-music-482398.mp3",
    "corporate": "jonasblakewood-upbeat-corporate-533853.mp3",
}

# ─── 并发/调度 ───
MAX_CONCURRENT_GENERATIONS = 3
GENERATION_TIMEOUT = 600       # 单个镜头最长等待 10 分钟 (I2V 比 T2V 慢, 需更多时间)
LIBLIB_TIMEOUT = int(os.getenv("LIBLIB_TIMEOUT", str(GENERATION_TIMEOUT)))
MAX_RETRIES_PER_SHOT = 3
DOWNLOAD_IMMEDIATELY = True    # 生成后立即下载 (URL 24h 过期)
