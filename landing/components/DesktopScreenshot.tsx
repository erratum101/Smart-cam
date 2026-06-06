import { DeviceMockup } from "./DeviceMockup";

export type DesktopScreenshotVariant = "wifi" | "usb" | "pro";

export function DesktopScreenshot({
  variant = "wifi",
  className = "",
  priority = false,
}: {
  variant?: DesktopScreenshotVariant;
  className?: string;
  priority?: boolean;
}) {
  const kind =
    variant === "usb" ? "desktop-cable" : "desktop-wifi";

  return (
    <DeviceMockup
      kind={kind}
      className={className}
      priority={priority}
      shadow
    />
  );
}
