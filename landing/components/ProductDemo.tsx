"use client";

import { useEffect, useState } from "react";
import { trackEvent } from "@/lib/analytics";

type DemoMode = "wifi" | "usb" | "pro";

const MODES: { id: DemoMode; label: string; desc: string }[] = [
  {
    id: "wifi",
    label: "Wi‑Fi",
    desc: "WebRTC 720p30 · низкая задержка",
  },
  {
    id: "usb",
    label: "USB",
    desc: "Кабель · стабильный TCP-поток",
  },
  {
    id: "pro",
    label: "Pro",
    desc: "Трекинг + запись + NDI",
  },
];

export function ProductDemo() {
  const [mode, setMode] = useState<DemoMode>("wifi");
  const [recording, setRecording] = useState(false);
  const [faceTrack, setFaceTrack] = useState(true);

  useEffect(() => {
    if (mode === "pro") {
      setFaceTrack(true);
    }
  }, [mode]);

  return (
    <section id="demo" className="py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mb-12 text-center">
          <h2 className="font-display text-3xl font-bold sm:text-4xl">
            Как это работает
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-white/55">
            Телефон снимает, ПК принимает и отдаёт в Zoom, OBS или Discord как
            обычную веб-камеру. Pro добавляет интеллектуальный трекинг из
            SmartCam Stand.
          </p>
        </div>

        <div className="mb-6 flex flex-wrap justify-center gap-2">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => {
                setMode(m.id);
                trackEvent("section_demo", { mode: m.id });
              }}
              className={`rounded-full px-5 py-2 text-sm font-medium transition ${
                mode === m.id
                  ? "bg-brand text-white"
                  : "bg-white/5 text-white/60 hover:bg-white/10 hover:text-white"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        <div className="grid items-center gap-8 lg:grid-cols-[1fr_auto_1fr]">
          {/* Phone */}
          <div className="mx-auto w-full max-w-xs animate-float">
            <div className="glass rounded-[2.5rem] p-3 brand-glow">
              <div className="relative aspect-[9/19] overflow-hidden rounded-[2rem] bg-surface">
                <div className="absolute inset-0 bg-gradient-to-b from-brand/20 via-transparent to-black/60" />
                <div className="absolute inset-x-4 top-4 flex items-center justify-between text-[10px] text-white/70">
                  <span>Smart Cam</span>
                  <span className="rounded-full bg-green-500/20 px-2 py-0.5 text-green-400">
                    LIVE
                  </span>
                </div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="h-24 w-24 rounded-full bg-white/10 ring-2 ring-brand/50" />
                </div>
                {mode === "pro" && faceTrack && (
                  <>
                    <div className="absolute left-[22%] top-[28%] h-[44%] w-[56%] rounded-2xl border-2 border-brand shadow-[0_0_20px_rgba(0,46,232,0.6)]" />
                    <div className="absolute left-1/2 top-[48%] h-2 w-2 -translate-x-1/2 rounded-full bg-brand" />
                  </>
                )}
                {mode === "pro" && (
                  <div className="absolute inset-x-3 bottom-3 flex justify-center gap-2">
                    <button
                      type="button"
                      onClick={() => setFaceTrack((v) => !v)}
                      className={`rounded-lg px-2 py-1 text-[9px] ${faceTrack ? "bg-brand" : "bg-white/10"}`}
                    >
                      Face
                    </button>
                    <button
                      type="button"
                      onClick={() => setRecording((v) => !v)}
                      className={`rounded-lg px-2 py-1 text-[9px] ${recording ? "bg-red-600" : "bg-white/10"}`}
                    >
                      REC
                    </button>
                  </div>
                )}
                <p className="absolute bottom-14 inset-x-0 text-center text-[10px] text-white/50">
                  {MODES.find((x) => x.id === mode)?.desc}
                </p>
              </div>
            </div>
            <p className="mt-4 text-center text-sm text-white/40">Телефон</p>
          </div>

          {/* Connection flow */}
          <div className="hidden flex-col items-center gap-3 lg:flex">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-brand animate-pulse" />
              <span className="h-px w-16 bg-gradient-to-r from-brand to-brand/20" />
              <span className="text-xs text-white/40">
                {mode === "usb" ? "adb reverse" : mode === "wifi" ? "WebRTC" : "WebRTC + CV"}
              </span>
              <span className="h-px w-16 bg-gradient-to-l from-brand to-brand/20" />
              <span className="h-2 w-2 rounded-full bg-brand animate-pulse" />
            </div>
            {mode === "wifi" && (
              <span className="rounded-full bg-brand/15 px-3 py-1 text-xs text-brand-glow">
                ~30 ms задержка
              </span>
            )}
            {mode === "pro" && recording && (
              <span className="rounded-full bg-red-500/20 px-3 py-1 text-xs text-red-400">
                ● Запись 00:42
              </span>
            )}
          </div>

          {/* Desktop */}
          <div className="mx-auto w-full max-w-md">
            <div className="glass overflow-hidden rounded-2xl">
              <div className="flex items-center gap-2 border-b border-white/10 bg-surface-elevated px-4 py-3">
                <div className="flex gap-1.5">
                  <span className="h-3 w-3 rounded-full bg-white/20" />
                  <span className="h-3 w-3 rounded-full bg-white/20" />
                  <span className="h-3 w-3 rounded-full bg-white/20" />
                </div>
                <span className="text-xs text-white/50">Smart Cam App</span>
              </div>
              <div className="relative aspect-video bg-surface">
                <div className="absolute inset-0 bg-gradient-to-br from-brand/10 to-transparent" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <div className="mx-auto mb-2 h-16 w-16 rounded-full bg-white/5 ring-1 ring-white/10" />
                    <p className="text-xs text-white/40">Превью 1280×720</p>
                  </div>
                </div>
                {mode === "pro" && faceTrack && (
                  <div className="absolute left-[30%] top-[18%] h-[64%] w-[40%] rounded-xl border border-brand/80" />
                )}
                <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between">
                  <span className="rounded-md bg-black/50 px-2 py-1 text-[10px] text-white/70">
                    Virtual Cam → OBS
                  </span>
                  {mode === "pro" && (
                    <span className="rounded-md bg-brand/30 px-2 py-1 text-[10px] text-brand-glow">
                      NDI
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2 border-t border-white/10 p-3">
                <span className="rounded-lg bg-brand/20 px-3 py-1.5 text-xs text-brand-glow">
                  {mode === "usb" ? "По кабелю" : "Wi‑Fi"}
                </span>
                <span className="rounded-lg bg-white/5 px-3 py-1.5 text-xs text-white/50">
                  QR готов
                </span>
              </div>
            </div>
            <p className="mt-4 text-center text-sm text-white/40">Компьютер</p>
          </div>
        </div>

        <div className="mt-14 grid gap-4 sm:grid-cols-3">
          {[
            {
              step: "1",
              title: "Установите на ПК и телефон",
              text: "Скачайте Smart Cam App и мобильное приложение.",
            },
            {
              step: "2",
              title: "Подключитесь",
              text: "Отсканируйте QR или выберите ПК в списке. Wi‑Fi или USB.",
            },
            {
              step: "3",
              title: "Выберите Smart Cam в Zoom",
              text: "Виртуальная камера появится как обычное устройство.",
            },
          ].map((item) => (
            <div key={item.step} className="glass rounded-2xl p-5">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-brand/20 text-sm font-bold text-brand-glow">
                {item.step}
              </span>
              <h3 className="mt-3 font-semibold">{item.title}</h3>
              <p className="mt-2 text-sm text-white/50">{item.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
