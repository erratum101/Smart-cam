"use client";

import { PLANS } from "@/lib/content";
import { trackEvent } from "@/lib/analytics";

export function Pricing() {
  return (
    <section id="pricing" className="border-t border-white/5 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mb-12 text-center">
          <h2 className="font-display text-3xl font-bold sm:text-4xl">
            Тарифы
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-white/55">
            Начните бесплатно. Перейдите на Pro, когда понадобятся трекинг,
            запись и NDI.
          </p>
        </div>

        <div className="mx-auto grid max-w-4xl gap-6 md:grid-cols-2">
          {PLANS.map((plan) => (
            <article
              key={plan.id}
              className={`relative rounded-2xl p-8 ${
                plan.highlighted
                  ? "border border-brand/50 bg-brand/10 brand-glow"
                  : "glass"
              }`}
            >
              {plan.highlighted && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand px-4 py-1 text-xs font-semibold text-white">
                  Рекомендуем
                </span>
              )}
              <h3 className="text-lg font-semibold">{plan.name}</h3>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="font-display text-4xl font-bold">
                  {plan.price}
                </span>
                <span className="text-sm text-white/40">/ {plan.period}</span>
              </div>
              <p className="mt-3 text-sm text-white/55">{plan.description}</p>
              <ul className="mt-6 space-y-2.5">
                {plan.features.map((f) => (
                  <li
                    key={f}
                    className="flex items-center gap-2 text-sm text-white/70"
                  >
                    <span className="text-brand">✓</span>
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
                className={`mt-8 block w-full rounded-full py-3 text-center text-sm font-semibold transition ${
                  plan.highlighted
                    ? "bg-brand text-white hover:bg-brand-dark"
                    : "border border-white/15 text-white hover:bg-white/5"
                }`}
              >
                {plan.cta}
              </a>
            </article>
          ))}
        </div>

        <p className="mx-auto mt-10 max-w-lg text-center text-xs text-white/35">
          Цены ориентировочные. Ссылки на скачивание и оплату подключите перед
          публикацией. Годовая подписка Pro — скидка 20%.
        </p>
      </div>
    </section>
  );
}
