import Image from "next/image";

export type DeviceMockupKind = "phone" | "desktop-wifi" | "desktop-cable";

const MOCKUPS: Record<
  DeviceMockupKind,
  { src: string; alt: string; width: number; height: number }
> = {
  phone: {
    src: "/screenshots/phone-mockup.png",
    alt: "Smart Cam на iPhone — экран подключения",
    width: 900,
    height: 1800,
  },
  "desktop-wifi": {
    src: "/screenshots/desktop-wifi-mockup.png",
    alt: "Smart Cam на MacBook — режим Wi‑Fi",
    width: 2400,
    height: 1600,
  },
  "desktop-cable": {
    src: "/screenshots/desktop-cable-mockup.png",
    alt: "Smart Cam на MacBook — режим по кабелю",
    width: 2400,
    height: 1600,
  },
};

export function DeviceMockup({
  kind,
  className = "",
  priority = false,
  shadow = true,
}: {
  kind: DeviceMockupKind;
  className?: string;
  priority?: boolean;
  shadow?: boolean;
}) {
  const { src, alt, width, height } = MOCKUPS[kind];

  return (
    <Image
      src={src}
      alt={alt}
      width={width}
      height={height}
      priority={priority}
      className={`h-auto w-full ${shadow ? "device-shadow" : ""} ${className}`}
      sizes={
        kind === "phone"
          ? "(max-width: 640px) 38vw, 220px"
          : "(max-width: 768px) 90vw, (max-width: 1200px) 50vw, 560px"
      }
    />
  );
}
