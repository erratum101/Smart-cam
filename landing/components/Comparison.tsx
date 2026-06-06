import { COMPARISON_ROWS } from "@/lib/content";
import { SectionHeader } from "./SectionHeader";

export function Comparison() {
  return (
    <section id="compare" className="py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader
          label="Сравнение"
          title="Free vs Pro"
          description="Выберите тариф под ваш сценарий — от звонков до профессионального стрима."
        />

        <div className="glass-strong overflow-hidden rounded-3xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead>
                <tr className="border-b border-white/20 bg-white/10">
                  <th className="px-6 py-5 font-semibold text-white/70">Функция</th>
                  <th className="px-6 py-5 font-semibold text-white/90">Free</th>
                  <th className="px-6 py-5 font-semibold">
                    <span className="rounded-full bg-white px-3 py-1 text-brand">Pro</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON_ROWS.map((row, i) => (
                  <tr
                    key={row.feature}
                    className={i % 2 === 0 ? "bg-transparent" : "bg-white/[0.06]"}
                  >
                    <td className="px-6 py-4 font-medium text-white/90">
                      {row.feature}
                    </td>
                    <td className="px-6 py-4">
                      <CellValue value={row.free} />
                    </td>
                    <td className="px-6 py-4 bg-white/[0.04]">
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

function CellValue({ value, pro = false }: { value: boolean | string; pro?: boolean }) {
  if (typeof value === "boolean") {
    return value ? (
      <span className={pro ? "text-white" : "text-white/80"}>
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
      <span className="text-white/30">—</span>
    );
  }
  return (
    <span className={pro ? "font-semibold text-white" : "text-white/65"}>
      {value}
    </span>
  );
}
