# AGENTS.md

改这个仓库前先读这份。它是工作约定的**正本**——同一条规矩写两遍，迟早只改一遍，所以别往别的文件（CLAUDE.md / README / 注释）复制内容，只留链接。

- 面向用户的说明：[README.md](README.md)（英文 [README.en.md](README.en.md)）
- 环境与打包：[DEVELOPMENT.md](DEVELOPMENT.md)
- 架构与「为什么这么设计」：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Health Stack

- **测试**：`python -m pytest -q`（CI 跑同一套测试，命令是 `pytest -q`，Python 3.12）
  CI 只装 `gradio numpy soundfile opencc-python-reimplemented pytest`——torch 与 qwen-tts 是运行时惰性导入，单测不需要，也别把它们装进来（GB 级依赖 + 会想去下权重）。
- **跑起来**：`python app_main.py`（首启会确保 0.6B 模型在位，缺则从 ModelScope 下载）
- **界面自证**：改 `app/ui.py` 就得起一个服务在浏览器里点一遍再报告。单测抓不到「控件渲染出来是灰的」「CSS 根本没生效」这类问题——这两桩都真实发生过（见下面两条陷阱）。

## 不可破坏的约定

**并发与状态**
- 凡**改写** `_sub_proj`（字幕工程 `gr.State`）的事件必须挂 `concurrency_id=_SUB_CC`，有结构化测试兜着：漏挂不会报错，只会让该 handler 悄悄排进另一条队，串行保证静默失效。
- **只读工程态的事件不能挂 `_SUB_CC`**（例：「停止生成」）。挂了会被排到整批生成之后才执行——用户点了停止，却要等批次跑完才生效。它用 `_SUB_STOP_CC`。
- 生成器 handler 的每一帧都要自己带好按钮状态：**中间帧沿用禁用态**，别用 `_gen_btn` 生成中间帧（它恒带 `interactive=True`，等于允许批次中途再点一次）。复位不能靠 `.then`，异常后 `.then` 不执行，按钮会永久卡在「生成中」。
- **推理与随机状态隔离**：冷加载与前向共用 `_INFER_LOCK`；固定种子请求通过 `_RequestRng` 隔离 Torch CPU/CUDA 状态，保证跨请求互不干扰、同请求跨块/跨 cue 连续。
- **音色库并发与原子写**：音色库 CRUD 须受 `voice_library._LOCK` 保护，写入必须走 `_atomic_file`（兼容 Windows 句柄占用），严禁原地直接覆盖可能正在被读取的文件。

**模型与下载边界**
- `ensure_model` 只在 `_prep_generation` 里、**只对 1.7B** 触发。别提到 `resolve_model_pref` 里去——那条边界是测试和 CI 不产生模型下载的原因，提上去就会开始拉 GB 级权重。
- ModelScope 在 Windows 下下载必须单线程（`max_workers=1`），避免共享 `.msc` 索引并发写坏。
- 引擎异常在 UI 层分流成可行动文案（内存/显存不足 → 建议缩短文本或换极速 0.6B；其余 → 统一失败提示），原始 traceback 只进启动窗口。**不要**把裸异常再弹回界面，也**不要**在文案里写死只有显卡才会出事（CPU 模式同样会 OOM）。

**界面（Gradio 6 实测陷阱）**
- `gr.render` 里生成的控件不会按用途自动启用：动态渲染的下拉/输入框必须显式 `interactive=True`。
- `css=` 里的 `@media` 规则会被重新挂到 `.contain` 下，`.contain` 的**祖先**选择器（如 `.main.fillable`）写在里面永远不生效，且不报错。要动那层结构样式只能进 `head=` 的 `<style>`。
- 界面语言重排：`_relabel_updates(lang)` 的键就是重排目标清单（单一事实源）。新增组件只加进这个 dict，别再维护第二份列表——两份手工同步曾经是隐患。
- `gr.BrowserState` 持久化密钥：必须显式传入持久化 `secret`（存 `presets/.browser-state-key`），否则每次重启服务 Gradio 随机生成新密钥，导致浏览器端 localStorage 设置解密失败被重置。

**文案与 i18n**
- 三语（`zh-Hans` / `zh-Hant` / `en`）的 key 必须齐，`tests/test_i18n.py` 会红。加一条 key 就三份同时加。
- 界面词用普通用户的话，内部枚举（`pending` / `dirty` / `ok`）不得直达界面——状态列走 `_ST_KEYS` 映射。
- 部分测试直接断言中文串（「未保存」「内存不足」「已解析」）。改文案时这些断言是**故意的钉子**，改文案就一起改断言，别把断言放宽成「任意字符串」。

**打包契约**
- 往 README 里加相对链接（文档、图片），必须同步加进 `build.ps1` 第 4 步的文件清单。漏一个，解压后的整合包里那条链接就是死的。
- `-Version` 每次发版显式传，默认值不跟 Release 走（漏传会覆盖上一版产物）。
- `build.ps1` 必须严格保持纯 ASCII 字符，内置路径白名单断言（`Assert-DistPath`），禁止跨越 `dist/` 或跟随链接。
- 启动脚本 `Start EasyVoice.bat` 必须使用 `python.exe -E -s` 启动，防止受主机外部 Python 环境变量污染。

## 改动范围

- 能改文案就不改交互，能改交互就不加功能。不擅自新增弹窗、确认框、设置项或步骤。
- 判断「值不值得改」的依据是真实操作里被卡住、被误导的人，不是审美偏好；理论上的不便、需要动手改数据才能复现的问题不算。
- 改界面视觉后要按真实界面重拍 README 首图（`assets/brand/screenshot.png` / `.en.png`）——README 展示旧界面比不放图更误导。
- 判据要能自己复现：说「某处不生效」之前先量一次（起服点一遍、或故意把它改坏看测试会不会红）。

## 提交与发版

- 用户可见改动同步记进 [CHANGELOG.md](CHANGELOG.md) / [CHANGELOG.en.md](CHANGELOG.en.md) 的「未发布」段（中英两份同改）；发版时再归入对应版本。
- 按功能域合并提交，一条提交说清一件事；message 写实质改动，不写过程词、不加署名。
- **不自动 push、不打 tag、不发 Release**——这些等人明确点头。
