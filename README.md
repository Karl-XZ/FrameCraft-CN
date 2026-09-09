# FrameCraft-CN openJiuwen 多 Agent 版

FrameCraft-CN 将解说音频或中文讲稿转换为可预览、可下载、可继续对话修改的无人物解说视频。当前后端基于华为开源的 openJiuwen Agent Core 编排多个 DeepSeek Agent，最终由 HyperFrames 真实渲染 MP4。

本版本不处理人物口播，不生成剪映草稿，不提供 FFmpeg 拼接兜底。只要 Agent、HyperFrames 或视觉验收未通过，任务就会明确停止，不注册伪成功版本。

## 功能

- 上传音频：本地 Whisper 生成简体中文逐字稿与词级时间戳。
- 输入讲稿：先使用 Edge TTS 生成中文旁白，再按原稿生成精确字幕与场景种子。
- 多 Agent 设计：内容、视觉、时序三个专家并行工作，代码总监统一生成每个项目的创意规格。
- 动态视频：根据内容选择流程、数据、知识关系、故事时间线等场景，不复用上一项目的固定文案。
- 真实渲染：输出 1080p、30fps、H.264/AAC MP4，同时保留 HyperFrames HTML 工程、字幕和时间线。
- 双重验收：先用 `ffprobe` 检查音视频流与完整时长，再由 DeepSeek 视觉模型检查全片联系表。
- 项目隔离：每个项目拥有独立素材、聊天、分析、Agent 追踪与版本目录。
- 自动清理：生产环境默认只保留 24 小时，活动任务不会被中途删除。

## 演示

[查看 Bilibili 演示视频](https://www.bilibili.com/video/BV1Q6jC6QEPv/)

![FrameCraft-CN 工作台预览](docs/assets/readme/workbench-chat-and-progress.png)

![FrameCraft-CN 成片示意](docs/assets/readme/final-video-sample.png)

## 架构

```text
React 工作台
  -> FastAPI 项目与任务 API
  -> 音频预处理 / 本地 Whisper ASR
  -> openJiuwen TeamRuntime
       -> narrative: 内容结构
       -> visual: 视觉隐喻与场景形式
       -> timing: 节奏与可读性
       -> code_director: DeepSeek V4 Pro 汇总创意规格
  -> HyperFrames HTML 编译器
  -> HyperFrames --strict 真实渲染
  -> ffprobe 完整性检查
  -> DeepSeek V4 Flash Vision 全片抽帧验收
  -> 注册版本与下载
```

三个专家由 openJiuwen `TeamRuntime` 并行调度，代码总监在专家完成后汇总。每次项目分析都会真实调用模型，追踪信息写入 `outputs/<project_id>/analysis/agent_trace.json`。该文件包含框架名、团队拓扑、各 Agent 模型、耗时和原始结构化结果，可确认任务确实经过 openJiuwen 与 DeepSeek。

## 模型分工

| 职责 | 默认模型 |
| --- | --- |
| 内容、视觉、时序专家 | `deepseek-v4-flash` |
| 代码总监 | `deepseek-v4-pro` |
| 成片视觉验收 | `deepseek-v4-flash-vision-exp` |

默认 OpenAI 兼容地址为 `https://api.deepseek.com`。密钥只通过环境变量或受保护的后端设置提供，不应写入仓库、前端源码、日志或 README。

## 环境要求

- Python 3.11
- Node.js 22 或更高版本
- npm
- ffmpeg 与 ffprobe
- Chromium 或 Chrome
- 可用的 DeepSeek API Key
- HyperFrames CLI，项目当前锁定 `0.7.41`

Ubuntu 依赖示例：

```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv ffmpeg curl fonts-noto-cjk
```

## 安装

```bash
git clone https://github.com/Karl-XZ/FrameCraft-CN.git
cd FrameCraft-CN
./scripts/setup-deps.sh
```

安装脚本会创建独立的 `backend/venv-openjiuwen`，安装 `openjiuwen==0.1.17.post1`、FastAPI、OpenAI SDK、前端依赖与 HyperFrames。

检查环境：

```bash
./scripts/verify-env.sh
```

## 配置

推荐使用环境变量：

```bash
export DEEPSEEK_API_KEY='your-key'
export DEEPSEEK_BASE_URL='https://api.deepseek.com'
```

不要把真实密钥写入 `.env.example`、Docker 镜像、Git 提交或浏览器构建产物。前端模型设置不会回显已保存的密钥。

可选运行参数：

```bash
export FRAMECRAFT_BACKEND_HOST=0.0.0.0
export FRAMECRAFT_BACKEND_PORT=8022
export FRAMECRAFT_RETENTION_ENABLED=1
export FRAMECRAFT_RETENTION_HOURS=24
```

## 启动

```bash
./scripts/start-backend.sh
./scripts/start-frontend.sh
```

健康检查：

```bash
curl http://127.0.0.1:8022/api/health
```

预期响应：

```json
{"ok":true,"mode":"openjiuwen-multi-agent"}
```

除健康检查外，API 默认要求访问口令。首次启动会生成 `backend/storage/access_token.txt`，文件权限设置为仅当前用户可读写。浏览器首次打开时可通过 `?access_token=<token>` 写入当前浏览器本地存储，之后 URL 中的口令会自动移除。

## 生成流程

1. 在网页新建项目并选择 16:9 或 9:16。
2. 上传一条解说音频，或直接输入中文讲稿。
3. 点击开始分析，等待 openJiuwen 团队完成内容、视觉、时序和代码设计。
4. 查看方案后点击生成。
5. HyperFrames 严格渲染通过后，系统检查媒体流、完整时长和全片联系表。
6. 验收通过后下载 MP4、字幕、时间线或 HyperFrames 工程。
7. 在项目聊天中提出修改要求，Agent 会在当前项目上下文内生成新版本。

## 质量门槛

- 音频必须完整保留，成片时长与输入时长误差受控。
- 字幕来自逐字稿，使用简体中文，固定在底部安全区居中显示。
- 观众画面不得出现“场景、制作、动画、工作流、Agent”等幕后文案。
- 不允许伪造数据；原稿没有数值时使用定性信息图。
- 流程类画面逐节点出现，不把整张流程图当作一页 PPT 一次展示。
- 圆角、半透明、布局密度和动画节奏必须通过全片抽帧检查。
- HyperFrames 以 `--strict` 运行，lint 硬错误会直接阻止版本注册。
- 视觉评分低于 75 或视觉模型判断失败时，任务不会注册版本。

## 五分钟基准

仓库提供真实 60 秒音频基准脚本。它会为每一轮重新创建项目、上传、ASR、调用四个 DeepSeek Agent、生成 HTML、严格渲染、视觉验收和 `ffprobe` 检查，不复用上一轮创意结果。

```bash
backend/venv-openjiuwen/bin/python scripts/benchmark_openjiuwen_60s.py \
  /absolute/path/to/real-60s.wav --api http://127.0.0.1:8022 --runs 3
```

2026-09-09 在 Apple Silicon 8 核机器上的连续三轮实测：

| 轮次 | 画幅 | 分析 | 生成与验收 | 端到端 | 视觉评分 |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | 16:9 | 20.16 秒 | 60.39 秒 | 80.63 秒 | 88 |
| 2 | 9:16 | 18.11 秒 | 72.37 秒 | 90.57 秒 | 88 |
| 3 | 16:9 | 18.11 秒 | 60.36 秒 | 78.57 秒 | 88 |

三轮最大端到端耗时 90.57 秒，平均 83.26 秒。机器、网络和 DeepSeek 服务负载会影响结果，因此生产验收应在目标服务器上再次运行同一基准。原始结构化结果位于 `benchmark-results/openjiuwen-60s-20260909-191937.json`。

## 产物

```text
outputs/<project_id>/
  analysis/
    analysis.json
    edit_plan.json
    creative_plan.json
    agent_trace.json
  <version_id>/
    preview.mp4
    subtitles.srt
    timeline.json
    visual-review.jpg
    agent_visual_review.json
    agent_trace.json
    hyperframes/
    hyperframes_project.zip
```

## 自动清理

后端启动时会清理超过保留期且没有活动任务的项目。服务器还可以每小时执行：

```bash
FRAMECRAFT_RETENTION_HOURS=24 ./scripts/cleanup-expired.sh
```

只查看待删除内容：

```bash
./scripts/cleanup-expired.sh --dry-run
```

## 参考

- [openJiuwen Agent Core](https://github.com/openJiuwen-ai/agent-core)
- [openJiuwen 文档](https://docs.openjiuwen.com/)
- [DeepSeek API 文档](https://api-docs.deepseek.com/)
- [HyperFrames](https://github.com/nateherk/hyperframes)
