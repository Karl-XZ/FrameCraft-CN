# openJiuwen + DeepSeek 解说视频工作流

> 历史文档：本文是早期无人物解说流程摘要。当前三种输入、阿里云语音和本地 HyperFrames 验收规范见 [一键科普视频生成工作流](SCIENCE_VIDEO_WORKFLOW.md)。

## 输入准备

- 音频模式保留用户原音频，本地 Whisper 生成简体中文逐字稿、词级时间戳与场景种子。
- 讲稿模式使用 Edge TTS 生成旁白，原稿直接作为逐字稿，不再进行会改变文字的二次 ASR。
- 输入准备失败会进入需要补充信息状态，不生成占位字幕或伪成片。

## openJiuwen 团队

每个分析任务创建一个独立 `BaseTeam`，由 `TeamRuntime` 调度：

1. `narrative` 提炼观众可见标题、说明和信息节点。
2. `visual` 选择视觉隐喻、主题色、动态图形类别和运动语言。
3. `timing` 检查阅读时长、同屏密度、字幕位置和出场顺序。
4. `code_director` 使用 DeepSeek V4 Pro 汇总专家报告，输出唯一创意规格。

前三个专家并行运行，代码总监在三者完成后运行。完整输入、输出、模型与耗时保存在项目 `agent_trace.json` 中。

## HyperFrames 生成

代码总监的创意规格与当前逐字稿共同驱动通用 HTML 编译器，逐项目生成：

- 16:9 或 9:16 的独立响应式布局
- 流程、数据、知识关系、故事线等动态场景
- GSAP 入场、持续运动、节点依次出现和退场
- 简体中文底部居中字幕
- `timeline.json` 与 `subtitles.srt`

原稿没有明确数值时禁止生成百分比。所有观众可见文案必须能追溯到逐字稿，禁止出现制作术语。

## 严格渲染与验收

1. 执行 `hyperframes render --strict`，任何 lint 硬错误都终止任务。
2. 用 `ffprobe` 确认视频流、音频流和完整时长。
3. 均匀抽取八个时间点，生成全片联系表。
4. 调用 DeepSeek V4 Flash Vision 检查文字、构图、拥挤、字幕与幕后文案。
5. 视觉评分至少 75 且模型明确通过，才能注册版本。

项目没有 FFmpeg 静态拼接、规则视频或旧版本复制等兜底路径。

## 性能验收

使用 `scripts/benchmark_openjiuwen_60s.py` 连续运行真实 60 秒音频。每轮必须重新上传、转写、调用模型、生成 HTML、渲染和验收。只有全部轮次端到端低于 300 秒，报告才会标记 `stable_under_five_minutes: true`。
