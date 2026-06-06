# Smart Cam — desktop (Windows + macOS)

Python 3.10+ app: принимает TCP-поток JPEG с телефона и выводит его в виртуальную веб-камеру через [pyvirtualcam](https://github.com/letmaik/pyvirtualcam).

## Иконка

- Положите **`app_icon.png`** в папку **`desktop/`** (рядом с `main.py`). Запасной вариант — **`desktop/icon.png`** (скрипт сборки при необходимости скопирует его в `app_icon.png`).
- **`app_icon.ico`** создаётся командой `python make_icon.py`.

## Сборка `Smart Cam App.exe` (Windows)

Из папки `desktop/` в PowerShell (предварительно `pip install -r requirements.txt` в вашем venv):

```powershell
.\build_windows.ps1
```

Готовый файл: **`Smart Cam App\dist\Smart Cam App.exe`**. Сборка тяжёлая из‑за `--collect-all PySide6` и может занять несколько минут.

### Сборка через Nuitka (альтернатива)

Нужен **компилятор C** под Windows (обычно MSVC из *Visual Studio Build Tools* с workload «Desktop development with C++» — тогда в среде доступен `cl.exe`). Nuitka сам подхватывает его.

```powershell
.\build_nuitka_windows.ps1
```

Результат: **`Smart Cam App\build-nuitka\Smart Cam App.exe`**. Первый прогон может занять **несколько минут**. Скрипт ставит Nuitka через pip.

Перед первым запуском на чистой машине всё равно нужны зависимости виртуальной камеры (Unity Capture / OBS и т.д.), см. ниже.

### Если `.exe` сразу закрывается и окна нет

1. Откройте журнал: **`%LOCALAPPDATA%\Smart Cam App\launch.log`** — видно, на каком шаге остановилось (`bootstrap`, `qt_env ok`, `import gui ok`, …).
2. При исключении смотрите **`%LOCALAPPDATA%\Smart Cam App\startup_error.log`**.
3. Запуск из **cmd** иногда показывает текст ошибки:  
   `"C:\path\to\Smart Cam App.exe"`
4. Пересоберите Nuitka после обновления (в скрипт добавлен явный набор Qt‑плагинов).

## Установка

```bash
cd desktop
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

Запуск:

```bash
python main.py
```

В окне показывается **QR-код** с JSON-подключением (`host`, `port`, `token`) для сканирования мобильным приложением.

## Виртуальная камера: зависимости ОС

### Windows

Рекомендуется бэкенд **Unity Capture** (см. раздел *Installation* в README pyvirtualcam): установите компонент, чтобы приложения видели виртуальную камеру без полного OBS.

Альтернатива: бэкенд **OBS** — установите OBS, один раз запустите виртуальную камеру по инструкции pyvirtualcam.

### macOS

Обычно требуется **OBS Studio 30+** и его виртуальная камера как бэкенд для pyvirtualcam. Следуйте [официальной документации pyvirtualcam для macOS](https://github.com/letmaik/pyvirtualcam) (подготовка виртуальной камеры OBS).

Собственное CMIO Camera Extension в этот проект не входит — без OBS/другого поддерживаемого бэкенда системная камера может быть недоступна.

## Протокол

Описан в [docs/PROTOCOL.md](../docs/PROTOCOL.md).

## Подключение телефона

См. [docs/CONNECTION.md](../docs/CONNECTION.md).
