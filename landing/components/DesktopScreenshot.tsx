import { DeviceMockup } from "./DeviceMockup";

export type DesktopScreenshotVariant = "wifi" | "usb" | "pro";

export function DesktopScreenshot({
  variant = "wifi",
  className = "",
  priority = false,
  sizes,
}: {
  variant?: DesktopScreenshotVariant;
  className?: string;
  priority?: boolean;
  sizes?: string;
}) {
  const kind =
    variant === "usb" ? "desktop-cable" : "desktop-wifi";

  return (
    <DeviceMockup
      kind={kind}
      className={className}
      priority={priority}
      sizes={sizes}
      shadow
    />
  );
}
