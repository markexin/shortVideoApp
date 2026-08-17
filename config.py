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

# MiniMax video_generation: subject-reference/image-to-video/text-to-video.
MINIMAX_VIDEO_API_KEY = os.getenv("MINIMAX_API_KEY") or os.getenv("MINIMAX_GROUP_API_KEY") or ""
MINIMAX_VIDEO_BASE_URL = os.getenv("MINIMAX_VIDEO_BASE_URL", "https://api.minimaxi.com")
MINIMAX_VIDEO_MODE = os.getenv("MINIMAX_VIDEO_MODE", "h3_reference")
MINIMAX_VIDEO_MODEL = os.getenv("MINIMAX_VIDEO_MODEL", "MiniMax-H3")
MINIMAX_VIDEO_DURATION = int(os.getenv("MINIMAX_VIDEO_DURATION", "6"))
MINIMAX_VIDEO_RESOLUTION = os.getenv("MINIMAX_VIDEO_RESOLUTION", "1080P")
MINIMAX_VIDEO_TIMEOUT = int(os.getenv("MINIMAX_VIDEO_TIMEOUT", "3600"))

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
MSR_GENERATION_TIMEOUT = int(os.getenv("MSR_GENERATION_TIMEOUT", "3600"))  # MSR 视频片段约 40-50 分钟
MAX_RETRIES_PER_SHOT = 3
DOWNLOAD_IMMEDIATELY = True    # 生成后立即下载 (URL 24h 过期)
