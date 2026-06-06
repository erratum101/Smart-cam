"use client";

import { trackEvent } from "@/lib/analytics";
import {
  DOWNLOAD_URLS,
  PLATFORM_LABELS,
  type DownloadPlatform,
  type DownloadTier,
} from "@/lib/downloads";
import { PlatformIcon } from "./PlatformIcons";

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
          <PlatformIcon
            platform={platform}
            className="h-5 w-5 shrink-0 sm:h-6 sm:w-6"
          />
          <span className="min-w-0 text-left leading-tight">
            <span className="block text-[9px] font-medium uppercase tracking-wide opacity-75 sm:text-[10px]">
              {prefix}
            </span>
            <span className="block text-xs font-bold sm:text-sm">
              {PLATFORM_LABELS[platform]}
            </span>
            {platform === "android" ? (
              <span className="block text-[9px] font-medium opacity-60 sm:text-[10px]">
                APK
              </span>
            ) : null}
          </span>
        </a>
      ))}
    </div>
  );
}

function buttonClass(variant: Variant): string {
  const base =
    "flex items-center gap-2 rounded-2xl px-3 py-2.5 text-left transition active:scale-[0.98] sm:gap-2.5 sm:px-4";

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
