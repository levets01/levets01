"""Build a grayscale ASCII portrait from the original image."""
import argparse
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

GRID = (96, 120)
ROW_CSS = """
.row { animation: reveal 260ms ease-out both; }
@keyframes reveal { from { opacity: 0; } to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .row { animation: none; } }
"""


def source_image(project_root: Path) -> Path | None:
    files = [
        path for name in ("asset", "assets")
        for path in (project_root / name).rglob("*")
        if path.stem.casefold() == "img_2087" and path.is_file()
    ]
    if len(files) > 1:
        raise ValueError(f"Multiple portrait sources: {', '.join(map(str, files))}")
    return next(iter(files), None)


def frame_portrait(image: Image.Image, focus: tuple[float, float]) -> Image.Image:
    """Isolate the sitter against the light studio backdrop and frame the head."""
    border = image.point(lambda level: 255 if level >= 243 else 0)
    # The padding connects all exterior edges without erasing interior highlights.
    mask = ImageOps.expand(border, border=1, fill=255)
    ImageDraw.floodfill(mask, (0, 0), 128)
    foreground = mask.crop((1, 1, image.width + 1, image.height + 1)).point(
        lambda level: 0 if level == 128 else 255)
    head_band = image.crop((0, 0, image.width, max(1, round(image.height * .56))))
    bounds = head_band.point(lambda level: 255 if level < 160 else 0).getbbox()
    enhanced = image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    tones = enhanced.point(lambda value: round(60 + 195 * (value / 255) ** .72))
    matte = foreground.filter(ImageFilter.MinFilter(5))
    isolated = Image.composite(tones, Image.new("L", image.size), matte)
    if bounds and foreground.getpixel((0, 0)) == 0:
        left, top, right, _ = bounds
        width = min(image.width, round((right - left) * 1.20))
        height = min(image.height, round(width * 410 / 320))
        x = max(0, min(image.width - width, round((left + right) / 2 - width * focus[0])))
        y = max(0, min(image.height - height, round(top - height * .17 * focus[1])))
        isolated = isolated.crop((x, y, x + width, y + height))
    return ImageOps.fit(isolated, (320, 410), Image.Resampling.LANCZOS, centering=focus)


def make_rows(path: Path, focus: tuple[float, float]) -> list[bytes]:
    with Image.open(path) as original:
        original.verify()
    with Image.open(path) as original:
        image = ImageOps.exif_transpose(original).convert("L")
    grid = frame_portrait(image, focus).resize(GRID, Image.Resampling.LANCZOS)
    pixels = grid.tobytes()
    return [pixels[start:start + grid.width] for start in range(0, len(pixels), grid.width)]


def portrait_markup(rows: list[bytes]) -> str:
    parts = ['<rect width="320" height="410" rx="10" fill="#000"/>',
             '<g fill="none" stroke-width="2.3" stroke-linecap="round" '
             'transform="translate(2 3) scale(1.1 1.12)">']
    for index, row in enumerate(rows):
        groups: dict[int, list[str]] = defaultdict(list)
        for column, luminance in enumerate(row):
            if luminance >= 20:
                shade = min(15, max(2, round((luminance - 48) * 1.45 / 17)))
                # One vertical bar per cell. Group equal tones into one SVG path.
                groups[shade].append(f"M{column * 3} 0v1")
        parts.append(f'<g class="row" transform="translate(0 {index * 3})" '
                     f'style="animation-delay:{index * 12}ms">')
        for shade, bars in groups.items():
            color = f"{shade:x}" * 3
            parts.append(f'<path stroke="#{color}" d="{"".join(bars)}"/>')
        parts.append("</g>")
    return "".join([*parts, "</g>"])


def portrait_svg(rows: list[bytes], static: bool = False) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 410" '
            'role="img" aria-labelledby="title"><title id="title">Particle portrait of Stevel Iglesias</title>'
            f'<style>{"" if static else ROW_CSS}</style>{portrait_markup(rows)}</svg>\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--focus", nargs=2, type=float, default=(0.5, 0.38))
    parser.add_argument("--static", action="store_true")
    args = parser.parse_args()
    if not all(0 <= value <= 1 for value in args.focus):
        parser.error("--focus values must be between 0 and 1")
    args.output.write_text(portrait_svg(make_rows(args.image, args.focus), args.static),
                           encoding="utf-8")


if __name__ == "__main__":
    main()
