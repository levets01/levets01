"""Build a grayscale ASCII portrait from the original image."""

import argparse
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

SIZE = (224, 246)
GRID = (84, 92)
ROW_CSS = """
.row { animation: reveal 260ms ease-out both; }
@keyframes reveal { from { opacity: 0; } to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .row { animation: none; } }
"""


def source_image(project_root: Path) -> Path | None:
    files = [
        path
        for name in ("asset", "assets")
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
        lambda level: 0 if level == 128 else 255
    )
    head_band = image.crop((0, 0, image.width, max(1, round(image.height * 0.56))))
    bounds = head_band.point(lambda level: 255 if level < 160 else 0).getbbox()
    enhanced = image.filter(
        ImageFilter.UnsharpMask(radius=1.6, percent=175, threshold=2)
    )
    tones = enhanced.point(lambda value: min(255, round(33 + value * 1.44)))
    matte = foreground.filter(ImageFilter.MinFilter(3)).filter(
        ImageFilter.GaussianBlur(0.45)
    )
    isolated = Image.composite(tones, Image.new("L", image.size), matte)
    if bounds and foreground.getpixel((0, 0)) == 0:
        left, top, right, _ = bounds
        width = min(image.width, round((right - left) * 1.15))
        height = min(image.height, round(width * SIZE[1] / SIZE[0]))
        x = max(
            0, min(image.width - width, round((left + right) / 2 - width * focus[0]))
        )
        y = max(0, min(image.height - height, round(top - height * 0.17 * focus[1])))
        isolated = isolated.crop((x, y, x + width, y + height))
    crop = ImageOps.fit(isolated, SIZE, Image.Resampling.LANCZOS, centering=focus)
    # Fade only the base of the shoulders into the surrounding terminal surface.
    fade = Image.new("L", (1, SIZE[1]))
    fade.putdata(
        [round(255 * min(1, (1 - y / (SIZE[1] - 1)) / 0.17)) for y in range(SIZE[1])]
    )
    return ImageChops.multiply(crop, fade.resize(SIZE))


def make_rows(path: Path, focus: tuple[float, float], grid_size=GRID) -> list[bytes]:
    with Image.open(path) as original:
        original.verify()
    with Image.open(path) as original:
        image = ImageOps.exif_transpose(original).convert("L")
    width, height = grid_size
    grid = frame_portrait(image, focus).resize(
        (2 * width, height), Image.Resampling.LANCZOS
    )
    return [
        grid.crop((0, y, grid.width, y + 1)).tobytes()[y % 2 :: 2]
        for y in range(height)
    ]


def portrait_markup(rows: list[bytes]) -> str:
    pitch = SIZE[0] / len(rows[0])
    glyph_style = (
        '<g font-family="Consolas,monospace" font-size="5.1" font-weight="700" '
        'text-rendering="geometricPrecision" text-anchor="middle" stroke-width=".65" '
        f'stroke-linejoin="round" transform="scale({pitch / 2:.5f})">'
    )
    parts = [glyph_style]
    for index, row in enumerate(rows):
        groups: dict[int, list[str]] = defaultdict(list)
        for column, luminance in enumerate(row):
            if luminance >= 24:
                shade = min(15, max(1, round(luminance / 17)))
                groups[shade].append(str(column * 2))
        y = (index + 0.5) * SIZE[1] / len(rows) * 2 / pitch
        parts.append(
            f'<g class="row" transform="translate({0.5 + index % 2} {y:.2f})" '
            f'style="animation-delay:{index * 11}ms">'
        )
        for shade, positions in groups.items():
            color = f"{shade:x}" * 3
            # Each ASCII full stop has its own sample position and luminance.
            parts.append(
                f'<text fill="#{color}" stroke="#{color}" y=".4" '
                f'x="{" ".join(positions)}">{"." * len(positions)}</text>'
            )
        parts.append("</g>")
    return "".join([*parts, "</g>"])


def portrait_svg(rows: list[bytes], static: bool = False) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE[0]} {SIZE[1]}" '
        'role="img" aria-labelledby="title"><title id="title">Particle portrait of Stevel Iglesias</title>'
        f'<style>{"" if static else ROW_CSS}</style><rect width="100%" height="100%" '
        f'fill="#05090D"/>{portrait_markup(rows)}</svg>\n'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--focus", nargs=2, type=float, default=(0.5, 0.38))
    parser.add_argument("--static", action="store_true")
    args = parser.parse_args()
    if not all(0 <= value <= 1 for value in args.focus):
        parser.error("--focus values must be between 0 and 1")
    args.output.write_text(
        portrait_svg(make_rows(args.image, args.focus), args.static), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
