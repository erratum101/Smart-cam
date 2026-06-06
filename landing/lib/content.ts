export const FREE_FEATURES = [
  "Телефон как веб-камера для Zoom, OBS, Teams",
  "Wi‑Fi: WebRTC 720p30 с низкой задержкой",
  "USB: стабильный поток по кабелю (TCP)",
  "Подключение по QR-коду за 10 секунд",
  "Виртуальная камера на Windows и macOS",
  "Автопоиск ПК в локальной сети (mDNS)",
  "Синхронный старт/стоп с телефона и ПК",
  "3 пресета качества потока",
] as const;

export const PRO_FEATURES = [
  {
    title: "Трекинг лица",
    description:
      "MediaPipe автоматически держит лицо в центре кадра — идеально для звонков и стримов без оператора.",
    badge: "Pro",
  },
  {
    title: "Трекинг тела",
    description:
      "Отслеживание позы для фитнеса, презентаций и динамичных трансляций. Плечи и центр тела в фокусе.",
    badge: "Pro",
  },
  {
    title: "Запись видео",
    description:
      "Одна кнопка — запись сессии в MP4/MKV с микрофоном (FFmpeg, H.264). Сохранение в выбранную папку.",
    badge: "Pro",
  },
  {
    title: "NDI-выход",
    description:
      "Прямой NDI-поток для vMix, Wirecast и профессиональных студий без лишних конвертеров.",
    badge: "Pro",
  },
  {
    title: "1080p60 и приоритет",
    description:
      "Полное разрешение 1920×1080@60, без водяного знака, приоритетная поддержка и ранний доступ.",
    badge: "Pro",
  },
] as const;

export const COMPARISON_ROWS = [
  { feature: "Виртуальная камера", free: true, pro: true },
  { feature: "Wi‑Fi WebRTC 720p30", free: true, pro: true },
  { feature: "USB по кабелю", free: true, pro: true },
  { feature: "QR + автопоиск ПК", free: true, pro: true },
  { feature: "Качество потока", free: "720p30", pro: "1080p60" },
  { feature: "Трекинг лица", free: false, pro: true },
  { feature: "Трекинг тела / позы", free: false, pro: true },
  { feature: "Оверлей трекинга", free: false, pro: true },
  { feature: "Запись видео + микрофон", free: false, pro: true },
  { feature: "NDI-выход", free: false, pro: true },
  { feature: "Водяной знак", free: "Да", pro: "Нет" },
  { feature: "Поддержка", free: "Сообщество", pro: "Приоритет" },
] as const;

export const PLANS = [
  {
    id: "free",
    name: "Free",
    price: "0 ₽",
    period: "навсегда",
    description: "Всё необходимое, чтобы превратить телефон в веб-камеру.",
    highlighted: false,
    features: [
      "Виртуальная камера",
      "720p30 по Wi‑Fi",
      "USB-кабель",
      "QR-подключение",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "300 ₽",
    period: "один раз",
    description: "Трекинг, запись и профессиональный вывод — разовая покупка, без подписки.",
    highlighted: true,
    features: [
      "Всё из Free",
      "Трекинг лица и тела",
      "Запись MP4/MKV + мик",
      "NDI + 1080p60",
      "Без водяного знака",
    ],
  },
] as const;
