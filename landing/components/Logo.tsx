import Image from "next/image";

const APP_ICON = "/app-icon.png";

export function Logo({ className = "", size = 40 }: { className?: string; size?: number }) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <Image
        src={APP_ICON}
        alt=""
        width={size}
        height={size}
        className="rounded-[22%] shadow-sm"
        priority
      />
      <span className="font-display text-xl font-bold tracking-tight text-white">
        Smart Cam
      </span>
    </div>
  );
}
