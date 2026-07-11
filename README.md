# FrameCraft-CN

`FrameCraft-CN` 是一个中文口播视频制片工作台。当前新版保留原 React 前端交互体验，后端重做为“轻 API 外壳 + 单项目单 Agent”架构：每个视频项目从素材理解、设计方案、HyperFrames 工程生成、真实渲染、截图验收，到版本注册与用户对话，都由同一个项目 Agent 负责到底。

它的目标不是提供一条写死的脚本流水线，而是提供一个能持续对话、持续改片、真实出片的 Agent 服务。

## 界面与成片示意

演示视频：https://www.bilibili.com/video/BV1Q6jC6QEPv

项目工作台会展示素材区、生成进度、步骤状态和项目聊天，用户可以直接在右侧对话区继续要求 Agent 修改视频：

![FrameCraft-CN 工作台预览](docs/assets/readme/workbench-chat-and-progress.png)

成片阶段支持在人物主画面上叠加由 Agent 设计的信息块、步骤动画和字幕，最终通过 HyperFrames 真实渲染输出：

![FrameCraft-CN 成片示意](docs/assets/readme/final-video-sample.png)

## 这版解决什么问题

- 不再把“分析”“生成”“修补”拆成互相失忆的多个子系统。
- 不再用固定模板、固定脚本或 FFmpeg 拼接去伪装成智能剪辑。
- 不再把失败任务包成成功结果返回。
- 不再让用户只看到冷冰冰的失败状态；项目 Agent 会在聊天里持续同步判断、进展和阻塞原因。
- 不再让不同项目共用上下文；每个项目都是独立 Agent 会话、独立素材目录、独立输出目录。

## 核心架构

```text
React 前端
  -> FastAPI 后端
  -> 当前项目唯一 Agent 会话
  -> Agent 自己分析素材 / 设计动画 / 生成 HyperFrames 工程
  -> HyperFrames 真实渲染 MP4
  -> Agent 截图验收 / 注册版本 / 在聊天区继续沟通
```

后端只负责这些基础能力：

- 项目、素材、版本、聊天记录的数据管理
- 文件上传与下载
- SSE 任务进度推送
- 访问口令校验
- 给 Agent 暴露一组最小工具

真正的剪辑判断、文案取舍、字幕要求、动画块设计、视觉复审和最终是否算“通过”，都必须由同一个项目 Agent 决定并执行。

## 单项目单 Agent 机制

这是这个版本最重要的设计原则。

- `analyze`
- `generate`
- `apply_patch`
- `chat`

以上任务都会启动或恢复“当前项目唯一的 Agent 会话”。

这意味着：

- 同一个项目从头到尾由同一个 Agent 负责。
- 同一个项目同一时刻只允许一个运行中的 Agent 任务。
- 项目之间互不串话、互不泄漏上下文。
- 用户后续在网页里的“继续改这个视频”是真正接着原项目上下文往下做，不是重新随机起一个流程。

## 关键原则

- `generate` 必须由 Agent 自己完成分析、设计、构图、真实 HyperFrames 渲染和验收。
- 禁止用 FFmpeg 拼接、截图轮播、静态 PPT 式兜底冒充成片。
- FFmpeg 只允许用于探测、抽帧、转码、时长检查等辅助动作。
- 如果 Agent 没写出关键产物，任务必须直接失败，不能伪装成功。
- 字幕必须来自真实逐字内容，不能拿总结字幕冒充字幕。
- 项目 Agent 要在聊天区暴露自己的真实执行过程和阻塞原因，而不是单纯回一个“任务失败”。

## 当前能力

- 上传口播视频并生成可继续修改的项目。
- 在同一项目聊天里要求 Agent 改字幕、改布局、改动画、重渲染。
- 生成真实 HyperFrames 工程和真实渲染 MP4。
- 对成片进行版本化管理和下载。
- 可选导出剪映草稿。
- 支持局域网访问和带口令的公网访问。
- 每个项目有独立素材、独立输出、独立聊天、独立 Agent 会话。

## 目录结构

仓库里比较重要的目录如下：

- `backend/`
  FastAPI 后端与项目 Agent 运行控制
- `framecraft-agent/`
  React 前端
- `docs/`
  设计与工作流文档
- `scripts/`
  安装、启动、测试、批量运行脚本
- `outputs/`
  本地产出结果与测试记录
- `deliverables/`
  示例成片与交付文件
- `hyperframes/`
  本地 HyperFrames 依赖仓库

## 安装依赖

在仓库根目录执行：

```bash
./scripts/setup-deps.sh
```

脚本会准备：

- `backend/venv` 的后端依赖
- 项目根的 `hyperframes`
- `framecraft-agent` 前端依赖
- 本机 Agent 运行时可用性检查

建议本机提前具备：

- `python3`
- `node` / `npm`
- `ffmpeg`
- `ffprobe`
- 可用的本机 Agent 运行环境与登录态

## 启动

后端与前端分开启动：

```bash
./scripts/start-backend.sh
./scripts/start-frontend.sh
```

默认新版端口：

- 后端：`http://0.0.0.0:8022`
- 前端：`http://0.0.0.0:5174`

健康检查：

```bash
curl http://127.0.0.1:8022/api/health
```

预期返回：

```json
{"ok":true,"mode":"single-agent"}
```

## 热重载说明

后端启动脚本默认关闭热重载，原因是长时间 Agent 任务在运行过程中会写入运行时文件、截图和状态文件；如果默认开 `--reload`，这些写入很容易把正在跑的任务打断。

开发时如果你明确需要热重载，再手动开启：

```bash
FRAMECRAFT_BACKEND_RELOAD=1 ./scripts/start-backend.sh
```

Windows 下同理：

```bat
set FRAMECRAFT_BACKEND_RELOAD=1
scripts\start-backend.bat
```

## 本机访问与局域网访问

如果只想本机访问：

```bash
FRAMECRAFT_BACKEND_HOST=127.0.0.1 FRAMECRAFT_BACKEND_PORT=8022 ./scripts/start-backend.sh
FRAMECRAFT_FRONTEND_HOST=127.0.0.1 FRAMECRAFT_FRONTEND_PORT=5174 ./scripts/start-frontend.sh
```

如果要让局域网其他电脑访问，先查本机局域网 IP，例如 macOS：

```bash
ipconfig getifaddr en0
```

然后启动后端，并给前端注入可被其他电脑访问的 API 地址：

```bash
./scripts/start-backend.sh
VITE_API_BASE_URL=http://<你的局域网IP>:8022 ./scripts/start-frontend.sh
```

其他电脑访问：

```text
http://<你的局域网IP>:5174/
```

## 公网访问与口令保护

新版后端默认启用访问口令。除 `/api/health` 外，项目、素材、聊天、生成、下载等接口都需要访问口令。

推荐显式设置：

```bash
FRAMECRAFT_ACCESS_TOKEN=<long-random-token> ./scripts/start-backend.sh
```

如果未显式设置，后端会自动生成：

```text
backend/storage/access_token.txt
```

前端行为如下：

- 首次遇到 `401` 会提示输入访问口令
- 输入后保存到当前浏览器 `localStorage`
- 也可以通过 URL 临时传入：

```text
http://<host>:5174/?access_token=<token>
```

默认 CORS 只允许 localhost 与常见局域网私有 IP 来源。如果部署到公网域名，请显式设置：

```bash
FRAMECRAFT_ALLOWED_ORIGINS=https://your-domain.example
```

## 项目工作流

一个典型的视频项目流程如下：

1. 用户在网页端新建项目。
2. 上传主视频或相关素材。
3. 触发 `analyze` 或直接触发 `generate`。
4. 后端启动或恢复当前项目唯一 Agent。
5. Agent 读取当前项目状态、聊天历史、素材信息和现有版本。
6. Agent 产出 `analysis.json` 与 `edit_plan.json`。
7. Agent 设计版式、字幕、动画块、构图与视觉层级。
8. Agent 生成 HyperFrames 工程。
9. HyperFrames 真实渲染 `preview.mp4`。
10. Agent 抽取截图或 contact sheet 做视觉复审。
11. 通过后注册版本，并在聊天里汇报结果。
12. 用户继续在聊天里要求修改，Agent 在同一项目里继续迭代。

## 任务产物门禁

`analyze` 成功前必须存在：

- `outputs/<project_id>/analysis/analysis.json`
- `outputs/<project_id>/analysis/edit_plan.json`

`generate` 和 `apply_patch` 成功前必须存在：

- 已注册的视频版本
- `preview.mp4`
- `timeline.json`
- `agent_visual_review.json`
- HyperFrames 工程痕迹，例如 `hyperframes_project.zip`、`hyperframes/`、`project.tsx` 或 `src/`

如果项目开启 `generate_draft=true`，还必须存在：

- 真实 `jianying_draft.zip`
- 前端版本 `draft_url` 指向真实草稿下载路由

缺少任意关键产物，任务会被标记为 `failed`，并返回明确失败原因。

## 剪映草稿

剪映草稿由：

- [draft_exporter.py](/Users/applemima111/framecraft/FrameCraft-Agent/backend/app/draft_exporter.py:1)

根据统一时间线同步生成。

它的边界很明确：

- 真实视觉验收对象始终是 HyperFrames 预览视频
- 草稿提供可编辑主视频、字幕和信息图层
- 复杂浏览器动画不会被伪装成“完整反编译回剪映原生工程”

如果草稿导出失败，本次任务也必须失败，不能返回空链接或假链接。

## Agent 工具边界

每个 Agent 任务运行时会得到 `framecraft-tool.sh` 一类的受控工具，典型能力包括：

- `read_state`
- `progress`
- `log`
- `write_analysis`
- `write_edit_plan`
- `create_version_dir`
- `register_version`
- `write_chat`
- `probe_media`
- `copy_file`

这些工具只负责状态和文件操作，不负责替 Agent 做创意判断。

## 对“真渲染”的要求

这个项目强调的不是“有一个视频文件”，而是“视频必须真的是 Agent 设计并真实渲染出来的”。

因此这里明确禁止：

- 用 FFmpeg 拼几张静态图冒充高级剪辑
- 截几秒原视频循环播放
- 用假字幕或总结字幕冒充逐字字幕
- 没做视觉复审却声明已经通过验收
- 没生成 HyperFrames 工程却声称可复渲染

## 旧版与备份

本机旧版独立前端目录：

```text
/Users/applemima111/Desktop/framecraft-agent
```

它曾运行在 `5173` 端口，现已停止，并已写入 `OLD_VERSION_NOTICE.md` 标记。

本次重做前的完整项目备份在：

```text
/Users/applemima111/framecraft/FrameCraft-Agent.backup-single-agent-20260619-010256
```

## 重要文档

- [单一 Agent 后端说明](docs/single-codex-agent-backend.md)
- [Agent + HyperFrames 可复现口播制片工作流](docs/codex-hyperframes-reproducible-workflow.md)
- [布局变体说明](docs/layout-variants.md)
- [视频内容类别说明](docs/video-content-categories.md)
- [优先保人像的选材原则](docs/face-first-source-selection.md)

## 常见排查

### 1. 前端能打开，但聊天没有响应

优先检查：

- 后端是否正常启动
- 访问口令是否已填写
- 本机 Agent 运行环境是否可用
- 当前项目是否已经有一个未结束任务在占用

### 2. 可以分析，但生成很快失败

优先检查：

- 是否真的生成了逐字字幕
- HyperFrames 工程是否写出
- 是否真实产出了 `preview.mp4`
- 版本注册前的门禁文件是否齐全

### 3. 外网能打开首页，但接口报 401 或 403

优先检查：

- `FRAMECRAFT_ACCESS_TOKEN`
- `FRAMECRAFT_ALLOWED_ORIGINS`
- 前端是否把口令真正带到了 API 请求

### 4. 长任务运行中后端自己重启

优先检查：

- 是否误开了默认热重载
- 是否有额外文件监控工具在盯着 `outputs/` 或运行时目录

## 仓库定位

这个仓库适合两类场景：

- 你想把“用户上传素材 -> Agent 自主生成和改片 -> 真实出片”做成网页服务
- 你想继续把单项目单 Agent 的视频编辑链路做深，而不是继续堆固定脚本

如果你的目标只是“一条固定模板流水线批量出视频”，那不是这个版本的设计方向。
