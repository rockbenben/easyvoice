# 易声 (EasyVoice)

**简体中文** | [English](README.en.md)

## 项目简介

**易声(EasyVoice)** 是一个基于 [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) 的本地**多语言**傻瓜配音 / 声音克隆工具（中文界面，开箱即用），特点如下：

- **多语言配音 / 克隆**：支持中文、英文、日文、韩文、德文、法文、俄文、葡萄牙文、西班牙文、意大利文共 **10 种语言**，3 秒参考音频即可克隆音色
- **字幕配音**：上传字幕（SRT / VTT / LRC），按时间轴生成对齐的整段配音，并导出对齐后的字幕
- **本地运行**：全程本地推理，不上传云端，保护隐私
- **显卡自适应**：有 GPU 自动使用 CUDA 加速，无显卡自动降级到 CPU
- **开箱即用**：普通用户下载整合包解压双击启动，开发者可本地源码运行

---

## 普通用户使用（3 步）

### 第 1 步：下载并解压
下载整合包，解压到本地目录。

### 第 2 步：双击启动
在目录里双击 `Start EasyVoice.bat`，首次启动约需 30 秒（加载模型）。

> **注意**：双击启动需要整合包（自带 `runtime/` 运行时与模型）。整合包可用项目内的 `build.ps1` 自行打包；预编译整合包见 [Releases](../../releases)（如已提供）。源码运行见下方**开发者运行**。

### 第 3 步：浏览器中使用
启动后自动打开浏览器 `http://127.0.0.1:7860`，共四个标签页：

- **配音**：输入文本，选择语言与参考音色，点击生成
- **字幕配音**：上传字幕文件，按时间轴生成对齐配音
- **我的音色库**：管理参考音色（添加、删除、重命名、调序）
- **常用方案**：保存常用的配音参数预设（语言 + 音色），快速调用

---

## 开发者运行（本地源码）

### 环境要求
- **Python 3.12**（示例使用 conda 环境 `easyvoice`）

### 安装步骤

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **安装 PyTorch CUDA 版**（若有 GPU）
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
   （若无 GPU，跳过此步，CPU 版会在第一步自动安装）

3. **（可选）变速功能需要 ffmpeg**：将 `ffmpeg.exe` 放到 PATH 或项目 `ffmpeg/` 目录；缺失时语速≠1.0 会自动优雅降级。

4. **模型**：首次运行自动从 ModelScope 下载到 `models/`。自定义缓存路径可设环境变量 `MODELSCOPE_CACHE`。

### 运行应用
```bash
python app_main.py
```
浏览器自动打开 `http://127.0.0.1:7860`。

### 运行测试
```bash
python -m pytest -q
```
全量回归测试应全部通过。

---

## 项目结构

```
easyvoice/
├── app/                  # 应用核心模块
│   ├── config.py         # 全局配置（路径、模型名、支持语言）
│   ├── i18n.py & i18n/   # 界面多语言（简体 / 繁体 / English）
│   ├── voice_library.py  # 音色库管理（增删改查、调序）
│   ├── presets.py        # 预设管理（保存 / 加载参数组合）
│   ├── seed.py           # 首次启动的示例音色 / 预设
│   ├── tts_engine.py     # TTS 引擎（加载、合成、分段、字幕对齐、变速）
│   └── ui.py             # Gradio UI（四标签页）
├── app_main.py           # 应用入口
├── build.ps1             # 整合包打包脚本（conda-pack 运行时 + 模型 + ffmpeg）
├── Start EasyVoice.bat   # Windows 用户启动脚本
├── requirements.txt      # Python 依赖
├── pyproject.toml        # pytest 配置
└── tests/                # 自动化测试
```

> `models/`、`voices/`、`presets/`、`outputs/`、`runtime/`、`ffmpeg/`、`dist/` 为运行时 / 打包产物，已在 `.gitignore` 中忽略。

---

## 整合包打包（可选）

用 `build.ps1` 可一键把已验证的 conda 环境打成「解压双击即用」的整合包（内置 Python 运行时 + 模型权重 + ffmpeg）：

```powershell
pwsh -File build.ps1
```
产物为 `dist/EasyVoice-vX.Y/` 目录与同名 `.zip`。注意整合包约数 GB，超过 GitHub Release 单文件 2 GB 上限，建议分卷或走外部托管分发。

---

## 致谢与许可

- 本项目自身代码采用 **MIT License**（见 [LICENSE](LICENSE)）。
- 基于 **[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)**（模型权重 Apache License 2.0）。
- 整合包内含的第三方组件（Qwen3-TTS 模型 / FFmpeg 等）的许可与来源见 [THIRD-PARTY-NOTICES](assets/packaging/THIRD-PARTY-NOTICES.txt)。

---

## 更多资源

- Qwen3-TTS：https://github.com/QwenLM/Qwen3-TTS
- ModelScope：https://modelscope.cn
- Gradio：https://www.gradio.app
