# 短剧智能体

基于 InstantVideo 改造的短剧生产智能体。项目保留分镜、视频后处理、字幕、BGM、导出等流水线能力，但视频生成不再绑定 Seedance，改为通过自定义工作流适配器生成。

## 当前能力

- 问答式入口: 首页、返回、切换剧本、查看状态、绑定图片、生成指定镜头、生成全部
- 多剧本项目管理: 每个剧本独立保存 `project.json`、图片提示词、图片、视频和日志
- LLM 脚本生成: 默认使用 OpenAI-compatible MiniMax M3
- 分镜视频生成: 每个分镜使用用户提供的图片路径，通过 `WorkflowAdapter` 调用外部图生视频工作流
- 人物一致性: 角色圣经 + 分镜提示词自动注入固定外观、负面约束
- 后期流水线: 保留 FFmpeg 拼接、转场、BGM、TTS、字幕、调色、多平台导出能力

## 配置

复制示例配置:

```bash
cp .env.example .env
```

`.env` 示例:

```bash
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://api.minimax.io/v1
LLM_MODEL=MiniMax-M3

WORKFLOW_ENDPOINT=http://127.0.0.1:8000/generate-shot
```

也可以使用 MiniMax 别名:

```bash
MINIMAX_API_KEY=your_minimax_token_plan_key
MINIMAX_BASE_URL=https://api.minimax.io/v1
LLM_MODEL=MiniMax-M3
```

不要把真实 key 写入 `.env.example` 或提交到 git。

## 启动问答式智能体

```bash
python main.py --agent
```

常用命令:

```text
首页
返回
切换剧本
查看状态
新建 女主被老板羞辱后逆袭，三集都市爽剧
第3镜图片: /Users/you/images/shot_003.png
生成第3镜
生成全部
合成整集
退出
```

推荐完整流程:

```text
新建 女主被老板羞辱后逆袭，三集都市爽剧
确认脚本
生成角色
生成分镜
导出图片提示词
第1镜图片: /Users/you/images/shot_001.png
第2镜图片: /Users/you/images/shot_002.png
生成全部
合成整集
```

状态机会按下面顺序推进，避免跳步:

```text
script_confirm
-> script_confirmed
-> characters_ready
-> storyboard_ready
-> image_prompts_exported
-> videos_ready
-> episode_ready
```

## MiniMax M3 连通性检查

`.env` 配好后运行:

```bash
python scripts/check_llm.py
```

成功时会输出模型返回的短文本。缺少 key 时会提示配置 `LLM_API_KEY` 或 `MINIMAX_API_KEY`。

## ComfyUI 工作流

推荐使用 ComfyUI API workflow。

1. 启动 ComfyUI，确认本地地址可访问:

```bash
curl http://127.0.0.1:8188/system_stats
```

2. 在 ComfyUI 里打开你的图生视频工作流。

3. 打开设置中的开发者模式，使用 `Save (API Format)` 导出 workflow JSON。

4. 把导出的 workflow JSON 放到项目里，例如:

```text
examples/my_i2v_workflow_api.json
```

5. 在 workflow JSON 中把对应字段替换成占位符:

```text
LoadImage.image              -> __IMAGE_NAME__
正向提示词 text              -> __PROMPT__
负向提示词 text              -> __NEGATIVE_PROMPT__
输出文件名前缀 filename_prefix -> __OUTPUT_PREFIX__
时长/帧数相关字段，可选        -> __DURATION__
```

6. `.env` 配置:

```bash
WORKFLOW_PROVIDER=comfyui
COMFYUI_BASE_URL=http://127.0.0.1:8188
COMFYUI_WORKFLOW_PATH=examples/my_i2v_workflow_api.json
```

适配器会自动:

- 上传分镜图片到 `/upload/image`
- 替换 workflow 中的占位符
- POST `/prompt`
- 轮询 `/history/{prompt_id}`
- 从 `/view` 下载输出视频到项目目录

参考占位符示例: [examples/comfyui_workflow_api_example.json](examples/comfyui_workflow_api_example.json)。

## 通用 HTTP 工作流接口

如果设置 `WORKFLOW_PROVIDER=http` 和 `WORKFLOW_ENDPOINT`，系统会向该地址发送 JSON:

```json
{
  "shot_id": 1,
  "image_path": "/absolute/path/shot_001.png",
  "prompt": "video prompt",
  "negative_prompt": "negative prompt",
  "duration": 5,
  "aspect_ratio": "9:16",
  "output_path": "/absolute/path/output/shot_001.mp4",
  "metadata": {}
}
```

工作流返回其一:

```json
{"status": "success", "local_path": "/absolute/path/shot_001.mp4"}
```

或:

```json
{"status": "success", "video_url": "https://example.com/shot_001.mp4"}
```

失败时:

```json
{"status": "failed", "error": "reason"}
```

本地 mock 工作流:

```bash
python scripts/mock_workflow_server.py
```

它只会写入占位文件，不会生成可播放视频，用于验证智能体调用链路。真实生产时把 `WORKFLOW_ENDPOINT` 指向你的图生视频工作流。

## 目录结构

```text
agent/             # 问答式入口、命令解析
projects/          # 剧本项目数据结构和保存/加载
pipeline/          # 脚本、分镜、提示词、视频生成、主编排
workflows/         # 自定义工作流适配器
tools/             # FFmpeg、TTS、节拍分析等后处理工具
projects_data/     # 本地剧本项目，默认不提交
output/            # 生成产物，默认不提交
```

## 测试

```bash
PYENV_VERSION=3.9.7 pyenv exec python -m pytest tests/test_workflow_generation.py tests/test_short_drama_project.py tests/test_agent_commands.py tests/test_script_writer.py tests/test_character_bible.py tests/test_drama_storyboard.py tests/test_episode_assembler.py tests/test_state_machine.py tests/test_llm_config.py -q
```
