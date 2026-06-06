@echo off
REM Запуск собранного exe из cmd — виден код выхода (соберите с build_nuitka_windows.ps1 -Debug для traceback).
cd /d "%~dp0"
set SMART_CAM_DEBUG_POPUP=
if "%1"=="debug" set SMART_CAM_DEBUG_POPUP=1

if exist "build-nuitka\SmartCam.exe" (
  echo Running build-nuitka\SmartCam.exe
  "build-nuitka\SmartCam.exe"
  echo Exit code: %ERRORLEVEL%
  goto :done
)
if exist "build-standalone\main.dist\SmartCam.exe" (
  echo Running build-standalone\main.dist\SmartCam.exe
  "build-standalone\main.dist\SmartCam.exe"
  echo Exit code: %ERRORLEVEL%
  goto :done
)
for /r "build-standalone" %%F in (SmartCam.exe) do if exist "%%F" (
  echo Running %%F
  "%%F"
  echo Exit code: %ERRORLEVEL%
  goto :done
)
echo Сначала выполните build_nuitka_windows.ps1 (ожидается SmartCam.exe).
:done
pause
