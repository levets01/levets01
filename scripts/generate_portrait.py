"""Sample the source photograph into a deterministic, self-contained vector portrait."""

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise
from math import ceil, isfinite, sqrt
from pathlib import Path
from random import Random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

ROOT = Path(__file__).resolve().parents[1]
SIZE = (264, 292)
FOCUS = (0.5, 0.38)
PALETTE = ("#14532D", "#647D73", "#00FF88", "#A7F3D0", "#F0FFF4")
PORTRAIT_CSS = """
@media (prefers-reduced-motion:no-preference){
 .particles{animation:assemble .7s ease-out var(--at) both}
 .seed{animation:ignite 2.6s ease-out both}
 .glint{animation:assemble .8s ease-out var(--at) both,glimmer 5s ease-in-out 3.4s 2}
}
@keyframes assemble{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:translateY(0)}}
@keyframes ignite{0%{opacity:.13}30%{opacity:.48}100%{opacity:1}}
@keyframes glimmer{50%{opacity:.75}}
"""


def source_image(project_root: Path) -> Path | None:
    matches = [
        p
        for folder in ("assets", "asset")
        for p in (project_root / folder).rglob("*")
        if p.is_file() and p.stem.casefold() == "img_2087"
    ]
    if len(matches) > 1:
        raise ValueError(f"Multiple portrait sources: {matches}")
    return next(iter(matches), None)


def frame_portrait(image, size, focus):
    """Remove only the pale backdrop connected to the exterior, preserving the shirt."""
    border = image.point(lambda v: 255 if v >= 242 else 0)
    padded = ImageOps.expand(border, border=1, fill=255)
    ImageDraw.floodfill(padded, (0, 0), 128)
    mask = padded.crop((1, 1, image.width + 1, image.height + 1)).point(
        lambda v: 0 if v == 128 else 255
    )
    head = image.crop((0, 0, image.width, max(1, round(image.height * 0.55))))
    bounds = head.point(lambda v: 255 if v < 150 else 0).getbbox()
    if bounds and mask.getpixel((0, 0)) == 0:
        left, top, right, _ = bounds
        cw = min(image.width, max(1, round((right - left) * 1.27)))
        ch = min(image.height, max(1, round(cw * size[1] / size[0])))
        x = max(0, min(image.width - cw, round((left + right) / 2 - cw * focus[0])))
        y = max(0, min(image.height - ch, round(top - ch * 0.13 * focus[1])))
        box = (x, y, x + cw, y + ch)
        image, mask = image.crop(box), mask.crop(box)
    # Resample both planes in the same coordinate space at twice the display resolution.
    sample_size = tuple(v * 2 for v in size)
    return tuple(
        ImageOps.fit(plane, sample_size, Image.Resampling.LANCZOS, centering=focus)
        for plane in (image, mask.filter(ImageFilter.MinFilter(3)))
    )


def color_ramp(palette):
    anchors = [bytes.fromhex(color[1:]) for color in palette]
    ramp = []
    for left, right in pairwise(anchors):
        for t in (0, 0.25, 0.5, 0.75):
            ramp.append(
                "#"
                + bytes(round(a + (b - a) * t) for a, b in zip(left, right))
                .hex()
                .upper()
            )
    return ramp + [palette[-1].upper()]


@dataclass
class Portrait:
    width: int
    height: int
    markup: str


def sample_portrait(
    source, width=SIZE[0], height=SIZE[1], density=1.0, palette=PALETTE, focus=FOCUS
):
    if not (
        1 <= width <= 2048
        and 1 <= height <= 2048
        and 0 < density <= 4
        and isfinite(density)
    ):
        raise ValueError(
            "Use dimensions from 1 to 2048 and a density greater than 0 and at most 4"
        )
    if not all(0 <= v <= 1 for v in focus):
        raise ValueError("--focus values must be between 0 and 1")
    if len(palette) != 5 or not all(
        re.fullmatch(r"#[0-9A-Fa-f]{6}", c) for c in palette
    ):
        raise ValueError(
            "--palette expects five #RRGGBB colors from shadows to highlights"
        )
    with Image.open(source) as original:
        gray, mask = frame_portrait(
            ImageOps.exif_transpose(original).convert("L"), (width, height), focus
        )

    # Stretch foreground tones only. Local adaptation recovers curls and facial features.
    low, high = ImageStat.Stat(gray, mask).extrema[0]
    gray = gray.point(lambda v: round((v - low) * 255 / max(1, high - low)))
    local = gray.filter(ImageFilter.GaussianBlur(max(2, width / 20)))
    sharp = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=130, threshold=2))
    detail = ImageChops.subtract(
        gray.filter(ImageFilter.MaxFilter(5)), gray.filter(ImageFilter.MinFilter(5))
    )
    luminance, neighborhood, edges, matte = (
        im.load() for im in (sharp, local, detail, mask)
    )
    silhouette = mask.filter(ImageFilter.GaussianBlur(3)).load()
    # Reserve saturated neon for fine edges; diffuse skin highlights run from sage to mint.
    colors = color_ramp((palette[0], palette[1], palette[3], palette[4]))
    pitch = 1.72 / sqrt(density)
    groups = defaultdict(lambda: defaultdict(list))
    rng = Random(2087)
    for row in range(ceil(height / pitch)):
        for col in range(ceil(width / pitch)):
            # Staggered, jittered sampling breaks up the square-pixel pattern.
            x = (col + 0.25 + 0.5 * (row % 2) + rng.uniform(-0.18, 0.18)) * pitch
            y = (row + 0.5 + rng.uniform(-0.18, 0.18)) * pitch
            if not (0 <= x < width and 0 <= y < height):
                continue
            p = (int(x * 2), int(y * 2))
            if matte[p] < 140:
                continue
            edge = min(1.0, edges[p] / 96)
            tone = (luminance[p] + 0.65 * (luminance[p] - neighborhood[p])) / 255
            tone = max(0.0, min(1.0, tone)) ** 0.64
            if y < height * 0.66 and silhouette[p] < 224:
                tone *= 0.62  # soften the pale studio fringe between individual curls
            # Keep the shirt subordinate and let its base dissolve into the frame.
            foot = max(0.0, (y / height - 0.78) / 0.22)
            tone *= 1 - 0.48 * foot
            if rng.random() > (0.82 + 0.23 * tone + 0.24 * edge) * (1 - foot**3):
                continue
            shade = round(tone * (len(colors) - 1))
            rare = rng.random()
            if rare < 0.022:
                stage = "seed"
            elif rare > 0.984 and tone > 0.42:
                stage = "glint"
            elif edge > 0.32 and 0.23 < y / height < 0.79:
                stage = "detail"
            else:
                stage = int(y / height * 5)
            # A zero-length segment with a round cap is a true circular vector dot.
            # Pack many dots into one path instead of allocating an element and timer per dot.
            accent = edge > 0.56 and 0.22 < tone < 0.72
            groups[stage][shade, accent].append((round(x * 2), round(y * 2)))
    parts = []
    for stage, tones in groups.items():
        phase = stage if stage in ("seed", "glint") else "particles"
        delay = 0.25 + stage * 0.24 if isinstance(stage, int) else 1.78
        parts.append(f'<g class="{phase}" style="--at:{delay:.2f}s">')
        for (shade, accent), points in tones.items():
            strength = shade / (len(colors) - 1)
            diameter = pitch * (1.32 + 1.32 * strength)  # coordinates are doubled
            color = palette[2] if accent else colors[shade]
            commands = []
            last_x = last_y = 0
            for x, y in points:
                commands.append(f"m{x - last_x} {y - last_y}h0")
                last_x, last_y = x, y
            parts.append(
                f'<path stroke="{color}" stroke-opacity="{0.64 + 0.36 * strength:.2f}" '
                f'stroke-width="{diameter:.2f}" d="{"".join(commands)}"/>'
            )
        parts.append("</g>")
    return Portrait(
        width,
        height,
        '<g transform="scale(.5)" fill="none" stroke-linecap="round">'
        + "".join(parts)
        + "</g>",
    )


def portrait_svg(portrait, static=False):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{portrait.width}" height="{portrait.height}" '
        f'viewBox="0 0 {portrait.width} {portrait.height}" role="img" aria-labelledby="title">'
        '<title id="title">Stevel Iglesias · retrato de partículas</title>'
        f'<style>{"" if static else PORTRAIT_CSS}</style><rect width="100%" height="100%" fill="#05090D"/>'
        f"{portrait.markup}</svg>\n"
    )


def create_portrait(
    source,
    output,
    width=SIZE[0],
    height=SIZE[1],
    *,
    density=1.0,
    palette=PALETTE,
    focus=FOCUS,
    static=False,
):
    portrait = sample_portrait(source, width, height, density, palette, focus)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(portrait_svg(portrait, static), encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, nargs="?")
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", dest="output_option", type=Path)
    parser.add_argument("--width", type=int, default=SIZE[0])
    parser.add_argument("--height", type=int, default=SIZE[1])
    parser.add_argument(
        "--density",
        type=float,
        default=1.0,
        help="Samples per area relative to the default",
    )
    parser.add_argument(
        "--palette",
        default="hologram",
        help="hologram or five comma-separated #RRGGBB colors",
    )
    parser.add_argument("--focus", nargs=2, type=float, default=FOCUS)
    parser.add_argument("--static", action="store_true")
    args = parser.parse_args()
    if (args.image and args.source) or (args.output and args.output_option):
        parser.error("Specify each path once")
    palette = (
        PALETTE
        if args.palette == "hologram"
        else tuple(c.strip() for c in args.palette.split(","))
    )
    try:
        source = args.image or args.source or source_image(ROOT)
        if source is None:
            parser.error("Portrait source IMG_2087 is missing")
        create_portrait(
            source,
            args.output or args.output_option or ROOT / "assets/generated/portrait.svg",
            args.width,
            args.height,
            density=args.density,
            palette=palette,
            focus=args.focus,
            static=args.static,
        )
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
