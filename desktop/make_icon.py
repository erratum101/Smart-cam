"""Generate app_icon.ico from desktop/app_icon.png (or desktop/icon.png)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def _source_png(desktop: Path) -> Path:
    for rel in ("app_icon.png", "icon.png"):
        p = desktop / rel
        if p.is_file():
            return p
    raise SystemExit(
        f"Missing app_icon.png or icon.png in the desktop folder:\n  {desktop}"
    )


def main() -> None:
    desktop = Path(__file__).resolve().parent
    png = _source_png(desktop)
    ico = desktop / "app_icon.ico"
    im = Image.open(png).convert("RGBA")
    im.save(
        ico,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"Wrote {ico} from {png}")


if __name__ == "__main__":
    main()
