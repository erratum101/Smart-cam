import {
  PRODUCTION_DOWNLOAD_URLS,
  RELEASE_ASSETS,
} from "./release";

export type DownloadTier = "free" | "pro";
export type DownloadPlatform = "windows" | "android";

const LOCAL_PATHS: Record<DownloadPlatform, string> = {
  windows: "/downloads/smart-cam-windows.exe",
  android: "/downloads/smart-cam-android.apk",
};

function isLocalDev(): boolean {
  return process.env.NODE_ENV === "development";
}

function defaultUrl(platform: DownloadPlatform): string {
  return isLocalDev()
    ? LOCAL_PATHS[platform]
    : PRODUCTION_DOWNLOAD_URLS[platform];
}

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
  return trimmed || defaultUrl(platform);
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

export { RELEASE_ASSETS };
