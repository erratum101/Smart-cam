export type DownloadTier = "free" | "pro";
export type DownloadPlatform = "windows" | "android";

export const DOWNLOAD_URLS: Record<
  DownloadTier,
  Record<DownloadPlatform, string>
> = {
  free: {
    windows: process.env.NEXT_PUBLIC_DOWNLOAD_FREE_WINDOWS ?? "#",
    android: process.env.NEXT_PUBLIC_DOWNLOAD_FREE_ANDROID ?? "#",
  },
  pro: {
    windows: process.env.NEXT_PUBLIC_DOWNLOAD_PRO_WINDOWS ?? "#",
    android: process.env.NEXT_PUBLIC_DOWNLOAD_PRO_ANDROID ?? "#",
  },
};

export const PLATFORM_LABELS: Record<DownloadPlatform, string> = {
  windows: "Windows",
  android: "Android",
};
