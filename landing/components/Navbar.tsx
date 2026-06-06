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
    <header className="fixed inset-x-0 top-0 z-50 border-b border-white/5 bg-[#0a0a0c]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <a href="#" aria-label="Smart Cam — на главную">
          <Logo />
        </a>
        <nav className="hidden items-center gap-8 md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => trackEvent("nav_click", { target: link.href })}
              className="text-sm text-white/60 transition hover:text-white"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <a
          href="#pricing"
          onClick={() => trackEvent("cta_download_free")}
          className="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-dark"
        >
          Скачать
        </a>
      </div>
    </header>
  );
}
