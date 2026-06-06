import Image from "next/image";

const DESKTOP_SCREENSHOT = "/screenshots/desktop-app.png";

export function DesktopScreenshot({
  className = "",
  priority = false,
}: {
  className?: string;
  priority?: boolean;
}) {
  return (
    <div
      className={`overflow-hidden rounded-2xl border border-white/25 shadow-[0_16px_48px_rgba(0,0,0,0.25)] ring-1 ring-white/20 ${className}`}
    >
      <Image
        src={DESKTOP_SCREENSHOT}
        alt="Smart Cam App на компьютере — экран подключения"
        width={1920}
        height={1080}
        priority={priority}
        className="h-auto w-full"
        sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 560px"
      />
    </div>
  );
}
