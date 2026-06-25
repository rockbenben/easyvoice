# SPIKE: qwen-tts 0.1.1 真实 API 记录

**日期：** 2026-06-22  
**模型：** `Qwen/Qwen3-TTS-12Hz-0.6B-Base`（本地路径 `models/Qwen/Qwen3-TTS-12Hz-0___6B-Base`）  
**包版本：** qwen-tts 0.1.1 · torch 2.5.1+cu121 · soundfile 0.14.0  
**环境：** Python 3.12.13 · conda env `easyvoice` · RTX 3080 Ti 12GB CUDA 12.1  
**目的：** 实测确认真实 Python API，为 Task 5 tts_engine 编码提供可直接抄用的调用。

---

## 1. 安装

```bash
# 1. PyTorch CUDA build（必须先装，否则 qwen-tts 安装后无 GPU）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 2. qwen-tts + 音频依赖
pip install qwen-tts soundfile modelscope
```

**安装摩擦点：**
- `sox` 系统命令不在 PATH 时，import 时会打印警告（`'sox' is not recognized`），但**不影响功能**——pydub/sox python 包已安装，核心推理走 torch 不依赖 sox 二进制。
- `flash-attn` 未安装时同样打印警告；推理仍可运行（纯 PyTorch attention），速度慢一些。
- `torch_dtype` 已废弃，应改用 `dtype`（下游调用直接用 `dtype=torch.bfloat16`）。
- 模型从 ModelScope 下载时符号链接创建失败（Windows 权限），实际文件路径为 `models/Qwen/Qwen3-TTS-12Hz-0___6B-Base`（注意三个下划线）；下载本身成功。

---

## 2. 顶层导出

```python
import qwen_tts
# qwen_tts.__all__ = ['Qwen3TTSModel', 'Qwen3TTSTokenizer', 'VoiceClonePromptItem']
```

公开的三个名称：
| 名称 | 类型 | 用途 |
|------|------|------|
| `Qwen3TTSModel` | class | 主推理包装器，所有合成操作入口 |
| `Qwen3TTSTokenizer` | class | 底层 tokenizer（通常不直接使用） |
| `VoiceClonePromptItem` | dataclass | 预计算 prompt 的容器（可选） |

---

## 3. 加载模型（load_model 真实写法）

```python
import torch
import qwen_tts

model = qwen_tts.Qwen3TTSModel.from_pretrained(
    "D:/path/to/models/Qwen/Qwen3-TTS-12Hz-0___6B-Base",  # 本地路径 or HuggingFace repo id
    device_map="cuda:0",       # GPU 设备；支持 "cpu"、"auto"
    dtype=torch.bfloat16,      # 推荐 bfloat16 节省显存；不传则用 float32
)
```

**说明：**
- `from_pretrained` 内部调用 `AutoConfig.register` + `AutoModel.from_pretrained` + `AutoProcessor.from_pretrained`，不需要手动注册任何自定义类。
- `**kwargs` 直接转发到 `AutoModel.from_pretrained`，因此所有 HuggingFace 标准参数均有效（如 `attn_implementation="flash_attention_2"` 等）。
- 返回类型为 `Qwen3TTSModel`（包含 `.model`、`.processor`、`.generate_defaults` 三个属性）。

---

## 4. 支持语言列表

```python
langs = model.get_supported_languages()
# 返回: ['auto', 'chinese', 'english', 'french', 'german', 'italian',
#        'japanese', 'korean', 'portuguese', 'russian', 'spanish']
```

- 返回 `Optional[List[str]]`，已排序，全小写。
- `'auto'` 表示自动检测语种。
- 若模型不暴露语言约束则返回 `None`。

```python
speakers = model.get_supported_speakers()
# 对 0.6B Base 模型返回: []（Base 模型不内置 speaker，需传参考音频）
```

---

## 5. 合成方法

### 5a. `generate_voice_clone`（Base 模型的主要方法）

**签名（实测）：**
```python
wavs, sample_rate = model.generate_voice_clone(
    text="你好，这是克隆合成测试。",   # str 或 List[str]（批量）
    language="chinese",               # 可选，默认 "Auto"；见支持语言列表
    ref_audio=ref_audio_path,         # 参考音频（见下方格式说明）
    ref_text=None,                    # 参考音频对应文本（ICL 模式需要，x_vector_only 可省略）
    x_vector_only_mode=True,          # True=只用 speaker embedding；False=ICL 模式（需 ref_text）
    non_streaming_mode=True,          # True=单次完整生成（推荐）；False=模拟流式
    # 可选生成参数：
    # do_sample=True, top_k=50, top_p=0.9, temperature=0.9,
    # repetition_penalty=1.0, max_new_tokens=2048
)
```

**返回值（实测）：**
```python
# wavs: List[np.ndarray]，每个元素 shape=(N,)，dtype=float32，range≈[-1, 1]
# sample_rate: int = 24000
print(type(wavs))        # <class 'list'>
print(wavs[0].shape)     # (82560,) — 约 3.44s @ 24kHz（文本决定长度）
print(wavs[0].dtype)     # float32
print(sample_rate)       # 24000
```

**保存到文件：**
```python
import soundfile as sf
sf.write("output.wav", wavs[0], sample_rate)
```

### 5b. `generate_voice_design`（Instruct/大模型专用）

```python
# 仅适用于 Instruct 模型（非 Base）；0.6B Base 调用时抛 ValueError
wavs, sr = model.generate_voice_design(
    text="...",
    instruct="A warm, friendly female voice.",
    language="english",
    non_streaming_mode=True,
)
```

> **注意：** `Qwen/Qwen3-TTS-12Hz-0.6B-Base` 不支持此方法，会抛出：  
> `ValueError: model with tts_model_type: base does not support generate_voice_design`

### 5c. `generate_custom_voice`（内置 speaker，Instruct 专用）

```python
wavs, sr = model.generate_custom_voice(
    text="...",
    speaker="Chelsie",    # 内置 speaker 名称
    language="english",
    non_streaming_mode=True,
)
# 同样：Base 模型不支持，仅 Instruct 模型有内置 speaker 列表
```

---

## 6. 参考音频格式（ref_audio 支持的所有形式）

```python
# 形式 1：WAV 文件路径（str）
ref_audio = "/path/to/reference.wav"

# 形式 2：URL（str，http/https）
ref_audio = "https://example.com/voice.wav"

# 形式 3：base64 音频字符串（str）
ref_audio = "<base64-encoded-audio-string>"

# 形式 4：numpy + sample_rate 元组
ref_audio = (np_array, 24000)   # np_array: np.ndarray, shape=(N,), dtype=float32

# 形式 5：以上任意形式的列表（批量）
ref_audio = [path1, (np2, sr2), url3]
```

实测验证：**路径**和 **(numpy, sr) 元组** 均可正常调用。

---

## 7. 两阶段 API：`create_voice_clone_prompt`

```python
# 可预先处理参考音频（适合同一 speaker 多次合成时复用）
prompts = model.create_voice_clone_prompt(
    ref_audio=(np_array, sr),   # 同上支持格式
    ref_text=None,              # str 或 None
    x_vector_only_mode=True,    # True=只用 x-vector
)
# 返回: List[VoiceClonePromptItem]
# VoiceClonePromptItem 字段：
#   .ref_code: Optional[torch.Tensor]    # (T, Q) 或 (T,)
#   .ref_spk_embedding: torch.Tensor     # (D,) speaker embedding
#   .x_vector_only_mode: bool
#   .icl_mode: bool
#   .ref_text: Optional[str]

# 然后传入 generate_voice_clone：
wavs, sr = model.generate_voice_clone(
    text="...",
    language="chinese",
    voice_clone_prompt=prompts,   # 代替 ref_audio 参数
    non_streaming_mode=True,
)
```

---

## 8. 实测运行结论

| 测试项 | 结果 |
|--------|------|
| `torch.cuda.is_available()` | `True`（RTX 3080 Ti，cu121） |
| 模型加载到 `cuda:0` | 成功（bfloat16） |
| `get_supported_languages()` | 11 种语言 + `auto` |
| `generate_voice_clone(path, x_vector_only=True)` | 成功，返回 `(List[np.ndarray], 24000)` |
| `generate_voice_clone((np,sr), x_vector_only=True)` | 成功 |
| `create_voice_clone_prompt` | 成功，返回 `List[VoiceClonePromptItem]` |
| `generate_voice_design`（Base 模型） | 失败（预期）：Base 不支持 |
| ICL 模式（`x_vector_only=False` + `ref_text`） | 后实测：会把 `ref_text` 诵进输出（+ref_text 时长），**生产已移除**该路径，统一用 `x_vector_only=True` |
| `generate_custom_voice` | **未实测**（Base 无内置 speaker） |

---

## 9. 后续 Task 5 的关键信息

1. **导入：** `from qwen_tts import Qwen3TTSModel`
2. **加载：** `Qwen3TTSModel.from_pretrained(local_path, device_map="cuda:0", dtype=torch.bfloat16)`
3. **推理：** `model.generate_voice_clone(text, language, ref_audio, x_vector_only_mode, non_streaming_mode=True)` → `(List[np.ndarray], int)`
4. **语言列表：** `model.get_supported_languages()` → list of 11 strings
5. **音频保存：** `soundfile.write(path, wavs[0], sample_rate)`
6. **ref_audio 推荐格式：** WAV 文件路径（str）最简单；也支持 `(np.ndarray, sr)` 元组
7. **SoX 警告**：在 PATH 中安装 sox 系统工具可消除，但非必需
8. **模型路径注意：** ModelScope 下载后实际目录名含三个下划线 `0___6B-Base`（Windows 符号链接创建失败）
