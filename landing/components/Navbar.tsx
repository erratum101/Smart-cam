"use client";

import { Logo } from "./Logo";
import { trackEvent } from "@/lib/analytics";

const LINKS = [
  { href: "#demo", label: "Демо" },
  { href: "#features", label: "Возможности" },
  { href: "#compare", label: "Сравнение" },
  { href: "#pricing", label: "Тарифы" },
];

export function Navbar() {
  return (
    <header className="fixed inset-x-0 top-0 z-50">
      <div className="mx-auto max-w-6xl px-4 pt-4 sm:px-6">
        <div className="flex h-14 items-center justify-between rounded-2xl border border-white/25 bg-white/10 px-5 shadow-[0_4px_24px_rgba(0,0,0,0.1)] backdrop-blur-2xl">
          <a href="#" aria-label="Smart Cam — на главную">
            <Logo />
          </a>
          <nav className="hidden items-center gap-1 md:flex">
            {LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => trackEvent("nav_click", { target: link.href })}
                className="rounded-xl px-4 py-2 text-sm text-white/75 transition hover:bg-white/10 hover:text-white"
              >
                {link.label}
              </a>
            ))}
          </nav>
          <a
            href="#pricing"
            onClick={() => trackEvent("cta_download_free")}
            className="rounded-full bg-white px-5 py-2 text-sm font-semibold text-brand shadow-md transition hover:bg-white/90"
          >
            Скачать
          </a>
        </div>
      </div>
    </header>
  );
}
