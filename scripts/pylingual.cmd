@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "PYLINGUAL_HOME=%ROOT%"
if not exist "%ROOT%\vendor\pylingual\pylingual\__init__.py" (
  >&2 echo [pylingual] Upstream submodules are not initialized.
  >&2 echo [pylingual] Run: git submodule update --init --recursive
  exit /b 1
)
set "PYTHONHOME=%ROOT%\runtime\python-3.15.1"
set "PYTHONPATH=%ROOT%\src;%ROOT%\vendor\pylingual"
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "HF_HOME=%ROOT%\models\hf-cache"
set "HF_HUB_CACHE=%ROOT%\models\hf-cache\hub"
set "HF_HUB_DISABLE_SYMLINKS=1"
set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
set "TMP=%ROOT%\workspace\tmp"
set "TEMP=%TMP%"
if not exist "%HF_HOME%" mkdir "%HF_HOME%"
if not exist "%TMP%" mkdir "%TMP%"
set "PATH=%ROOT%\runtime\python-3.15.1;%ROOT%\runtime\python-3.15.1\Scripts;%ROOT%\runtime\python-3.15.1\Lib\site-packages\torch\lib;%PATH%"
"%ROOT%\runtime\python-3.15.1\python.exe" -m pylingual_portable.cli %*
exit /b %ERRORLEVEL%
