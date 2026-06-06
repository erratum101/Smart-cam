export type DownloadTier = "free" | "pro";
export type DownloadPlatform = "windows" | "android";

const DEFAULT_PATHS: Record<DownloadPlatform, string> = {
  windows: "/api/download/windows",
  android: "/api/download/android",
};

export const DOWNLOAD_FILENAMES: Record<DownloadPlatform, string> = {
  windows: "Smart-Cam-App.exe",
  android: "Smart-Cam-App.apk",
};

function resolveUrl(tier: DownloadTier, platform: DownloadPlatform): string {
  const env =
    tier === "free"
      ? platform === "windows"
        ? process.env.NEXT_PUBLIC_DOWNLOAD_FREE_WINDOWS
        : process.env.NEXT_PUBLIC_DOWNLOAD_FREE_ANDROID
      : platform === "windows"
        ? process.env.NEXT_PUBLIC_DOWNLOAD_PRO_WINDOWS
        : process.env.NEXT_PUBLIC_DOWNLOAD_PRO_ANDROID;

  const trimmed = env?.trim();
  return trimmed || DEFAULT_PATHS[platform];
}

export const DOWNLOAD_URLS: Record<
  DownloadTier,
  Record<DownloadPlatform, string>
> = {
  free: {
    windows: resolveUrl("free", "windows"),
    android: resolveUrl("free", "android"),
  },
  pro: {
    windows: resolveUrl("pro", "windows"),
    android: resolveUrl("pro", "android"),
  },
};

export const PLATFORM_LABELS: Record<DownloadPlatform, string> = {
  windows: "Windows",
  android: "Android",
};
