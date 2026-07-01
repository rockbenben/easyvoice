# 易声 (EasyVoice) 架构与设计

> 面向维护者的系统总览：模块职责、两条主数据流、以及关键设计决策的**为什么**。
> qwen-tts 库的真实 API 见 [SPIKE-qwen-tts.md](SPIKE-qwen-tts.md)（冻结的调研记录）。

## 1. 总览

单机本地的 Gradio 应用，基于 Qwen3-TTS 做声音克隆 + 多语言配音。全程本地推理，不上云。

- **入口** `app_main.py::main()`：建目录 → 把随包 `ffmpeg/` 前置进 `PATH` → 确保 0.6B 模型（缺则下载）→ 播种示例音色/预设 → `build_ui()` → 后台线程预热模型 → `demo.launch()` 绑定 `127.0.0.1:7860`，`allowed_paths=[outputs, voices]`（否则 Gradio 拒绝外发本地音频）。
- **四个标签页**（`app/ui.py`）：配音 · 我的音色库 · 常用方案 · 字幕配音。
- **数据落盘**：`voices/`（音色库 + `index.json`）、`presets/`（每方案一个 JSON）、`outputs/`（生成结果）、`models/`（权重）；均在 `.gitignore` 里。

## 2. 模块职责

| 模块 | 职责 |
|---|---|
| `config.py` | 路径常量、`MODEL_06B/17B`、`SUPPORTED_LANGS`（10 种） |
| `tts_engine.py` | 模型加载/缓存、合成、分段、字幕解析、时间轴拼接、变速、模型档位解析 |
| `dubbing_project.py` | 字幕配音工程态：说话人识别、逐条生成/重录、cue 状态机、拼装 |
| `voice_library.py` | 音色库 CRUD + 排序（`index.json`） |
| `presets.py` | 方案保存/读取（文件名安全化 + 冲突校验） |
| `seed.py` | 首启空库时播种示例音色/预设（幂等） |
| `video_mux.py` | 用 ffmpeg 把配音合进视频（替换/保留原声） |
| `i18n.py` + `i18n/*.json` | 简体/繁体/English 三语 |
| `ui.py` | Gradio 界面、事件接线、并发策略、持久化、语言重排 |

## 3. 主数据流

### 3a. 配音（文本 → 语音）
`do_generate` → `tts_engine.synthesize`：归一文本（繁→简，仅中文）→ 解析模型档位 → 超 200 字按句/逗号/字数切块 → 逐块 `generate_voice_clone`（x-vector 克隆模式）→ 去首尾异常静音 → 多块间插 0.25s 停顿拼接 → 写 WAV → 变速≠1.0 时 `ffmpeg atempo`（缺 ffmpeg 优雅降级为原速）。

### 3b. 字幕配音（字幕 → 多说话人配音 → 视频）
1. **解析**（`build_project`）：`parse_subtitles_ex` 解析 SRT/VTT/LRC（去 BOM、丢弃起点 >6h 的异常时间戳）→ 按行首「名字：」前缀识别说话人 → 建 cue 列表，每 cue 状态 `pending`。
2. **配角**：每个说话人一个音色下拉（`gr.render` 动态渲染），改音色把该角色所有 cue 标 `dirty`。
3. **挑错**：逐条试听/改词（标 `dirty`）/重录（新随机种子重生该条）。
4. **生成全部**（`generate_all`）：只重生 `pending/dirty/error` 的 cue（`ok` 跳过省时，`error` 重试）。
5. **导出**（`assemble` → `assemble_timeline`）：只取 `ok` 的 cue，按 `start` 放上时间轴，超时隙则限速压缩（≤1.5×）贴轴，重叠则后者覆盖；导出反映实际时长的对齐 SRT；有视频则 `video_mux.mux` 合成成片。

**cue 状态机**：`pending →(生成)→ ok/error`；改词/换音色/改角色 →`dirty`；`generate_all` 重生 `pending/dirty/error`；`assemble` 只用 `ok`（跳过的条数用 `gr.Info` 明示，避免静默缺字）。

## 4. 关键设计决策（为什么）

### 4.1 并发串行——两层锁，职责不重叠
Gradio `demo.queue()` 默认 `default_concurrency_limit=1`：**同 `concurrency_id`** 的事件串行，**不同 id** 可并行。
- **字幕同工程串行**：解析/改词/重录/生成全部/导出共享 `concurrency_id="ev_sub_project"`，避免并发改同一 `gr.State` 工程 dict 造成状态错乱/导出错乱。
- **GPU 前向串行**：配音 Tab 与字幕 Tab 的生成事件 id 不同、可被同时调度，故在引擎层用进程级 `_INFER_LOCK` 裹住 `generate_voice_clone` 调用（在 `_load` 之后取锁，不与 `_LOAD_LOCK` 嵌套，无死锁），避免并发前向致显存翻倍 OOM / CUDA 竞争。
- 模型缓存 `_LOAD_LOCK` 双检锁：预热线程与首个生成请求不会重复加载。

### 4.2 模型档位
`resolve_model_pref(pref)`：CPU 恒 0.6B（忽略 pref）；GPU 下 `auto`=有 1.7B 就用否则 0.6B，`0.6b`/`1.7b` 照选。0.6B 是常驻基座（启动即 `ensure`），1.7B 由 `_ensure_local` 在选中时**懒下载**（不触碰 CI/测试的下载路径）。

### 4.3 说话人前缀识别 + 开关
`SPEAKER_RE` 只把「**单个词**（不含空白/冒号）、≤20 字、且**非纯数字**」的行首前缀当说话人——避免把普通字幕里的冒号（`12:30`、`Note:`、URL）误当说话人而吞掉正文。另有「字幕含说话人前缀」开关（默认开），可对含冒号的普通字幕一键关闭识别、整行按单一音色配音。

### 4.4 视频合成——保留视频完整长度
配音常短于视频（末句字幕多在片尾前）。替换原声分支用 `-af apad` 把配音补静音到无限长，再由 `-shortest` 收到视频长度 → 输出恒等于视频时长（短则补静音到片尾、长则按视频截）。保留原声分支由原声轨 `amix=duration=longest` 锚定长度。ffmpeg 缺失/失败 → `mux` 返回 `None`，UI 降级为只给「音频 + 字幕」并 `gr.Warning`。

### 4.5 参数持久化 ↔ 风格
配音设置——语言 / 音色 / 风格 / 语速 / top_k / 重复惩罚 / 最大长度 / 种子 / 模型——存 `gr.BrowserState`（浏览器 localStorage）。**唯独不持久化 temperature/top_p**：它们由「风格」经 `do_apply_style` 派生，只需持久化风格，重载时恢复风格→重算二者（避免独立持久化引发的覆盖循环）。套用预设时同步风格芯片（由温度反推档位），使芯片/滑块/重载三者一致。

### 4.6 界面语言
`gr.I18n` 按浏览器语言自动本地化；运行时无法改 locale，故 `demo.load` 时用服务端 `_relabel` 确定性重排全部组件（含 Tab 标签、下拉 choices）。手动切换经 `?__lang=` + localStorage。

### 4.7 错误 UX
- 生成用**生成器** handler：先 `yield` 禁用按钮（生成中），无论成功/出错都 `yield` 复位——不能用 `.then` 复位，异常后 `.then` 不执行会把按钮永久卡在「生成中」。
- 友好 `gr.Error`：音色中途被删（文件消失）、未选行、无可导出内容等给中英友好提示，真实错误仍原样冒泡不掩盖。
- 优雅降级：ffmpeg 缺失（变速/合成）、输出目录不可写、超长时间戳等都降级而非崩溃。

## 5. 测试
`tests/` 覆盖各模块纯函数与 UI handler（mock 掉真实 TTS/ffmpeg），CI 无模型下载。运行：
```bash
python -m pytest -q
```
