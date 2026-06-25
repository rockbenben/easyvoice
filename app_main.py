import os
import logging
import warnings
import threading
import traceback as _traceback
from app import ui, seed, tts_engine


class _QuietClientCancelNoise(logging.Filter):
    """吞掉浏览器取消媒体请求(音频试听拉取够了就主动断开)引发的无害报错噪音：
    h11 'Too little data for declared Content-Length' + WinError 10054 连接重置。
    这类报错并非服务端故障——文件其实正常外发，只是客户端中途取消，详见 RangedFileResponse。"""
    _N = ("Too little data for declared Content-Length", "WinError 10054",
          "ConnectionResetError", "_call_connection_lost")

    def filter(self, record):
        try:
            blob = record.getMessage()
            if record.exc_info:
                blob += "".join(_traceback.format_exception(*record.exc_info))
        except Exception:
            return True
        return not any(n in blob for n in self._N)


def main(open_browser: bool = True) -> None:
    # 吞掉浏览器取消音频拉取导致的无害 ASGI/连接重置噪音(不影响功能，仅清控制台)
    _qf = _QuietClientCancelNoise()
    for _ln in ("uvicorn.error", "uvicorn", "asyncio"):
        logging.getLogger(_ln).addFilter(_qf)
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
                # 放行 outputs/(生成结果) 与 voices/(音色库试听)，否则 Gradio 拒绝外发本地文件
                allowed_paths=[str(ui.config.OUTPUTS_DIR), str(ui.config.VOICES_DIR)])

if __name__ == "__main__":
    main()
