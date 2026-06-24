# 易声 (EasyVoice)

## 项目简介

**易声(EasyVoice)** 是一个基于 Qwen3-TTS 的中文傻瓜配音/声音克隆工具，具有以下特点：

- **多语言支持**：中文、英文、日文、韩文、德文、法文、俄文、葡文、西班牙文、意大利文声音克隆
- **本地运行**：无需上传到云端，保护隐私
- **显卡自适应**：有 GPU 自动使用 CUDA 加速，无显卡自动降级到 CPU
- **开箱即用**：普通用户下载解压双击启动，开发者本地源码运行

---

## 普通用户使用（3 步）

### 第 1 步：下载并解压
下载项目的整合包或源码，解压到本地目录。

### 第 2 步：双击启动
在项目根目录双击 `Start EasyVoice.bat` 文件，首次启动约需 30 秒。

> **注意**：双击 `Start EasyVoice.bat` 需要阶段二整合包（提供 `runtime/` 运行时目录）；如使用当前源码版本，请按下方**开发者运行**步骤启动。

### 第 3 步：浏览器中使用
启动后自动打开浏览器，访问 `http://127.0.0.1:7860`，可看到三个标签页：

- **配音**：输入文本，选择语言和参考音频，点击生成配音
- **我的音色库**：管理已保存的参考音色（添加、删除、重命名）
- **常用流程**：保存常用的配音参数预设（语言 + 音色），快速调用

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

3. **下载模型**（可选）
   
   模型会自动从 ModelScope 下载到 `models/` 目录。
   
   如需自定义缓存路径，设置环境变量：
   ```bash
   set MODELSCOPE_CACHE=D:\path\to\models
   ```

### 运行应用
```bash
python app_main.py
```

浏览器自动打开 `http://127.0.0.1:7860`。

---

## 运行测试

执行全量回归测试（共 21 个测试用例）：
```bash
python -m pytest -v
```

所有测试应为 PASS。

---

## 项目结构

```
018/
├── app/                       # 应用核心模块
│   ├── config.py             # 全局配置（路径、模型名、支持语言）
│   ├── i18n.py & i18n/       # 多语言支持（中、英、繁体）
│   ├── voice_library.py       # 音色库管理（增删改查）
│   ├── presets.py            # 预设管理（保存/加载参数组合）
│   ├── tts_engine.py         # TTS 引擎（模型加载、合成、简繁转换）
│   └── ui.py                 # Gradio UI 界面（三标签页构建）
├── app_main.py               # 应用入口
├── Start EasyVoice.bat              # Windows 用户启动脚本
├── models/                   # 下载的模型文件目录
├── voices/                   # 参考音频存放目录
├── presets/                  # 预设配置文件目录
├── outputs/                  # 合成输出目录
├── requirements.txt          # Python 依赖列表
├── pyproject.toml            # pytest 配置
└── tests/                    # 自动化测试
```

### 关键目录说明

- **models/**：存放 Qwen3-TTS 模型权重（0.6B / 1.7B），自动从 ModelScope 下载
- **voices/**：保存用户上传的参考音频文件（音色库条目）
- **presets/**：存放预设配置（JSON 格式，含语言 + 音色映射）
- **outputs/**：合成完成的 WAV 音频输出目录

---

## 阶段二：打包（下一步）

当前为**开发阶段**，支持源码运行和测试。

**阶段二计划**（待后续实现）：
- 将 Python 环境、依赖、模型打包成单个 `.exe` 或整合包
- 内嵌运行时和模型权重，实现"解压双击即用"
- 详见 `build.ps1` 和项目计划二

---

## 致谢与许可

本项目基于 **[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)**，采用 **Apache License 2.0** 许可。

**声明**：本项目使用了 Qwen3-TTS 模型权重，权重同样受 Apache License 2.0 保护。

---

## 更多资源

- Qwen3-TTS 官方文档：https://github.com/QwenLM/Qwen3-TTS
- ModelScope 模型平台：https://modelscope.cn
- Gradio UI 框架：https://www.gradio.app
