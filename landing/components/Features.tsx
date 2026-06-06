import { FREE_FEATURES, PRO_FEATURES } from "@/lib/content";

export function Features() {
  return (
    <section id="features" className="border-t border-white/5 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mb-14 text-center">
          <h2 className="font-display text-3xl font-bold sm:text-4xl">
            Возможности
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-white/55">
            Бесплатная версия закрывает базовые сценарии. Pro объединяет Smart
            Cam с технологиями SmartCam Stand — трекинг, запись и студийный
            вывод.
          </p>
        </div>

        <div className="grid gap-10 lg:grid-cols-2">
          <div>
            <div className="mb-6 flex items-center gap-3">
              <h3 className="text-xl font-semibold">Free</h3>
              <span className="rounded-full bg-white/10 px-3 py-0.5 text-xs text-white/60">
                Базовый набор
              </span>
            </div>
            <ul className="space-y-3">
              {FREE_FEATURES.map((f) => (
                <li
                  key={f}
                  className="flex items-start gap-3 text-sm text-white/70"
                >
                  <CheckIcon className="mt-0.5 shrink-0 text-brand" />
                  {f}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <div className="mb-6 flex items-center gap-3">
              <h3 className="text-xl font-semibold">Pro</h3>
              <span className="rounded-full bg-brand/20 px-3 py-0.5 text-xs text-brand-glow">
                SmartCam Stand + запись
              </span>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {PRO_FEATURES.map((f) => (
                <article
                  key={f.title}
                  className="glass rounded-2xl p-4 transition hover:border-brand/30"
                >
                  <span className="text-[10px] font-medium uppercase tracking-wider text-brand-glow">
                    {f.badge}
                  </span>
                  <h4 className="mt-2 font-semibold">{f.title}</h4>
                  <p className="mt-1.5 text-xs leading-relaxed text-white/50">
                    {f.description}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function CheckIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`h-4 w-4 ${className}`}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden
    >
      <path
        d="M3 8.5L6.5 12L13 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
