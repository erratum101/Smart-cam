"use client";

import { PLANS } from "@/lib/content";
import { trackEvent } from "@/lib/analytics";
import { SectionHeader } from "./SectionHeader";

export function Pricing() {
  return (
    <section id="pricing" className="py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader
          label="Тарифы"
          title="Начните бесплатно"
          description="Перейдите на Pro за 300 ₽ — разовая покупка, без подписки."
        />

        <div className="mx-auto grid max-w-4xl gap-6 md:grid-cols-2">
          {PLANS.map((plan) => (
            <article
              key={plan.id}
              className={`relative flex flex-col rounded-3xl p-8 ${
                plan.highlighted
                  ? "bg-white text-brand shadow-[0_16px_48px_rgba(0,0,0,0.2)] ring-4 ring-white/40"
                  : "glass-strong"
              }`}
            >
              {plan.highlighted && (
                <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-brand px-5 py-1 text-xs font-bold text-white shadow-lg">
                  Рекомендуем
                </span>
              )}
              <h3 className={`text-xl font-bold ${plan.highlighted ? "text-brand" : ""}`}>
                {plan.name}
              </h3>
              <div className="mt-5 flex items-baseline gap-1">
                <span className="font-display text-5xl font-bold">{plan.price}</span>
                <span
                  className={`text-sm ${plan.highlighted ? "text-brand/60" : "text-white/50"}`}
                >
                  / {plan.period}
                </span>
              </div>
              <p
                className={`mt-4 text-sm leading-relaxed ${
                  plan.highlighted ? "text-brand/70" : "text-white/70"
                }`}
              >
                {plan.description}
              </p>
              <ul className="mt-6 flex-1 space-y-3">
                {plan.features.map((f) => (
                  <li
                    key={f}
                    className={`flex items-center gap-2.5 text-sm ${
                      plan.highlighted ? "text-brand/80" : "text-white/80"
                    }`}
                  >
                    <span
                      className={`flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold ${
                        plan.highlighted
                          ? "bg-brand/10 text-brand"
                          : "bg-white/20 text-white"
                      }`}
                    >
                      ✓
                    </span>
                    {f}
                  </li>
                ))}
              </ul>
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  trackEvent(plan.ctaEvent);
                  trackEvent("section_pricing", { plan: plan.id });
                }}
                className={`mt-8 block w-full rounded-full py-3.5 text-center text-sm font-bold transition active:scale-[0.98] ${
                  plan.highlighted
                    ? "bg-brand text-white shadow-lg hover:bg-brand-mid"
                    : "btn-secondary !w-full"
                }`}
              >
                {plan.cta}
              </a>
            </article>
          ))}
        </div>

        <p className="mx-auto mt-10 max-w-md text-center text-xs text-white/50">
          Разовая покупка Pro — 300 ₽, без автопродления.
        </p>
      </div>
    </section>
  );
}
