import os
import logging
import warnings
import threading
from app import ui, seed, tts_engine

def main(open_browser: bool = True) -> None:
    # 清掉无害但吓人的控制台噪音：SoX 探测告警(我们用 ffmpeg，不需要 sox) + gradio 内部弃用告警。
    # sox/log.py 在 import 时会把自己的 logger 级别重置回 WARNING，故不能靠 setLevel；
    # 改为阻断其传播到 root 并挂 NullHandler——sox 不碰这两项，能稳定吞掉那段告警块。
    _sox_log = logging.getLogger("sox")
    _sox_log.addHandler(logging.NullHandler())
    _sox_log.propagate = False
    warnings.filterwarnings("ignore", message=".*HTTP_422_UNPROCESSABLE.*")
    ui.config.ensure_dirs()
    tts_engine.add_bundled_ffmpeg_to_path()        # 让 gradio 录音转码能找到随包 ffmpeg(否则录的音色无法播放)
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
