"use client";

import { DeviceMockup } from "./DeviceMockup";
import { DownloadButtons } from "./DownloadButtons";
import { trackEvent } from "@/lib/analytics";

const STATS = [
  { value: "720p30", label: "WebRTC по Wi‑Fi" },
  { value: "<30 ms", label: "Задержка" },
  { value: "0 ₽", label: "Базовая версия" },
];

export function Hero() {
  return (
    <section className="relative overflow-x-clip pt-32 pb-20 sm:pt-40 sm:pb-28">
      <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid items-center gap-14 lg:grid-cols-2 lg:gap-10">
          <div className="text-center lg:text-left">
            <p className="mb-5 inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-1.5 text-xs font-medium text-white/90 backdrop-blur-sm">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-300 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-green-400" />
              </span>
              Телефон → ПК → Zoom / OBS
            </p>
            <h1 className="font-display text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
              <span className="text-gradient">Веб-камера</span>
              <br />
              из вашего смартфона
            </h1>
            <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-white/80 lg:mx-0">
              Smart Cam передаёт видео на компьютер как виртуальную камеру.
              Подключение по Wi‑Fi или USB за секунды. Pro — NDI, 1080p60 и
              приоритетная поддержка.
            </p>
            <div className="mx-auto mt-9 max-w-md space-y-4 lg:mx-0">
              <DownloadButtons tier="free" variant="hero-free" />
              <a
                href="#demo"
                onClick={() => trackEvent("section_demo")}
                className="btn-secondary block w-full text-center"
              >
                Смотреть демо
              </a>
            </div>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
              {STATS.map((s) => (
                <div
                  key={s.label}
                  className="rounded-2xl bg-white/10 px-4 py-3 text-center backdrop-blur-sm"
                >
                  <p className="font-display text-lg font-bold">{s.value}</p>
                  <p className="text-[11px] text-white/60">{s.label}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="relative mx-auto w-full overflow-visible lg:max-w-none">
            <div className="relative min-h-[280px] sm:min-h-[360px] lg:min-h-[420px]">
              {/* Десктоп */}
              <div className="relative z-10 w-[108%] max-w-none -translate-x-[2%] sm:w-[112%] lg:w-[118%] lg:-translate-x-[4%] animate-float-delayed">
                <DeviceMockup
                  kind="desktop-wifi"
                  priority
                  className="!max-w-none"
                  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 720px, 820px"
                />
              </div>

              {/* iPhone справа, на переднем плане */}
              <div className="absolute right-[-10%] top-[6%] z-20 w-[34%] max-w-[210px] sm:right-[-6%] sm:top-[4%] sm:max-w-[230px] lg:right-[-12%] lg:max-w-[250px] animate-float">
                <DeviceMockup kind="phone" priority />
              </div>
            </div>
            <div className="absolute -bottom-2 left-0 z-30 hidden rounded-2xl bg-white px-4 py-3 shadow-xl sm:block animate-float-delayed">
              <p className="text-xs font-medium text-brand">Pro</p>
              <p className="text-lg font-bold text-brand">300 ₽</p>
              <p className="text-[10px] text-brand/60">один раз</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
