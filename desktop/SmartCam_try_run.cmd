@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "EXE=%~dp0build-nuitka\SmartCam.exe"

echo.
echo === Smart Cam: пробный запуск ===
echo EXE: %EXE%
echo.

if not exist "%EXE%" (
  echo ОШИБКА: файл не найден. Соберите проект:
  echo   cd /d "%~dp0"
  echo   powershell -ExecutionPolicy Bypass -File build_nuitka_windows.ps1
  echo.
  pause
  exit /b 1
)

echo Файл найден, размер:
dir "%EXE%"
echo.

set SMART_CAM_DEBUG_POPUP=1
echo Запуск с SMART_CAM_DEBUG_POPUP=1 ...
echo После закрытия программы смотрите код выхода ниже.
echo Рядом с exe: SmartCam_boot.log, SmartCam_python_reached_popup.txt
echo.

"%EXE%"
set RC=%ERRORLEVEL%
echo.
echo Код выхода: %RC%
if exist "%~dp0build-nuitka\SmartCam_boot.log" (
  echo.
  echo --- SmartCam_boot.log ---
  type "%~dp0build-nuitka\SmartCam_boot.log"
)
if exist "%~dp0build-nuitka\SmartCam_python_reached_popup.txt" (
  echo.
  echo --- маркер Python ---
  type "%~dp0build-nuitka\SmartCam_python_reached_popup.txt"
)
echo.
pause
exit /b %RC%
