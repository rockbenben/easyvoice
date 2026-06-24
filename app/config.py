from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICES_DIR = ROOT / "voices"
PRESETS_DIR = ROOT / "presets"
OUTPUTS_DIR = ROOT / "outputs"
MODELS_DIR = ROOT / "models"

MODEL_06B = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
MODEL_17B = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

# code 必须与 model.generate_voice_clone(language=...) 接受的字符串一致
# (见 docs/SPIKE-qwen-tts.md §4 get_supported_languages())
SUPPORTED_LANGS = [
    {"code": "chinese", "label_key": "lang.zh"},
    {"code": "english", "label_key": "lang.en"},
    {"code": "japanese", "label_key": "lang.ja"},
    {"code": "korean", "label_key": "lang.ko"},
    {"code": "german", "label_key": "lang.de"},
    {"code": "french", "label_key": "lang.fr"},
    {"code": "russian", "label_key": "lang.ru"},
    {"code": "portuguese", "label_key": "lang.pt"},
    {"code": "spanish", "label_key": "lang.es"},
    {"code": "italian", "label_key": "lang.it"},
]

def ensure_dirs() -> None:
    for d in (VOICES_DIR, PRESETS_DIR, OUTPUTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
