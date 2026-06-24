import os
import threading
from app import ui, seed, tts_engine

def main(open_browser: bool = True) -> None:
    ui.config.ensure_dirs()
    os.environ.setdefault("MODELSCOPE_CACHE", str(ui.config.MODELS_DIR))
    tts_engine.ensure_model(ui.config.MODEL_06B)   # 缺模型则先下载(带进度)，下完再起界面
    seed.seed_defaults()
    demo = ui.build_ui("zh-Hans")
    # 后台预热模型，避免首次生成时干等加载(~15-30s)
    threading.Thread(target=tts_engine.warmup, daemon=True).start()
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=open_browser,
                theme=ui.THEME, css=ui.CSS, head=ui.HEAD, i18n=ui.I18N,
                favicon_path=ui.FAVICON,
                # 生成的音频在 outputs/（不在 CWD/临时目录下时 Gradio 默认拒绝外发），
                # 显式放行，否则播放/下载会报 InvalidPathError。
                allowed_paths=[str(ui.config.OUTPUTS_DIR)])

if __name__ == "__main__":
    main()
