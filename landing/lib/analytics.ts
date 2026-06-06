export type AnalyticsEvent =
  | "cta_download_free"
  | "cta_download_pro"
  | "cta_waitlist"
  | "section_pricing"
  | "section_demo"
  | "nav_click";

export function trackEvent(
  name: AnalyticsEvent,
  props?: Record<string, string | number | boolean>,
) {
  if (typeof window === "undefined") return;

  const payload = { event: name, ...props };

  // Vercel Web Analytics custom events (when enabled in dashboard)
  if (typeof window.va === "function") {
    window.va("event", name, props);
  }

  // Optional Google Analytics 4
  const gaId = process.env.NEXT_PUBLIC_GA_ID;
  if (gaId && typeof window.gtag === "function") {
    window.gtag("event", name, props);
  }

  if (process.env.NODE_ENV === "development") {
    console.debug("[analytics]", payload);
  }
}

declare global {
  interface Window {
    va?: (action: string, name: string, props?: Record<string, unknown>) => void;
    gtag?: (...args: unknown[]) => void;
    dataLayer?: unknown[];
  }
}
