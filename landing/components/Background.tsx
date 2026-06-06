export function Background() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden page-bg">
      <div className="absolute inset-0 bg-dot-pattern bg-[length:28px_28px] opacity-60" />
      <div className="absolute -left-32 top-20 h-96 w-96 rounded-full bg-white/10 blur-3xl animate-shimmer" />
      <div className="absolute -right-24 top-1/3 h-80 w-80 rounded-full bg-brand-light/30 blur-3xl animate-float" />
      <div className="absolute bottom-0 left-1/2 h-64 w-[600px] -translate-x-1/2 rounded-full bg-brand-dark/50 blur-3xl" />
    </div>
  );
}
