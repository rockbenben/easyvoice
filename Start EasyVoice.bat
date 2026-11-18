@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PATH=%~dp0runtime\Library\bin;%PATH%"
rem First run: relocate the embedded runtime to this machine (once, ~1 min)
if not exist "runtime\.unpacked" (
  echo Initializing runtime, please wait...  -  首次启动，正在初始化运行环境，请稍候...
  "%~dp0runtime\Scripts\conda-unpack.exe"
  if errorlevel 1 (
    echo Runtime initialization failed. See the error above and try starting EasyVoice again.
    pause
    exit /b 1
  )
  echo ok> "runtime\.unpacked"
)
echo Starting EasyVoice, loading the model (~30s; first run may take longer)...  -  正在启动并加载模型（约 30 秒，首次启动或需下载模型会更久），请稍候...
echo.
echo [ Quit: close THIS window when done (closing the browser alone won't quit), or click the on-page Quit button. ]
echo [ 退出：用完后关闭本窗口即可退出（仅关浏览器不会退出），或点界面右下角的「退出」按钮。 ]
echo.
"%~dp0runtime\python.exe" -E -s "%~dp0app_main.py"
pause
