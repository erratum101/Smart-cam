"use client";

import { Analytics } from "@vercel/analytics/react";
import Script from "next/script";

export function SiteAnalytics() {
  const gaId = process.env.NEXT_PUBLIC_GA_ID;

  return (
    <>
      <Analytics />
      {gaId ? (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`}
            strategy="afterInteractive"
          />
          <Script id="ga-init" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', '${gaId}', { anonymize_ip: true });
            `}
          </Script>
        </>
      ) : null}
    </>
  );
}
