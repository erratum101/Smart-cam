"use client";

import { trackEvent } from "@/lib/analytics";
import {
  DOWNLOAD_URLS,
  PLATFORM_LABELS,
  type DownloadPlatform,
  type DownloadTier,
} from "@/lib/downloads";

type Variant = "hero-free" | "hero-pro" | "card-free" | "card-pro";

const PLATFORMS: DownloadPlatform[] = ["windows", "android"];

export function DownloadButtons({
  tier,
  variant,
  onExtraTrack,
}: {
  tier: DownloadTier;
  variant: Variant;
  onExtraTrack?: () => void;
}) {
  const isPro = tier === "pro";
  const prefix = isPro ? "Купить" : "Скачать";

  return (
    <div className="grid grid-cols-2 gap-2.5 sm:gap-3">
      {PLATFORMS.map((platform) => (
        <a
          key={platform}
          href={DOWNLOAD_URLS[tier][platform]}
          onClick={() => {
            trackEvent(isPro ? "cta_download_pro" : "cta_download_free", {
              platform,
            });
            onExtraTrack?.();
          }}
          className={buttonClass(variant)}
        >
          <span className="block text-[10px] font-medium uppercase tracking-wide opacity-75">
            {prefix}
          </span>
          <span className="block text-sm font-bold">{PLATFORM_LABELS[platform]}</span>
        </a>
      ))}
    </div>
  );
}

function buttonClass(variant: Variant): string {
  const base =
    "rounded-2xl px-3 py-2.5 text-center transition active:scale-[0.98]";

  switch (variant) {
    case "hero-free":
      return `${base} bg-white text-brand shadow-md hover:bg-white/95`;
    case "hero-pro":
      return `${base} bg-white/15 text-white backdrop-blur-sm hover:bg-white/25`;
    case "card-free":
      return `${base} bg-white/10 text-white backdrop-blur-sm hover:bg-white/20`;
    case "card-pro":
      return `${base} bg-brand text-white shadow-md hover:bg-brand-mid`;
    default:
      return base;
  }
}
