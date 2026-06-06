"use client";

import { useState } from "react";
import { trackEvent } from "@/lib/analytics";
import { DesktopScreenshot } from "./DesktopScreenshot";
import { PhoneFrame } from "./PhoneFrame";
import { SectionHeader } from "./SectionHeader";

type DemoMode = "wifi" | "usb" | "pro";

const MODES: { id: DemoMode; label: string }[] = [
  { id: "wifi", label: "Wi‑Fi" },
  { id: "usb", label: "USB" },
  { id: "pro", label: "Pro" },
];

export function ProductDemo() {
  const [mode, setMode] = useState<DemoMode>("wifi");

  return (
    <section id="demo" className="py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader
          label="Демонстрация"
          title="Как это работает"
          description="Телефон снимает, ПК принимает и отдаёт в Zoom, OBS или Discord. Pro добавляет NDI и 1080p60."
        />

        <div className="mb-8 flex flex-wrap justify-center gap-2">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => {
                setMode(m.id);
                trackEvent("section_demo", { mode: m.id });
              }}
              className={`rounded-full px-6 py-2.5 text-sm font-semibold transition ${
                mode === m.id
                  ? "bg-white text-brand shadow-lg"
                  : "bg-white/10 text-white/80 hover:bg-white/20"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        <div className="glass-strong rounded-[2rem] p-6 sm:p-10">
          <div className="flex flex-col items-center gap-8 lg:flex-row lg:items-center lg:justify-start lg:gap-6 xl:gap-10">
            <div className="w-full max-w-[200px] shrink-0 sm:max-w-[220px]">
              <PhoneFrame label="Телефон" animate />
            </div>

            <div className="flex shrink-0 items-center justify-center">
              <ConnectionFlow mode={mode} />
            </div>

            <div className="w-full max-w-xl sm:max-w-2xl lg:max-w-[520px] lg:-translate-x-4 xl:max-w-[580px] xl:-translate-x-8">
              <div className="animate-float-delayed">
                <DesktopScreenshot
                  variant={mode}
                  sizes="(max-width: 768px) 90vw, (max-width: 1200px) 520px, 580px"
                />
              </div>
              <p className="mt-3 text-center text-sm font-medium text-white/60">
                Компьютер ·{" "}
                {mode === "usb" ? "по кабелю" : mode === "wifi" ? "Wi‑Fi" : "Pro"}
              </p>
            </div>
          </div>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          {[
            { step: "01", title: "Установите", text: "Smart Cam на ПК и телефон." },
            { step: "02", title: "Подключитесь", text: "QR-код, Wi‑Fi или USB-кабель." },
            { step: "03", title: "Готово", text: "Выберите Smart Cam в Zoom или OBS." },
          ].map((item) => (
            <div key={item.step} className="glass-card p-6 transition hover:bg-white/[0.16]">
              <span className="font-display text-3xl font-bold text-white/30">
                {item.step}
              </span>
              <h3 className="mt-2 text-lg font-semibold">{item.title}</h3>
              <p className="mt-1.5 text-sm text-white/70">{item.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ConnectionFlow({ mode }: { mode: DemoMode }) {
  const label =
    mode === "usb" ? "adb reverse" : mode === "wifi" ? "WebRTC" : "NDI";

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full bg-white animate-pulse" />
        <span className="h-px w-12 bg-gradient-to-r from-white/60 to-transparent" />
        <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-white/80 backdrop-blur-sm">
          {label}
        </span>
        <span className="h-px w-12 bg-gradient-to-l from-white/60 to-transparent" />
        <span className="h-2.5 w-2.5 rounded-full bg-white animate-pulse" />
      </div>
      {mode === "wifi" && (
        <p className="text-center text-xs leading-tight text-white/60">
          <span className="block">~30 ms</span>
          <span className="block">задержка</span>
        </p>
      )}
    </div>
  );
}
