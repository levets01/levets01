
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from html import escape
import argparse
import math
import random

ROOT = Path(__file__).resolve().parents[1]

PALETTE = [
    "#14532D",  # sombras
    "#365C4A",  # verde oscuro
    "#647D73",  # gris verdoso
    "#A7F3D0",  # verde suave
    "#F0FFF4",  # luces
]

def create_portrait(source, output, width=210, height=235):
    random.seed(42)

    image = Image.open(source).convert("RGB")

    # Recorte centrado para conservar rostro y cabello.
    image = ImageOps.fit(
        image,
        (width, height),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.36),
    )

    gray = ImageOps.grayscale(image)
    gray = ImageEnhance.Contrast(gray).enhance(1.65)
    gray = ImageEnhance.Sharpness(gray).enhance(1.45)

    # Bordes para resaltar ojos, nariz, boca y cabello.
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edges = ImageEnhance.Contrast(edges).enhance(1.8)

    # Estimación sencilla del fondo usando las esquinas.
    corners = [
        image.getpixel((0, 0)),
        image.getpixel((width - 1, 0)),
        image.getpixel((0, height - 1)),
        image.getpixel((width - 1, height - 1)),
    ]
    background = tuple(
        sum(pixel[channel] for pixel in corners) / 4
        for channel in range(3)
    )

    def distance(a, b):
        return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))

    particles = []

    # Cuadrícula de partículas.
    step = 2.6
    cols = int(width / step)
    rows = int(height / step)

    for row in range(rows):
        for col in range(cols):
            x = int(col * step)
            y = int(row * step)

            if x >= width or y >= height:
                continue

            pixel = image.getpixel((x, y))
            luminance = gray.getpixel((x, y)) / 255
            edge = edges.getpixel((x, y)) / 255

            # Evitar partículas de fondo muy parecidas
            # al color de las esquinas.
            bg_distance = distance(pixel, background)

            if bg_distance < 25 and edge < 0.16:
                continue

            # Más detalle en bordes y rasgos faciales.
            detail = min(1, luminance * 0.75 + edge * 0.55)

            if detail < 0.12:
                continue

            color_index = min(
                len(PALETTE) - 1,
                int(detail * len(PALETTE))
            )
            color = PALETTE[color_index]

            radius = 0.30 + detail * 0.48
            opacity = min(1, 0.38 + detail * 0.62)

            # Pequeñas variaciones naturales.
            px = x + random.uniform(-0.24, 0.24)
            py = y + random.uniform(-0.24, 0.24)

            # Revelado por filas, desde el cabello.
            delay = (y / height) * 2.2 + random.uniform(0, 0.16)

            particles.append(
                f'<circle cx="{px:.2f}" cy="{py:.2f}" '
                f'r="{radius:.2f}" fill="{color}" '
                f'opacity="{opacity:.2f}" '
                f'style="--delay:{delay:.2f}s"/>'
            )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
      width="{width}" height="{height}"
      viewBox="0 0 {width} {height}"
      role="img"
      aria-label="Retrato de Stevel Iglesias formado por partículas animadas">

<defs>
  <style>
    circle {{
      transform-box: fill-box;
      transform-origin: center;
      animation: reveal 0.65s ease-out both;
      animation-delay: var(--delay);
    }}

    @keyframes reveal {{
      from {{
        opacity: 0;
        transform: scale(0.15);
      }}
      to {{
        transform: scale(1);
      }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      circle {{
        animation: none !important;
      }}
    }}
  </style>
</defs>

<g>
{''.join(particles)}
</g>

</svg>"""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")

    print(f"Retrato generado: {output}")
    print(f"Partículas: {len(particles)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default=str(ROOT / "assets" / "IMG_2087.jpg")
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "assets" / "generated" / "portrait.svg")
    )
    parser.add_argument("--width", type=int, default=210)
    parser.add_argument("--height", type=int, default=235)

    args = parser.parse_args()

    create_portrait(
        Path(args.source),
        Path(args.output),
        args.width,
        args.height,
    )
