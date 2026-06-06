# Smart Cam — Landing Page

Маркетинговый лендинг для [Vercel](https://vercel.com). Демонстрация продукта, сравнение Free / Pro, премиум-функции (NDI, 1080p60).

## Локальный запуск

```bash
cd landing
npm install
npm run dev
```

Откройте [http://localhost:3000](http://localhost:3000).

## Деплой на Vercel

### Вариант 1 — через CLI

```bash
cd landing
npx vercel
```

### Вариант 2 — через GitHub

1. Залейте репозиторий на GitHub.
2. [vercel.com/new](https://vercel.com/new) → Import репозитория.
3. **Root Directory** → `landing`.
4. Deploy.

### Аналитика

- **Vercel Analytics** — включите в настройках проекта на Vercel (уже подключён `@vercel/analytics`).
- **Google Analytics 4** (опционально) — задайте `NEXT_PUBLIC_GA_ID=G-XXXXXXXX` в Environment Variables.

События кнопок: `cta_download_free`, `cta_download_pro`, `section_demo`, `section_pricing`, `nav_click`.

## Скачивание .exe / .apk

**Локально:** файлы из `public/downloads/` (после `npm run sync-downloads`).

**На Vercel:** `.exe` ~300 MB не деплоится (лимит). Файлы хранятся в **GitHub Releases**, кнопки и `/downloads/...` ведут туда.

### 1. Сборка

```powershell
cd desktop
.\build_windows.ps1

cd ..\mobile
flutter build apk --release
```

### 2. Публикация в GitHub Releases

```powershell
cd landing
$env:GITHUB_TOKEN = "ghp_..."   # repo scope: https://github.com/settings/tokens
npm run publish-release
```

Создаст релиз `v1.0.0` с `Smart-Cam-App.exe` и `Smart-Cam-App.apk`.

### 3. Деплой лендинга

Запушьте изменения или redeploy на Vercel. В production кнопки ведут на:

- `https://github.com/erratum101/Smart-cam/releases/download/v1.0.0/Smart-Cam-App.exe`
- `https://github.com/erratum101/Smart-cam/releases/download/v1.0.0/Smart-Cam-App.apk`

Новая версия: измените тег в `lib/release.ts` или задайте `NEXT_PUBLIC_RELEASE_TAG` на Vercel.

### Локальная разработка

```bash
cd landing
npm run sync-downloads
npm run dev
```

## Перед публикацией

1. Обновите цену Pro в `lib/content.ts`, если нужно.
3. Подставьте рабочий email в `components/Footer.tsx`.
4. При желании добавьте скриншоты в `public/` и вставьте в `ProductDemo.tsx`.

## Стек

- Next.js 15 + React 19
- Tailwind CSS
- TypeScript
- Vercel Analytics
