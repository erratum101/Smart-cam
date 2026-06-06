import { DeviceMockup } from "./DeviceMockup";

export function PhoneFrame({
  className = "",
  priority = false,
  label,
  animate = false,
}: {
  className?: string;
  priority?: boolean;
  label?: string;
  animate?: boolean;
}) {
  return (
    <div className={className}>
      <div className={animate ? "animate-float" : ""}>
        <DeviceMockup kind="phone" priority={priority} shadow />
      </div>
      {label ? (
        <p className="mt-3 text-center text-sm font-medium text-white/60">
          {label}
        </p>
      ) : null}
    </div>
  );
}
