export function Logo({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/20 ring-1 ring-white/30">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/icon.svg"
          alt=""
          width={24}
          height={24}
          className="brightness-0 invert"
        />
      </div>
      <span className="font-display text-xl font-bold tracking-tight text-white">
        Smart Cam
      </span>
    </div>
  );
}
