import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/downloads/smart-cam-windows.exe",
        headers: [
          {
            key: "Content-Disposition",
            value: 'attachment; filename="Smart-Cam-App.exe"',
          },
          {
            key: "Content-Type",
            value: "application/octet-stream",
          },
        ],
      },
      {
        source: "/downloads/smart-cam-android.apk",
        headers: [
          {
            key: "Content-Disposition",
            value: 'attachment; filename="Smart-Cam-App.apk"',
          },
          {
            key: "Content-Type",
            value: "application/vnd.android.package-archive",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
