import QRCode from "qrcode";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://smart-cam-peach.vercel.app/";

export async function SiteQrCode() {
  const svg = await QRCode.toString(SITE_URL, {
    type: "svg",
    margin: 1,
    width: 136,
    color: { dark: "#243b6b", light: "#ffffff" },
  });

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        className="rounded-2xl bg-white p-3 shadow-lg [&_svg]:block"
        dangerouslySetInnerHTML={{ __html: svg }}
        aria-hidden
      />
      <p className="max-w-xs text-center text-xs text-white/55">{SITE_URL}</p>
    </div>
  );
}
