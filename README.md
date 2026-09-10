# FrameCraft-CN 一键科普视频版

FrameCraft-CN 把一个科普主题、一篇中文文案或一段音视频，转换为带旁白、简体中文字幕和科学动态图解的 HyperFrames 视频工程。服务端使用华为 openJiuwen 编排 DeepSeek 多 Agent，阿里云百炼提供 TTS 与 ASR，最终 MP4 默认在用户电脑真实渲染并下载。

项目不处理人物口播，不生成剪映草稿，也不提供 FFmpeg 静态拼接兜底。HyperFrames、媒体检查或视觉验收没有通过时，系统会保留真实失败原因，不注册伪成功版本。

## 功能

- 输入主题：DeepSeek 自动生成科普讲稿、章节、视觉主张和来源台账，再调用阿里云 TTS。
- 输入文案：严格按照用户原文生成阿里云 TTS、字幕和视频，不改写正文。
- 上传媒体：阿里云 ASR 转写音频或视频原音轨；最终成片完整使用原音频，不重新配音。
- 多 Agent 设计：内容、视觉、时序专家并行工作，代码总监生成当前项目的唯一创意规格。
- 科学语义动画：机制、尺度、对比、时间线和系统关系使用不同空间结构与持续动画。
- 真实 HyperFrames：本地 Renderer 调用 HyperFrames `--strict` 渲染 H.264/AAC MP4。
- 双重验收：本地 `ffprobe` 检查流和完整时长，DeepSeek 视觉模型检查八帧联系表。
- 项目隔离：每个项目拥有独立素材、聊天、Agent 跟踪、工程和版本记录。
- 工程留云端：服务器保存可复渲染工程，MP4 只在用户电脑生成和下载。
- 自动清理：生产环境默认清理超过 24 小时且没有活动任务的项目资源。

## 演示

[查看 Bilibili 演示视频](https://www.bilibili.com/video/BV1Q6jC6QEPv/)

![FrameCraft-CN 工作台预览](docs/assets/readme/workbench-chat-and-progress.png)

![FrameCraft-CN 成片示意](docs/assets/readme/final-video-sample.png)

## 三种输入模式

| 模式 | 用户输入 | 内容边界 | 声音来源 |
| --- | --- | --- | --- |
| 主题 | 主题、受众、额外要求 | DeepSeek 生成讲稿并核验来源链接 | 阿里云 Qwen3 TTS |
| 文案 | 完整演讲稿 | 保持原文字序和内容，只按标点分段 | 阿里云 Qwen3 TTS |
| 媒体 | 音频或含音轨的视频 | 阿里云 ASR 转写，视觉严格跟随原音频 | 用户原音频 |

完整规范见 [一键科普视频生成工作流](docs/SCIENCE_VIDEO_WORKFLOW.md)。

## 架构

```text
React 网页工作台
  -> FastAPI 项目、素材、任务和聊天 API
  -> 主题：DeepSeek 讲稿与来源 / 文案：原文 / 媒体：阿里云 ASR
  -> 文本输入使用阿里云 Qwen3 TTS
  -> openJiuwen TeamRuntime
       -> narrative：科学叙事与信息层级
       -> visual：视觉隐喻与语义运动
       -> timing：节奏、字幕和同屏密度
       -> code_director：DeepSeek Pro 汇总创意规格
  -> 生成 HyperFrames HTML、时间线、字幕和来源台账
  -> 浏览器把工程包交给用户电脑的 FrameCraft Renderer
  -> HyperFrames --strict 真实渲染
  -> ffprobe 完整性检查 + 临时联系表视觉验收
  -> MP4 在当前电脑预览和下载，服务器只保存工程
```

`outputs/<project_id>/analysis/agent_trace.json` 保存 openJiuwen 团队拓扑、模型、耗时和结构化结果，用于确认每次任务真实经过多 Agent。

## 模型分工

| 职责 | 默认模型或服务 |
| --- | --- |
| 内容、视觉、时序专家 | `deepseek-v4-flash` |
| 科普写稿、代码总监 | `deepseek-v4-pro` |
| 成片视觉验收 | `deepseek-v4-flash-vision-exp` |
| 文本转语音 | 阿里云百炼 `qwen3-tts-flash` |
| 语音转文字 | 阿里云百炼 `qwen3-asr-flash` |

## 环境要求

- Python 3.11
- Node.js 22 或更高版本
- npm
- `ffmpeg` 与 `ffprobe`
- Chromium 或 Chrome
- DeepSeek API Key
- 阿里云百炼 DashScope API Key
- HyperFrames CLI，当前锁定 `0.7.41`

Ubuntu 示例：

```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv ffmpeg curl fonts-noto-cjk
```

## 安装

```bash
git clone https://github.com/Karl-XZ/FrameCraft-CN.git
cd FrameCraft-CN
./scripts/setup-deps.sh
./scripts/verify-env.sh
```

## 配置

```bash
export DEEPSEEK_API_KEY='your-deepseek-key'
export DEEPSEEK_BASE_URL='https://api.deepseek.com'

export DASHSCOPE_API_KEY='your-dashscope-key'
export DASHSCOPE_BASE_URL='https://dashscope.aliyuncs.com/api/v1'
export DASHSCOPE_COMPATIBLE_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'
export DASHSCOPE_TTS_MODEL='qwen3-tts-flash'
export DASHSCOPE_TTS_VOICE='Cherry'
export DASHSCOPE_ASR_MODEL='qwen3-asr-flash'
```

不要把真实密钥写入 Git、README、前端源码、浏览器构建产物或日志。后端设置接口不会向前端回显已保存的密钥。

可选运行参数：

```bash
export FRAMECRAFT_BACKEND_HOST=0.0.0.0
export FRAMECRAFT_BACKEND_PORT=8022
export FRAMECRAFT_RETENTION_ENABLED=1
export FRAMECRAFT_RETENTION_HOURS=24
export FRAMECRAFT_RENDER_TARGET=local
```

## 启动

```bash
./scripts/start-backend.sh
./scripts/start-frontend.sh
```

每台负责渲染的用户电脑还要启动本地 Renderer：

```bash
npm install
npm run local-renderer
```

macOS/Linux 可运行 `./scripts/start-local-renderer.sh`，Windows 可运行 `scripts/start-local-renderer.cmd`。Renderer 只监听 `127.0.0.1:19186`，不接收 DeepSeek、DashScope Key 或服务器访问口令。公网工作台必须使用 HTTPS，浏览器首次访问回环服务时需要允许“本地网络访问”。

正式域名建议配置来源白名单：

```bash
export FRAMECRAFT_LOCAL_RENDERER_ORIGINS='https://your-framecraft.example.com'
export FRAMECRAFT_LOCAL_RENDERER_CRF=30
```

除健康检查外，API 默认需要访问口令。首次启动会生成权限为 `0600` 的 `backend/storage/access_token.txt`。浏览器通过一次性 URL 查询参数写入本地存储后会移除地址栏中的口令。

## 网页流程

1. 新建项目，选择主题、文案或媒体模式。
2. 设置画幅、目标时长和科学视觉风格；媒体模式进入工作台后上传文件。
3. 点击“开始生成科普方案”，等待内容准备和 openJiuwen 多 Agent 分析。
4. 查看方案并确认生成。
5. 网页连接本地 Renderer，下载工程并执行 HyperFrames 严格渲染。
6. 本机检查音视频流与完整时长，并生成临时八帧联系表。
7. 云端视觉 Agent 验收后删除联系表；通过时 MP4 直接进入当前浏览器预览和下载。
8. 在项目聊天中继续提出修改，当前项目 Agent 基于同一上下文生成新版本。

## 质量门槛

- 文案模式字幕必须覆盖原文，媒体模式必须保留原音频完整时长。
- 字幕使用简体中文，固定居中放在底部安全区，并带渐入渐出。
- 观众画面禁止出现幕后制作文案。
- 精确数据必须可追溯；没有数字时只用定性图解，不伪造刻度。
- 机制、尺度、对比、时间线和系统关系使用不同主视觉结构。
- 关键节点逐个出现，并具有表达含义的持续运动。
- 主视觉充分利用画幅，避免拥挤、遮挡与无意义空白。
- HyperFrames 必须以 `--strict` 运行；视觉评分低于 75 时不登记通过版本。

## 测试

```bash
backend/venv-openjiuwen/bin/python -m unittest discover -s backend/tests -v
cd framecraft-agent && npm run lint && npm run build
```

部署到 `/FrameCraft/` 子路径时使用：

```bash
cd framecraft-agent
FRAMECRAFT_PUBLIC_BASE=/FrameCraft/ npm run build
```

真实网页端主题模式：

```bash
backend/venv-openjiuwen/bin/python scripts/run_science_ui_flow.py \
  --mode topic \
  --input '为什么天空通常呈现蓝色，日落时偏红？' \
  --requirements '面向成年人，约一分钟，避免公式' \
  --studio 'https://your-framecraft.example.com' \
  --output benchmark-results/science-topic.mp4
```

`--mode script` 时 `--input` 传完整文案；`--mode media` 时传音频或视频绝对路径。测试脚本连接真实 API、本地 Renderer 和真实 HyperFrames，不提供模拟成片。

## 产物

```text
outputs/<project_id>/
  analysis/analysis.json, edit_plan.json, creative_plan.json, agent_trace.json
  input/scene_seed.json, source_bundle.json, transcript.txt, SOURCE_LEDGER.md
  <version_id>/subtitles.srt, timeline.json, agent_visual_review.json
  <version_id>/local_render_manifest.json, hyperframes/, hyperframes_project.zip
```

## 安全与保留

- Renderer 只绑定回环地址，拒绝 ZIP 目录穿越，并在系统临时目录隔离执行。
- 服务端忽略云端渲染请求；MP4 不上传服务器，历史预览接口返回 `410`。
- 服务器只接收临时联系表用于验收，接口结束后立即删除图片，只保存验收 JSON。
- 同一时间只允许一个本地渲染任务，本机临时工程和 MP4 默认一小时后删除。
- 后端可执行 `FRAMECRAFT_RETENTION_HOURS=24 ./scripts/cleanup-expired.sh` 清理过期项目。
- 来源 URL 只允许公开 HTTPS 地址，并拒绝内网目标和越界重定向。

## 参考

- [openJiuwen Agent Core](https://github.com/openJiuwen-ai/agent-core)
- [openJiuwen 文档](https://docs.openjiuwen.com/)
- [DeepSeek API 文档](https://api-docs.deepseek.com/)
- [阿里云百炼 Qwen TTS API](https://help.aliyun.com/zh/model-studio/qwen-tts-api)
- [阿里云百炼 Qwen ASR API](https://help.aliyun.com/zh/model-studio/qwen-asr-api-reference)
- [HyperFrames](https://github.com/nateherk/hyperframes)
