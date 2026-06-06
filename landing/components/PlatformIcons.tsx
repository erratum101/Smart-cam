import type { DownloadPlatform } from "@/lib/downloads";

export function PlatformIcon({
  platform,
  className = "h-5 w-5",
}: {
  platform: DownloadPlatform;
  className?: string;
}) {
  switch (platform) {
    case "windows":
      return <WindowsIcon className={className} />;
    case "android":
      return <AndroidIcon className={className} />;
  }
}

function WindowsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M3 5.5L10.5 4.6V11.5H3V5.5ZM11.5 4.4L21 3V11.5H11.5V4.4ZM3 12.5H10.5V19.4L3 18.5V12.5ZM11.5 12.5H21V21L11.5 19.6V12.5Z" />
    </svg>
  );
}

function AndroidIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M6.5 7.5c0-2.2 1.8-4 4-4s4 1.8 4 4h-8Zm-2 1h12a2 2 0 0 1 2 2v5.5a2 2 0 0 1-2 2h-1.1l.9 1.6a.75.75 0 1 1-1.3.75L14.8 18H9.2l-.9 1.6a.75.75 0 1 1-1.3-.75l.9-1.6H4.5a2 2 0 0 1-2-2V10.5a2 2 0 0 1 2-2Zm1.5 3.25a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8 0a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Z" />
    </svg>
  );
}
