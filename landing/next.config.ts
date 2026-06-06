import type { NextConfig } from "next";
import {
  PRODUCTION_DOWNLOAD_URLS,
  RELEASE_ASSETS,
} from "./lib/release";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: __dirname,
  async headers() {
    if (process.env.NODE_ENV !== "development") {
      return [];
    }

    return [
      {
        source: "/downloads/smart-cam-windows.exe",
        headers: [
          {
            key: "Content-Disposition",
            value: `attachment; filename="${RELEASE_ASSETS.windows}"`,
          },
          { key: "Content-Type", value: "application/octet-stream" },
        ],
      },
      {
        source: "/downloads/smart-cam-android.apk",
        headers: [
          {
            key: "Content-Disposition",
            value: `attachment; filename="${RELEASE_ASSETS.android}"`,
          },
          {
            key: "Content-Type",
            value: "application/vnd.android.package-archive",
          },
        ],
      },
    ];
  },
  async redirects() {
    if (process.env.NODE_ENV === "development") {
      return [];
    }

    return [
      {
        source: "/downloads/smart-cam-windows.exe",
        destination: PRODUCTION_DOWNLOAD_URLS.windows,
        permanent: false,
      },
      {
        source: "/downloads/smart-cam-android.apk",
        destination: PRODUCTION_DOWNLOAD_URLS.android,
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
