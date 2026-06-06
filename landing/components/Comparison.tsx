import { COMPARISON_ROWS } from "@/lib/content";

export function Comparison() {
  return (
    <section id="compare" className="border-t border-white/5 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mb-12 text-center">
          <h2 className="font-display text-3xl font-bold sm:text-4xl">
            Free vs Pro
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-white/55">
            Сравните тарифы и выберите то, что подходит вашему сценарию.
          </p>
        </div>

        <div className="glass overflow-hidden rounded-2xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead>
                <tr className="border-b border-white/10 bg-white/[0.02]">
                  <th className="px-6 py-4 font-medium text-white/50">
                    Функция
                  </th>
                  <th className="px-6 py-4 font-medium text-white/70">Free</th>
                  <th className="px-6 py-4 font-medium text-brand-glow">Pro</th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON_ROWS.map((row, i) => (
                  <tr
                    key={row.feature}
                    className={
                      i % 2 === 0 ? "bg-transparent" : "bg-white/[0.02]"
                    }
                  >
                    <td className="px-6 py-3.5 text-white/80">{row.feature}</td>
                    <td className="px-6 py-3.5">
                      <CellValue value={row.free} />
                    </td>
                    <td className="px-6 py-3.5">
                      <CellValue value={row.pro} pro />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

function CellValue({
  value,
  pro = false,
}: {
  value: boolean | string;
  pro?: boolean;
}) {
  if (typeof value === "boolean") {
    return value ? (
      <span className={pro ? "text-brand-glow" : "text-white/70"}>
        <span className="sr-only">Да</span>
        <svg className="inline h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
          <path
            d="M3 8.5L6.5 12L13 4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    ) : (
      <span className="text-white/25">
        <span className="sr-only">Нет</span>—
      </span>
    );
  }
  return (
    <span className={pro ? "font-medium text-brand-glow" : "text-white/60"}>
      {value}
    </span>
  );
}
