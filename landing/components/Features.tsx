import { FREE_FEATURES, PRO_FEATURES } from "@/lib/content";
import { SectionHeader } from "./SectionHeader";

export function Features() {
  return (
    <section id="features" className="py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader
          label="Возможности"
          title="Всё для стрима и звонков"
          description="Бесплатная версия закрывает базовые сценарии. Pro добавляет трекинг, запись и студийный вывод."
        />

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="glass-strong rounded-3xl p-8">
            <div className="mb-6 flex items-center gap-3">
              <h3 className="font-display text-2xl font-bold">Free</h3>
              <span className="rounded-full border border-white/30 bg-white/10 px-3 py-0.5 text-xs font-medium text-white/80">
                Бесплатно
              </span>
            </div>
            <ul className="space-y-3.5">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm text-white/85">
                  <CheckIcon />
                  {f}
                </li>
              ))}
            </ul>
          </div>

          <div className="glass-strong rounded-3xl p-8 ring-1 ring-white/30">
            <div className="mb-6 flex items-center gap-3">
              <h3 className="font-display text-2xl font-bold">Pro</h3>
              <span className="rounded-full bg-white px-3 py-0.5 text-xs font-bold text-brand">
                300 ₽
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {PRO_FEATURES.map((f) => (
                <article
                  key={f.title}
                  className="rounded-2xl border border-white/20 bg-white/10 p-4 transition hover:bg-white/15"
                >
                  <span className="text-[10px] font-bold uppercase tracking-wider text-white/50">
                    {f.badge}
                  </span>
                  <h4 className="mt-1.5 font-semibold">{f.title}</h4>
                  <p className="mt-1 text-xs leading-relaxed text-white/65">
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

function CheckIcon() {
  return (
    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/20">
      <svg className="h-3 w-3 text-white" viewBox="0 0 16 16" fill="none" aria-hidden>
        <path
          d="M3 8.5L6.5 12L13 4"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}
