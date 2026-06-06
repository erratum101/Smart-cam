"use client";

import { trackEvent } from "@/lib/analytics";

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-28 pb-16 sm:pt-36 sm:pb-24">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-20%,rgba(0,46,232,0.35),transparent)]" />
      <div className="pointer-events-none absolute inset-0 bg-grid-pattern bg-[length:48px_48px] opacity-40" />

      <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand/30 bg-brand/10 px-4 py-1.5 text-xs font-medium text-brand-glow">
            <span className="h-1.5 w-1.5 rounded-full bg-brand animate-pulse" />
            Телефон → ПК → Zoom / OBS
          </p>
          <h1 className="font-display text-4xl font-bold leading-[1.1] tracking-tight sm:text-6xl">
            <span className="text-gradient">Профессиональная</span>
            <br />
            <span className="text-white">веб-камера из смартфона</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-white/60">
            Smart Cam передаёт видео с телефона на компьютер как виртуальную
            камеру. Wi‑Fi без задержек или USB-кабель. В Pro — трекинг лица и
            тела, запись сессий и NDI.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a
              href="#pricing"
              onClick={() => trackEvent("cta_download_free")}
              className="w-full rounded-full bg-brand px-8 py-3.5 text-center text-sm font-semibold text-white brand-glow transition hover:bg-brand-dark sm:w-auto"
            >
              Скачать бесплатно
            </a>
            <a
              href="#demo"
              onClick={() => trackEvent("section_demo")}
              className="w-full rounded-full border border-white/15 px-8 py-3.5 text-center text-sm font-semibold text-white/90 transition hover:border-white/30 hover:bg-white/5 sm:w-auto"
            >
              Смотреть демо
            </a>
          </div>
          <div className="mt-12 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-xs text-white/40">
            <span>Windows & macOS</span>
            <span>Android & iOS</span>
            <span>WebRTC 720p30</span>
            <span>Без облака</span>
          </div>
        </div>
      </div>
    </section>
  );
}
