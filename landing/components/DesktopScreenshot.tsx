import Image from "next/image";

export type DesktopScreenshotVariant = "wifi" | "usb" | "pro";

const SCREENSHOTS: Record<DesktopScreenshotVariant, { src: string; alt: string }> = {
  wifi: {
    src: "/screenshots/desktop-wifi.png",
    alt: "Smart Cam App — режим Wi‑Fi, QR-код для подключения",
  },
  usb: {
    src: "/screenshots/desktop-cable.png",
    alt: "Smart Cam App — режим по кабелю, ожидание подключения",
  },
  pro: {
    src: "/screenshots/desktop-wifi.png",
    alt: "Smart Cam App — режим Pro",
  },
};

export function DesktopScreenshot({
  variant = "wifi",
  className = "",
  priority = false,
}: {
  variant?: DesktopScreenshotVariant;
  className?: string;
  priority?: boolean;
}) {
  const { src, alt } = SCREENSHOTS[variant];

  return (
    <Image
      src={src}
      alt={alt}
      width={1920}
      height={1080}
      priority={priority}
      className={`h-auto w-full ${className}`}
      sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 560px"
    />
  );
}
