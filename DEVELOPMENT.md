# 开发者文档 · 易声 EasyVoice

普通用户不需要看这里 —— 下载整合包双击即用，见 [README](README.md)。

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

```text
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
