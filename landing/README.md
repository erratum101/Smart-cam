# Smart Cam — Landing Page

Маркетинговый лендинг для [Vercel](https://vercel.com). Демонстрация продукта, сравнение Free / Pro, премиум-функции (трекинг, запись, NDI).

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

## Перед публикацией

1. Замените `href="#"` в кнопках «Скачать» на реальные ссылки (Microsoft Store, Google Play, Gumroad и т.д.).
2. Обновите цену Pro в `lib/content.ts`, если нужно.
3. Подставьте рабочий email в `components/Footer.tsx`.
4. При желании добавьте скриншоты в `public/` и вставьте в `ProductDemo.tsx`.

## Стек

- Next.js 15 + React 19
- Tailwind CSS
- TypeScript
- Vercel Analytics
