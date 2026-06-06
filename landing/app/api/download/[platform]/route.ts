import { createReadStream } from "fs";
import { access, stat } from "fs/promises";
import type { NextRequest } from "next/server";
import path from "path";
import { Readable } from "stream";

const DOWNLOADS = {
  windows: {
    diskName: "smart-cam-windows.exe",
    fileName: "Smart-Cam-App.exe",
    contentType: "application/octet-stream",
  },
  android: {
    diskName: "smart-cam-android.apk",
    fileName: "Smart-Cam-App.apk",
    contentType: "application/vnd.android.package-archive",
  },
} as const;

type Platform = keyof typeof DOWNLOADS;

function isPlatform(value: string): value is Platform {
  return value in DOWNLOADS;
}

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ platform: string }> },
) {
  const { platform } = await context.params;

  if (!isPlatform(platform)) {
    return new Response("Not found", { status: 404 });
  }

  const meta = DOWNLOADS[platform];
  const filePath = path.join(
    process.cwd(),
    "public",
    "downloads",
    meta.diskName,
  );

  try {
    await access(filePath);
  } catch {
    return new Response(
      "Файл ещё не загружен. Соберите приложение и выполните npm run sync-downloads в папке landing.",
      { status: 404 },
    );
  }

  const fileStat = await stat(filePath);
  const stream = createReadStream(filePath);

  return new Response(Readable.toWeb(stream) as ReadableStream, {
    headers: {
      "Content-Type": meta.contentType,
      "Content-Disposition": `attachment; filename="${meta.fileName}"`,
      "Content-Length": String(fileStat.size),
      "Cache-Control": "public, max-age=3600",
    },
  });
}
