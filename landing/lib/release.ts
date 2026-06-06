export const GITHUB_REPO =
  process.env.NEXT_PUBLIC_GITHUB_REPO ?? "erratum101/Smart-cam";

export const RELEASE_TAG = process.env.NEXT_PUBLIC_RELEASE_TAG ?? "v1.0.0";

export const RELEASE_ASSETS = {
  windows: "Smart-Cam-App.exe",
  android: "Smart-Cam-App.apk",
} as const;

export function githubReleaseAssetUrl(assetName: string): string {
  return `https://github.com/${GITHUB_REPO}/releases/download/${RELEASE_TAG}/${encodeURIComponent(assetName)}`;
}

export const PRODUCTION_DOWNLOAD_URLS = {
  windows: githubReleaseAssetUrl(RELEASE_ASSETS.windows),
  android: githubReleaseAssetUrl(RELEASE_ASSETS.android),
} as const;
