import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import { SiteAnalytics } from "@/components/SiteAnalytics";
import "./globals.css";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space",
});

export const metadata: Metadata = {
  title: "Smart Cam — веб-камера из смартфона",
  description:
    "Превратите телефон в профессиональную веб-камеру для Zoom и OBS. Wi‑Fi, USB, виртуальная камера. Pro: NDI, 1080p60, без водяного знака.",
  openGraph: {
    title: "Smart Cam — веб-камера из смартфона",
    description:
      "Телефон → ПК → Zoom / OBS. Бесплатно. Pro с NDI и 1080p60.",
    type: "website",
  },
  icons: {
    icon: "/app-icon.png",
    apple: "/app-icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className={`${inter.variable} ${spaceGrotesk.variable}`}>
      <body className="font-sans antialiased">
        {children}
        <SiteAnalytics />
      </body>
    </html>
  );
}
