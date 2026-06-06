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
          description="Телефон снимает, ПК принимает и отдаёт в Zoom, OBS или Discord. Pro добавляет трекинг, запись и NDI."
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
          <div className="grid items-end gap-8 lg:grid-cols-[auto_auto_auto] lg:justify-center lg:gap-10">
            <PhoneFrame label="Телефон" animate />

            <div className="hidden flex-col items-center gap-4 pb-16 lg:flex">
              <ConnectionFlow mode={mode} />
            </div>

            <div className="mx-auto w-full max-w-md lg:mx-0">
              <DesktopScreenshot variant={mode} />
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
    mode === "usb" ? "adb reverse" : mode === "wifi" ? "WebRTC" : "WebRTC + CV";

  return (
    <>
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
        <span className="text-xs text-white/60">~30 ms задержка</span>
      )}
    </>
  );
}
