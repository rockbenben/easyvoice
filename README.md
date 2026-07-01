# 易声 (EasyVoice)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/) [![Release](https://img.shields.io/github/v/release/rockbenben/easyvoice)](https://github.com/rockbenben/easyvoice/releases/latest) [![Powered by Qwen3-TTS](https://img.shields.io/badge/Powered%20by-Qwen3--TTS-orange.svg)](https://github.com/QwenLM/Qwen3-TTS)

**简体中文** | [English](README.en.md)

> 365 开源计划 #018 · 基于 Qwen3-TTS 的本地多语言傻瓜配音 / 声音克隆工具，中文界面、开箱即用

## 项目简介

**易声(EasyVoice)** 是一个基于 [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) 的本地**多语言**傻瓜配音 / 声音克隆工具（中文界面，开箱即用），特点如下：

- **3 秒声音克隆**：上传或录制约 3 秒参考音频，即可克隆出该音色，用于任意文本 / 字幕配音
- **多语言配音**：支持中文、英文、日文、韩文、德文、法文、俄文、葡萄牙文、西班牙文、意大利文共 **10 种语言**，默认「自动识别语种」，也可手动指定
- **省心**：配音参数（语言 / 音色 / 风格 / 语速等）自动记忆，下次打开沿用
- **字幕配音（多角色）**：上传字幕（SRT / VTT / LRC），按行首「名字：」前缀自动分配说话人音色、逐条试听 / 改词 / 重录，按时间轴对齐生成，并可直接合进原视频（导出成片 + 对齐字幕）。无说话人前缀的普通字幕同样支持（单一音色）；正文含冒号时可关闭「字幕含说话人前缀」开关避免误拆
- **本地运行**：全程本地推理，不上传云端，保护隐私
- **显卡自适应**：有 GPU 自动使用 CUDA 加速，无显卡自动降级到 CPU
- **音质可选（有 N 卡时）**：在「极速 0.6B / 高质 1.7B」两档模型间手动切换（首次用 1.7B 自动下载）；无显卡固定 0.6B
- **开箱即用**：普通用户下载整合包解压双击启动，开发者可本地源码运行

---

## 下载

前往 **[Releases](../../releases/latest)** 下载，两种整合包任选：

> 🇨🇳 **国内下载（更快）**：<https://alist.newzone.top:9003/apps/EasyVoice>

| 包 | 体积 | 适用 | 模型 |
|---|---|---|---|
| **完整大包**（GPU/CPU 自适应） | ~4.6GB（分 3 卷） | 有 N 卡 / 追求速度 | 内置 |
| **CPU 精简包** | **~0.5GB（单文件）** | 无显卡 / 想要小包 | 首启在工具内下载（~1.8GB） |

- **完整大包**：下载 `EasyVoice-v1.1.0.zip.01/.02/.03` + `merge-and-extract.bat` 到同一文件夹，双击 bat 自动合并解压。
- **CPU 精简包**：下载单个 `EasyVoice-v1.1.0-cpu.zip`，解压即用。⚠️ **CPU 生成较慢**：约每句 20–40 秒（视机器）、长段落数分钟，适合短句/预览。有 N 卡求速度请用完整大包。

---

## 普通用户使用（3 步）

### 第 1 步：下载并解压
按上方 [下载](#下载) 选一种整合包，解压到本地目录。

### 第 2 步：双击启动
在目录里双击 `Start EasyVoice.bat`，首次启动约需 30 秒（加载模型）。

> **注意**：双击启动需要整合包（自带 `runtime/` 运行时与模型）。整合包可用项目内的 `build.ps1` 自行打包；预编译整合包见 [Releases](../../releases)（如已提供）。源码运行见下方**开发者运行**。

### 第 3 步：浏览器中使用
启动后自动打开浏览器 `http://127.0.0.1:7860`，共四个标签页：

- **配音**：输入文本，选择语言（默认自动）与参考音色，点击生成
- **字幕配音**：上传字幕 → 按说话人分配音色 → 逐条挑错（试听 / 改词 / 重录）→ 合成导出（可合进原视频）
- **我的音色库**：上传或录制参考音色并管理（添加、删除、重命名、调序、试听）
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
│   ├── tts_engine.py     # TTS 引擎（加载、合成、分段、字幕对齐、变速、模型选择）
│   ├── dubbing_project.py# 字幕配音工程态（说话人识别 / 逐条生成·重录 / 拼装）
│   ├── video_mux.py      # 把配音合进视频（ffmpeg）
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

用 `build.ps1` 把已验证的 conda 环境打成「解压双击即用」的整合包：

```powershell
pwsh -File build.ps1                 # 完整大包：GPU/CPU 自适应、内置模型（约 4.6GB）
pwsh -File build.ps1 -Variant cpu    # CPU 精简包：无 CUDA、不含模型（约 0.5GB；模型首启在工具内下载）
```
产物为 `dist/EasyVoice-vX.Y[-cpu]/` 目录与同名 `.zip`。完整大包超过 GitHub Release 单文件 2 GB 上限，需分卷（配 `merge-and-extract.bat`）或走外部托管；CPU 精简包单文件即可上传。

---

## 更新记录

以下修复已在源码中，将随下次整合包一并发布（下载包仍为 v1.1.0）：

- **字幕配音 · 说话人识别**：收紧行首「名字：」前缀识别——含空格的多词短语、纯数字时间（如 `12:30`）不再被误当说话人而吞掉正文；并新增「字幕含说话人前缀」开关，可对含冒号的普通字幕一键关闭识别、整行按单一音色配音。
- **字幕配音 · 替换原声导出**：导出视频完整保留到片尾。此前当配音短于视频（最后一句字幕在片尾前结束）时，尾部画面会被静默截断，现已补齐到视频完整长度。
- **字幕配音 · 并发稳定性**：对同一字幕工程的多项操作（解析 / 改词 / 重录 / 生成全部 / 导出）串行执行，避免并发点击导致工程状态错乱、导出异常。
- **稳定性 · GPU 串行**：跨「配音 / 字幕配音」标签页的生成改为串行，避免同时生成导致显存溢出（OOM）或音频损坏。
- **配音 · 音色删除**：生成过程中所选音色被删除时给出友好提示，不再抛出原始报错。

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

---

## 关于 365 开源计划

本项目是 [365 开源计划](https://github.com/rockbenben/365opensource) 的第 18 个项目。

一个人 + AI，一年 300+ 个开源项目。[提交你的需求 →](https://my.feishu.cn/share/base/form/shrcnI6y7rrmlSjbzkYXh6sjmzb)
