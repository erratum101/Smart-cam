"use client";

import { useEffect, useState } from "react";
import { trackEvent } from "@/lib/analytics";
import { DesktopScreenshot } from "./DesktopScreenshot";
import { SectionHeader } from "./SectionHeader";

type DemoMode = "wifi" | "usb" | "pro";

const MODES: { id: DemoMode; label: string; desc: string }[] = [
  { id: "wifi", label: "Wi‑Fi", desc: "WebRTC 720p30 · низкая задержка" },
  { id: "usb", label: "USB", desc: "Кабель · стабильный TCP-поток" },
  { id: "pro", label: "Pro", desc: "Трекинг + запись + NDI" },
];

export function ProductDemo() {
  const [mode, setMode] = useState<DemoMode>("wifi");
  const [recording, setRecording] = useState(false);
  const [faceTrack, setFaceTrack] = useState(true);

  useEffect(() => {
    if (mode === "pro") setFaceTrack(true);
  }, [mode]);

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
                  : "border border-white/30 bg-white/10 text-white/80 hover:bg-white/20"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        <div className="glass-strong rounded-[2rem] p-6 sm:p-10">
          <div className="grid items-center gap-10 lg:grid-cols-[1fr_auto_1fr]">
            <PhoneMockup
              mode={mode}
              faceTrack={faceTrack}
              recording={recording}
              onToggleFace={() => setFaceTrack((v) => !v)}
              onToggleRec={() => setRecording((v) => !v)}
            />

            <div className="hidden flex-col items-center gap-4 lg:flex">
              <ConnectionFlow mode={mode} recording={recording} />
            </div>

            <div className="mx-auto w-full max-w-md">
              <DesktopScreenshot />
              <p className="mt-3 text-center text-sm font-medium text-white/60">
                Компьютер
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

function PhoneMockup({
  mode,
  faceTrack,
  recording,
  onToggleFace,
  onToggleRec,
}: {
  mode: DemoMode;
  faceTrack: boolean;
  recording: boolean;
  onToggleFace: () => void;
  onToggleRec: () => void;
}) {
  return (
    <div className="mx-auto w-full max-w-[220px] animate-float">
      <div className="rounded-[2.2rem] border-4 border-white/30 bg-white/10 p-2 shadow-2xl">
        <div className="relative aspect-[9/18] overflow-hidden rounded-[1.8rem] bg-brand-dark">
          <div className="absolute inset-x-3 top-3 flex justify-between text-[9px] text-white/70">
            <span>Smart Cam</span>
            <span className="rounded-full bg-green-400/25 px-2 text-green-200">LIVE</span>
          </div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-16 w-16 rounded-full bg-white/10 ring-2 ring-white/25" />
          </div>
          {mode === "pro" && faceTrack && (
            <div className="absolute left-[20%] top-[26%] h-[46%] w-[60%] rounded-xl border-2 border-white/80 shadow-[0_0_16px_rgba(255,255,255,0.4)]" />
          )}
          {mode === "pro" && (
            <div className="absolute inset-x-2 bottom-2 flex justify-center gap-1.5">
              <button
                type="button"
                onClick={onToggleFace}
                className={`rounded-md px-2 py-0.5 text-[8px] font-medium ${faceTrack ? "bg-white text-brand" : "bg-white/15 text-white"}`}
              >
                Face
              </button>
              <button
                type="button"
                onClick={onToggleRec}
                className={`rounded-md px-2 py-0.5 text-[8px] font-medium ${recording ? "bg-red-500 text-white" : "bg-white/15 text-white"}`}
              >
                REC
              </button>
            </div>
          )}
          <p className="absolute bottom-10 inset-x-0 text-center text-[8px] text-white/50">
            {MODES.find((x) => x.id === mode)?.desc}
          </p>
        </div>
      </div>
      <p className="mt-3 text-center text-sm font-medium text-white/60">Телефон</p>
    </div>
  );
}

function ConnectionFlow({
  mode,
  recording,
}: {
  mode: DemoMode;
  recording: boolean;
}) {
  const label =
    mode === "usb" ? "adb reverse" : mode === "wifi" ? "WebRTC" : "WebRTC + CV";

  return (
    <>
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full bg-white animate-pulse" />
        <span className="h-px w-12 bg-gradient-to-r from-white/60 to-transparent" />
        <span className="rounded-full border border-white/30 bg-white/10 px-3 py-1 text-xs text-white/80">
          {label}
        </span>
        <span className="h-px w-12 bg-gradient-to-l from-white/60 to-transparent" />
        <span className="h-2.5 w-2.5 rounded-full bg-white animate-pulse" />
      </div>
      {mode === "wifi" && (
        <span className="text-xs text-white/60">~30 ms задержка</span>
      )}
      {mode === "pro" && recording && (
        <span className="rounded-full bg-red-500/30 px-3 py-1 text-xs text-red-100">
          ● Запись 00:42
        </span>
      )}
    </>
  );
}
