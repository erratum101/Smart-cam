export function Logo({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand text-white">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/icon.svg" alt="" width={22} height={22} className="invert-0" />
      </div>
      <span className="font-display text-lg font-semibold tracking-tight">
        Smart Cam
      </span>
    </div>
  );
}
