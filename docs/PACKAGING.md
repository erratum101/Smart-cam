# Сборка и упаковка

## Десктоп (Python)

### Зависимости

См. [desktop/README.md](../desktop/README.md) — виртуальная камера на Windows/macOS требует настройки бэкенда **pyvirtualcam** (Unity Capture / OBS и т.д.).

### Запуск из исходников

```bash
cd desktop
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Windows: один `SmartCam.exe`

Иконка: **`desktop/app_icon.png`** (или **`desktop/icon.png`** — скрипт подставит как `app_icon.png`), плюс **`desktop/app_icon.ico`** из `python make_icon.py`.

Из каталога `desktop/` в PowerShell:

```powershell
.\build_windows.ps1
```

Результат: **`desktop/Smart Cam App/dist/Smart Cam App.exe`**. PyInstaller ставится скриптом через pip.

**Nuitka (Windows):** `.\build_nuitka_windows.ps1` — **`desktop/Smart Cam App/build-nuitka/Smart Cam App.exe`**, нужен MSVC (`cl.exe`).

Сборка объёмная из‑за Qt/PySide6; на macOS тот же подход возможен, но проще запускать из исходников или собрать свой `.app` с аналогичными флагами PyInstaller.

### PyInstaller вручную (кратко)

```bash
cd desktop
pip install pyinstaller
python make_icon.py
pyinstaller --noconfirm --onefile --windowed --name "Smart Cam App" --icon app_icon.ico --paths . --distpath "Smart Cam App/dist" --workpath "Smart Cam App/build" --collect-all PySide6 --add-data "app_icon.png;." main.py
```

(Разделитель `--add-data` на Windows: `исходник;папка_внутри_бандла`.)

## Мобильное приложение (Flutter)

Каталог: [mobile/](../mobile/).

### Иконка на телефоне

Исходник: **`../icon.png`** относительно `mobile/` (корень проекта Smart cam). После замены пересоберите иконки лаунчера:

```bash
cd mobile
flutter pub get
dart run flutter_launcher_icons
```

### Подготовка

```bash
cd mobile
flutter pub get
```

### Android (APK / App Bundle)

```bash
flutter build apk --release
# или
flutter build appbundle --release
```

Артефакты: `build/app/outputs/flutter-apk/app-release.apk` или `build/app/outputs/bundle/release/app-release.aab`.

Нужны настроенный Android SDK и ключ подписи для публикации в Google Play (см. [документацию Flutter](https://docs.flutter.dev/deployment/android)).

### iOS

Требуется macOS с Xcode и учётная запись Apple Developer для установки на устройство и для App Store.

```bash
cd mobile
flutter build ios --release
```

Далее откройте `ios/Runner.xcworkspace` в Xcode, настройте signing, соберите архив и выгрузите в TestFlight/App Store.

### Версии SDK

В [mobile/pubspec.yaml](../mobile/pubspec.yaml) задан `environment.sdk`; при необходимости синхронизируйте с установленным Flutter (`flutter --version`).
