import Image from "next/image";

export type DeviceMockupKind = "phone" | "desktop-wifi" | "desktop-cable";

const MOCKUPS: Record<
  DeviceMockupKind,
  { src: string; alt: string; width: number; height: number }
> = {
  phone: {
    src: "/screenshots/phone.png",
    alt: "Smart Cam на iPhone — экран подключения",
    width: 900,
    height: 1840,
  },
  "desktop-wifi": {
    src: "/screenshots/wifi.png",
    alt: "Smart Cam на MacBook — режим Wi‑Fi",
    width: 3233,
    height: 3000,
  },
  "desktop-cable": {
    src: "/screenshots/cable.png",
    alt: "Smart Cam на MacBook — режим по кабелю",
    width: 3233,
    height: 3000,
  },
};

export function DeviceMockup({
  kind,
  className = "",
  priority = false,
  shadow = true,
  sizes,
}: {
  kind: DeviceMockupKind;
  className?: string;
  priority?: boolean;
  shadow?: boolean;
  sizes?: string;
}) {
  const { src, alt, width, height } = MOCKUPS[kind];
  const defaultSizes =
    kind === "phone"
      ? "(max-width: 640px) 38vw, 220px"
      : "(max-width: 768px) 90vw, (max-width: 1200px) 50vw, 560px";

  return (
    <Image
      src={src}
      alt={alt}
      width={width}
      height={height}
      priority={priority}
      className={`h-auto w-full ${shadow ? "device-shadow" : ""} ${className}`}
      sizes={sizes ?? defaultSizes}
    />
  );
}
