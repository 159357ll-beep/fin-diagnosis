@echo off
cd /d "%~dp0"
if exist "%~dp0.tools\python\python.exe" (
  set "PY=%~dp0.tools\python\python.exe"
) else (
  set "PY=C:\Users\fcr20\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
  set "PYTHONPATH=%~dp0.deps"
)
echo Starting Midea annual report analysis site...
echo Open: http://127.0.0.1:8502
"%PY%" -m streamlit run midea_app.py --global.developmentMode false --server.port 8502
pause
