export function SectionHeader({
  label,
  title,
  description,
}: {
  label: string;
  title: string;
  description: string;
}) {
  return (
    <div className="mb-14 text-center">
      <span className="section-label">{label}</span>
      <h2 className="font-display text-3xl font-bold tracking-tight sm:text-5xl">
        {title}
      </h2>
      <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-white/75 sm:text-lg">
        {description}
      </p>
    </div>
  );
}
