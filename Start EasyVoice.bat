@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem First run: relocate the embedded runtime to this machine (once, ~1 min)
if not exist "runtime\.unpacked" (
  echo Initializing runtime, please wait...  -  首次启动，正在初始化运行环境，请稍候...
  "%~dp0runtime\Scripts\conda-unpack.exe"
  echo ok> "runtime\.unpacked"
)
echo Starting EasyVoice, loading the model (~30s)...  -  正在启动，首次加载模型约 30 秒，请稍候...
echo.
echo [ Quit: close THIS window when done (closing the browser alone won't quit), or click the on-page Quit button. ]
echo [ 退出：用完后关闭本窗口即可退出（仅关浏览器不会退出），或点界面右下角的「退出」按钮。 ]
echo.
set MODELSCOPE_CACHE=%~dp0models
"%~dp0runtime\python.exe" "%~dp0app_main.py"
pause
